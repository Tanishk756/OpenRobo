import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from openrobo_agent.certificates import create_device_csr, generate_agent_key_and_csr, generate_keypair
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.database import Base, get_db
from apps.api.main import app
from apps.api.models.fleet import AgentEnrollmentTokenModel
from apps.api.services.fleet_security import get_rate_limiter, get_replay_manager, hash_enrollment_token

# In-memory SQLite DB for tests
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def enable_dev_ca(monkeypatch):
    monkeypatch.setenv("OPENROBO_DEV_CA", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("OPENROBO_ALLOW_DEV_CERT_HEADER", "true")
    monkeypatch.setenv("OPENROBO_ADMIN_KEY", "test-admin-secret")
    get_replay_manager().clear()
    get_rate_limiter().clear()


@pytest.fixture
async def async_client():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        client.session_factory = session_factory
        yield client

    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_token_issuance_and_single_use_enrollment(async_client):
    # 1. Admin creates token
    res = await async_client.post(
        "/api/v1/fleet/enrollment-tokens",
        json={"device_name": "rover-1", "ttl_minutes": 60},
        headers={"X-OpenRobo-Admin-Key": "test-admin-secret"},
    )
    assert res.status_code == 201
    data = res.json()
    assert "token" in data
    token = data["token"]

    # 2. Agent generates keypair and CSR
    dev_id = "00000000-0000-0000-0000-000000000001"
    _, csr = generate_agent_key_and_csr(dev_id, "rover-1")

    # 3. Agent enrolls
    enroll_payload = {
        "enrollment_token": token,
        "device_id": dev_id,
        "device_name": "rover-1",
        "csr_pem": csr,
        "capabilities": ["camera", "lidar"],
    }
    enroll_res = await async_client.post("/api/v1/fleet/enroll", json=enroll_payload)
    assert enroll_res.status_code == 200
    enroll_data = enroll_res.json()
    assert enroll_data["device_id"] == dev_id
    assert "-----BEGIN CERTIFICATE-----" in enroll_data["certificate_pem"]
    assert len(enroll_data["certificate_fingerprint"]) == 64
    assert enroll_data["expires_at"] is not None

    # 4. Attempt re-enrollment with same token -> 409 Conflict
    re_enroll = await async_client.post("/api/v1/fleet/enroll", json=enroll_payload)
    assert re_enroll.status_code == 409
    assert "already been consumed" in re_enroll.json()["detail"]


@pytest.mark.asyncio
async def test_concurrent_token_consumption(async_client):
    # Two requests attempting to consume the same unbound token simultaneously
    res = await async_client.post(
        "/api/v1/fleet/enrollment-tokens",
        json={"ttl_minutes": 10},
        headers={"X-OpenRobo-Admin-Key": "test-admin-secret"},
    )
    token = res.json()["token"]

    dev1_id = "11111111-1111-1111-1111-111111111111"
    dev2_id = "22222222-2222-2222-2222-222222222222"

    _, csr1 = generate_agent_key_and_csr(dev1_id, "race-rover-1")
    _, csr2 = generate_agent_key_and_csr(dev2_id, "race-rover-2")

    req1 = {"enrollment_token": token, "device_id": dev1_id, "device_name": "race-rover-1", "csr_pem": csr1, "capabilities": []}
    req2 = {"enrollment_token": token, "device_id": dev2_id, "device_name": "race-rover-2", "csr_pem": csr2, "capabilities": []}

    res1, res2 = await asyncio.gather(
        async_client.post("/api/v1/fleet/enroll", json=req1),
        async_client.post("/api/v1/fleet/enroll", json=req2),
    )

    statuses = [res1.status_code, res2.status_code]
    assert 200 in statuses
    assert 409 in statuses


@pytest.mark.asyncio
async def test_token_device_binding_enforcement(async_client):
    # Token pre-bound to 'bound-robot-alpha'
    res = await async_client.post(
        "/api/v1/fleet/enrollment-tokens",
        json={"device_name": "bound-robot-alpha", "ttl_minutes": 30},
        headers={"X-OpenRobo-Admin-Key": "test-admin-secret"},
    )
    token = res.json()["token"]

    # Request from different device 'other-robot-beta'
    dev_id = "55555555-5555-5555-5555-555555555555"
    _, csr = generate_agent_key_and_csr(dev_id, "other-robot-beta")

    req = {
        "enrollment_token": token,
        "device_id": dev_id,
        "device_name": "other-robot-beta",
        "csr_pem": csr,
        "capabilities": [],
    }
    enroll_res = await async_client.post("/api/v1/fleet/enroll", json=req)
    assert enroll_res.status_code == 403
    assert "bound to device" in enroll_res.json()["detail"]


@pytest.mark.asyncio
async def test_expired_token_rejection(async_client):
    # Insert an expired token directly into DB
    raw_token = "orb_tok_expired_test_token_12345"
    tok_hash = hash_enrollment_token(raw_token)
    past_time = datetime.now(timezone.utc) - timedelta(hours=2)

    async with async_client.session_factory() as session:
        tok_model = AgentEnrollmentTokenModel(
            id="exp-tok-1",
            token_hash=tok_hash,
            device_name=None,
            expires_at=past_time,
            is_used=False,
        )
        session.add(tok_model)
        await session.commit()

    dev_id = "66666666-6666-6666-6666-666666666666"
    _, csr = generate_agent_key_and_csr(dev_id, "expired-test-bot")

    enroll_res = await async_client.post(
        "/api/v1/fleet/enroll",
        json={
            "enrollment_token": raw_token,
            "device_id": dev_id,
            "device_name": "expired-test-bot",
            "csr_pem": csr,
            "capabilities": [],
        },
    )
    assert enroll_res.status_code == 401
    assert "expired" in enroll_res.json()["detail"].lower()

    # Verify token was not marked is_used in DB
    async with async_client.session_factory() as session:
        stmt = select(AgentEnrollmentTokenModel).where(AgentEnrollmentTokenModel.id == "exp-tok-1")
        res = await session.execute(stmt)
        token_in_db = res.scalar_one()
        assert token_in_db.is_used is False


@pytest.mark.asyncio
async def test_csr_device_identity_mismatch_rejection(async_client):
    t_res = await async_client.post(
        "/api/v1/fleet/enrollment-tokens",
        json={},
        headers={"X-OpenRobo-Admin-Key": "test-admin-secret"},
    )
    token = t_res.json()["token"]

    # CSR generated for 'device-AAA' but request claims 'device-BBB'
    priv, _ = generate_keypair()
    csr = create_device_csr(priv, "device-AAA")

    enroll_res = await async_client.post(
        "/api/v1/fleet/enroll",
        json={
            "enrollment_token": token,
            "device_id": "device-BBB",
            "csr_pem": csr,
            "capabilities": [],
        },
    )
    assert enroll_res.status_code == 400
    assert "CSR validation failed" in enroll_res.json()["detail"]


@pytest.mark.asyncio
async def test_header_spoofing_rejected_without_dev_gate(async_client, monkeypatch):
    # In production without dev header flag, headers must be ignored
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("OPENROBO_ALLOW_DEV_CERT_HEADER", "false")

    headers = {"X-OpenRobo-Cert-Fingerprint": "aabbccdd" * 8}
    res = await async_client.post(
        "/api/v1/fleet/agent/heartbeat",
        json={
            "protocol_version": "1.0",
            "message_id": "spoof-msg-1",
            "device_id": "some-device",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message_type": "HEARTBEAT",
            "payload": {},
        },
        headers=headers,
    )
    assert res.status_code == 401
    assert "No verified client certificate identity presented" in res.json()["detail"]


@pytest.mark.asyncio
async def test_admin_endpoint_authorization_enforcement(async_client, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("OPENROBO_ADMIN_KEY", "prod-admin-secret-key")

    # 1. Without admin key -> 401
    unauth = await async_client.post("/api/v1/fleet/enrollment-tokens", json={})
    assert unauth.status_code == 401

    # 2. With invalid admin key -> 401
    invalid_auth = await async_client.post(
        "/api/v1/fleet/enrollment-tokens",
        json={},
        headers={"X-OpenRobo-Admin-Key": "wrong-key"},
    )
    assert invalid_auth.status_code == 401

    # 3. With valid admin key -> 201
    valid_auth = await async_client.post(
        "/api/v1/fleet/enrollment-tokens",
        json={},
        headers={"X-OpenRobo-Admin-Key": "prod-admin-secret-key"},
    )
    assert valid_auth.status_code == 201


@pytest.mark.asyncio
async def test_replay_protection_and_clock_skew(async_client):
    token_res = await async_client.post(
        "/api/v1/fleet/enrollment-tokens",
        json={},
        headers={"X-OpenRobo-Admin-Key": "test-admin-secret"},
    )
    token = token_res.json()["token"]
    dev_id = "33333333-3333-3333-3333-333333333333"
    _, csr = generate_agent_key_and_csr(dev_id, "replay-bot")
    enroll_res = await async_client.post(
        "/api/v1/fleet/enroll",
        json={
            "enrollment_token": token,
            "device_id": dev_id,
            "device_name": "replay-bot",
            "csr_pem": csr,
            "capabilities": [],
        },
    )
    fp = enroll_res.json()["certificate_fingerprint"]
    headers = {"X-OpenRobo-Cert-Fingerprint": fp}

    now = datetime.now(timezone.utc)
    envelope = {
        "protocol_version": "1.0",
        "message_id": "msg-unique-12345",
        "device_id": dev_id,
        "timestamp": now.isoformat(),
        "message_type": "HEARTBEAT",
        "payload": {"status": "ACTIVE", "metrics": {"cpu_percent": 10.5}},
    }

    # First attempt -> 200 OK
    hb1 = await async_client.post("/api/v1/fleet/agent/heartbeat", json=envelope, headers=headers)
    assert hb1.status_code == 200
    assert hb1.json()["status"] == "ACK"

    # Replayed attempt -> 409 Conflict
    hb2 = await async_client.post("/api/v1/fleet/agent/heartbeat", json=envelope, headers=headers)
    assert hb2.status_code == 409
    assert "Replay detected" in hb2.json()["detail"]

    # Clock skew tests
    future_envelope = dict(envelope, message_id="msg-future-1", timestamp=(now + timedelta(seconds=120)).isoformat())
    hb_future = await async_client.post("/api/v1/fleet/agent/heartbeat", json=future_envelope, headers=headers)
    assert hb_future.status_code == 400
    assert "too far in the future" in hb_future.json()["detail"]

    stale_envelope = dict(envelope, message_id="msg-stale-1", timestamp=(now - timedelta(seconds=120)).isoformat())
    hb_stale = await async_client.post("/api/v1/fleet/agent/heartbeat", json=stale_envelope, headers=headers)
    assert hb_stale.status_code == 400
    assert "too stale" in hb_stale.json()["detail"]


@pytest.mark.asyncio
async def test_cross_device_authorization_rejection(async_client):
    res_a = await async_client.post("/api/v1/fleet/enrollment-tokens", json={}, headers={"X-OpenRobo-Admin-Key": "test-admin-secret"})
    t_a = res_a.json()["token"]
    dev_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    _, csr_a = generate_agent_key_and_csr(dev_a, "robot-alpha")
    enroll_a = await async_client.post(
        "/api/v1/fleet/enroll",
        json={"enrollment_token": t_a, "device_id": dev_a, "device_name": "robot-alpha", "csr_pem": csr_a, "capabilities": []},
    )
    fp_a = enroll_a.json()["certificate_fingerprint"]

    res_b = await async_client.post("/api/v1/fleet/enrollment-tokens", json={}, headers={"X-OpenRobo-Admin-Key": "test-admin-secret"})
    t_b = res_b.json()["token"]
    dev_b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    _, csr_b = generate_agent_key_and_csr(dev_b, "robot-beta")
    await async_client.post(
        "/api/v1/fleet/enroll",
        json={"enrollment_token": t_b, "device_id": dev_b, "device_name": "robot-beta", "csr_pem": csr_b, "capabilities": []},
    )

    now = datetime.now(timezone.utc)
    attack_envelope = {
        "protocol_version": "1.0",
        "message_id": "attack-msg-001",
        "device_id": dev_b,  # Claims Beta's ID
        "timestamp": now.isoformat(),
        "message_type": "TELEMETRY",
        "payload": {"event_type": "ROGUE_UPDATE"},
    }
    headers = {"X-OpenRobo-Cert-Fingerprint": fp_a}
    res = await async_client.post("/api/v1/fleet/agent/telemetry", json=attack_envelope, headers=headers)
    assert res.status_code == 403
    assert "Cross-device access forbidden" in res.json()["detail"]


@pytest.mark.asyncio
async def test_device_revocation_enforcement(async_client):
    res_t = await async_client.post("/api/v1/fleet/enrollment-tokens", json={}, headers={"X-OpenRobo-Admin-Key": "test-admin-secret"})
    t = res_t.json()["token"]
    dev_id = "44444444-4444-4444-4444-444444444444"
    _, csr = generate_agent_key_and_csr(dev_id, "revoke-target")
    enroll = await async_client.post(
        "/api/v1/fleet/enroll",
        json={"enrollment_token": t, "device_id": dev_id, "device_name": "revoke-target", "csr_pem": csr, "capabilities": []},
    )
    fp = enroll.json()["certificate_fingerprint"]
    headers = {"X-OpenRobo-Cert-Fingerprint": fp}

    now = datetime.now(timezone.utc)
    # Valid heartbeat before revocation
    res = await async_client.post(
        "/api/v1/fleet/agent/heartbeat",
        json={
            "protocol_version": "1.0",
            "message_id": "hb-before-revoke",
            "device_id": dev_id,
            "timestamp": now.isoformat(),
            "message_type": "HEARTBEAT",
            "payload": {"status": "ACTIVE"},
        },
        headers=headers,
    )
    assert res.status_code == 200

    # Admin revokes device
    revoke_res = await async_client.post(
        f"/api/v1/fleet/devices/{dev_id}/revoke",
        json={"reason": "Compromised device"},
        headers={"X-OpenRobo-Admin-Key": "test-admin-secret"},
    )
    assert revoke_res.status_code == 200
    assert revoke_res.json()["status"] == "REVOKED"

    # Subsequent heartbeat must be rejected -> 403 Forbidden
    res_after = await async_client.post(
        "/api/v1/fleet/agent/heartbeat",
        json={
            "protocol_version": "1.0",
            "message_id": "hb-after-revoke",
            "device_id": dev_id,
            "timestamp": (now + timedelta(seconds=1)).isoformat(),
            "message_type": "HEARTBEAT",
            "payload": {"status": "ACTIVE"},
        },
        headers=headers,
    )
    assert res_after.status_code == 403
    assert "REVOKED" in res_after.json()["detail"]
