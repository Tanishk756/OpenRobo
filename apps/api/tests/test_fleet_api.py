import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from openrobo_agent.certificates import generate_agent_key_and_csr
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.database import Base, get_db
from apps.api.main import app
from apps.api.services.fleet_security import get_replay_manager

# In-memory SQLite DB for tests
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def enable_dev_ca(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROBO_DEV_CA", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    # Clean up replay cache before each test
    get_replay_manager().clear()


@pytest.fixture
async def async_client(tmp_path):
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
        yield client

    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_token_issuance_and_single_use_enrollment(async_client, tmp_path):
    # 1. Issue Token
    res = await async_client.post("/api/v1/fleet/enrollment-tokens", json={"device_name": "test-rover-01", "ttl_minutes": 30})
    assert res.status_code == 201
    tok_data = res.json()
    token = tok_data["token"]
    assert token.startswith("orb_tok_")

    # 2. Generate Key and CSR
    dev_id = "00000000-0000-0000-0000-000000000001"
    key_pem, csr_pem = generate_agent_key_and_csr(dev_id, "test-rover-01")

    # 3. Enroll Device
    enroll_payload = {
        "enrollment_token": token,
        "device_id": dev_id,
        "device_name": "test-rover-01",
        "domain": "ugv",
        "robot_type": "rover",
        "csr_pem": csr_pem,
        "capabilities": ["ROS2_HUMBLE", "COLCON_BUILD"],
    }
    enroll_res = await async_client.post("/api/v1/fleet/enroll", json=enroll_payload)
    assert enroll_res.status_code == 200
    enroll_data = enroll_res.json()
    assert enroll_data["device_id"] == dev_id
    assert "BEGIN CERTIFICATE" in enroll_data["certificate_pem"]
    assert enroll_data["certificate_fingerprint"]

    # 4. Attempt Re-use of Token -> 409 Conflict
    re_res = await async_client.post("/api/v1/fleet/enroll", json=enroll_payload)
    assert re_res.status_code == 409
    assert "already been consumed" in re_res.json()["detail"]


@pytest.mark.asyncio
async def test_concurrent_token_consumption(async_client):
    # Concurrency test: Two requests attempting to consume the same token simultaneously
    res = await async_client.post("/api/v1/fleet/enrollment-tokens", json={"device_name": "race-rover", "ttl_minutes": 10})
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
async def test_replay_protection_and_clock_skew(async_client):
    # Enroll a test device
    token_res = await async_client.post("/api/v1/fleet/enrollment-tokens", json={})
    token = token_res.json()["token"]
    dev_id = "33333333-3333-3333-3333-333333333333"
    _, csr = generate_agent_key_and_csr(dev_id, "replay-bot")
    enroll_res = await async_client.post("/api/v1/fleet/enroll", json={
        "enrollment_token": token,
        "device_id": dev_id,
        "device_name": "replay-bot",
        "csr_pem": csr,
        "capabilities": [],
    })
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

    # Replay same message_id -> 409 Conflict
    hb_replay = await async_client.post("/api/v1/fleet/agent/heartbeat", json=envelope, headers=headers)
    assert hb_replay.status_code == 409
    assert "Replay detected" in hb_replay.json()["detail"]

    # Stale timestamp (> 60s ago) -> 400 Bad Request
    stale_env = dict(envelope, message_id="msg-stale-001", timestamp=(now - timedelta(seconds=120)).isoformat())
    hb_stale = await async_client.post("/api/v1/fleet/agent/heartbeat", json=stale_env, headers=headers)
    assert hb_stale.status_code == 400
    assert "stale" in hb_stale.json()["detail"]

    # Future timestamp outside skew (> 60s ahead) -> 400 Bad Request
    future_env = dict(envelope, message_id="msg-future-001", timestamp=(now + timedelta(seconds=120)).isoformat())
    hb_future = await async_client.post("/api/v1/fleet/agent/heartbeat", json=future_env, headers=headers)
    assert hb_future.status_code == 400
    assert "future" in hb_future.json()["detail"]


@pytest.mark.asyncio
async def test_cross_device_authorization_rejection(async_client):
    # Enroll Device Alpha
    t_a = (await async_client.post("/api/v1/fleet/enrollment-tokens", json={})).json()["token"]
    dev_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    _, csr_a = generate_agent_key_and_csr(dev_a, "robot-alpha")
    enroll_a = await async_client.post(
        "/api/v1/fleet/enroll",
        json={"enrollment_token": t_a, "device_id": dev_a, "device_name": "robot-alpha", "csr_pem": csr_a, "capabilities": []},
    )
    fp_a = enroll_a.json()["certificate_fingerprint"]

    # Enroll Device Beta
    t_b = (await async_client.post("/api/v1/fleet/enrollment-tokens", json={})).json()["token"]
    dev_b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    _, csr_b = generate_agent_key_and_csr(dev_b, "robot-beta")
    await async_client.post(
        "/api/v1/fleet/enroll",
        json={"enrollment_token": t_b, "device_id": dev_b, "device_name": "robot-beta", "csr_pem": csr_b, "capabilities": []},
    )

    # Device Alpha attempts to submit telemetry for Device Beta -> 403 Forbidden
    now = datetime.now(timezone.utc)
    attack_envelope = {
        "protocol_version": "1.0",
        "message_id": "attack-msg-001",
        "device_id": dev_b,  # Claims Beta's ID
        "timestamp": now.isoformat(),
        "message_type": "TELEMETRY",
        "payload": {"event_type": "ROGUE_UPDATE"},
    }
    # Alpha sends with Alpha's certificate fingerprint
    headers = {"X-OpenRobo-Cert-Fingerprint": fp_a}
    res = await async_client.post("/api/v1/fleet/agent/telemetry", json=attack_envelope, headers=headers)
    assert res.status_code == 403
    assert "Cross-device access forbidden" in res.json()["detail"]


@pytest.mark.asyncio
async def test_device_revocation_enforcement(async_client):
    # Enroll device
    t = (await async_client.post("/api/v1/fleet/enrollment-tokens", json={})).json()["token"]
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
    res = await async_client.post("/api/v1/fleet/agent/heartbeat", json={
        "protocol_version": "1.0",
        "message_id": "hb-before-revoke",
        "device_id": dev_id,
        "timestamp": now.isoformat(),
        "message_type": "HEARTBEAT",
        "payload": {"status": "ACTIVE"},
    }, headers=headers)
    assert res.status_code == 200

    # Revoke Device
    revoke_res = await async_client.post(f"/api/v1/fleet/devices/{dev_id}/revoke", json={"reason": "Compromised credential test"})
    assert revoke_res.status_code == 200
    assert revoke_res.json()["status"] == "REVOKED"

    # Attempt Heartbeat after revocation -> 403 Forbidden
    hb_after = await async_client.post("/api/v1/fleet/agent/heartbeat", json={
        "protocol_version": "1.0",
        "message_id": "hb-after-revoke",
        "device_id": dev_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message_type": "HEARTBEAT",
        "payload": {"status": "ACTIVE"},
    }, headers=headers)
    assert hb_after.status_code == 403
    assert "REVOKED" in hb_after.json()["detail"]

    # Attempt Telemetry after revocation -> 403 Forbidden
    telem_after = await async_client.post("/api/v1/fleet/agent/telemetry", json={
        "protocol_version": "1.0",
        "message_id": "telem-after-revoke",
        "device_id": dev_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message_type": "TELEMETRY",
        "payload": {"event": "TEST"},
    }, headers=headers)
    assert telem_after.status_code == 403
    assert "REVOKED" in telem_after.json()["detail"]
