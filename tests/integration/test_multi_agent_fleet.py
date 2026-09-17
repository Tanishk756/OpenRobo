import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Enable dev CA and test environment
os.environ["OPENROBO_DEV_CA"] = "true"
os.environ["ENVIRONMENT"] = "development"

from openrobo_agent.certificates import compute_certificate_fingerprint, generate_agent_key_and_csr
from openrobo_agent.models import MessageEnvelope
from openrobo_agent.spool import OfflineTelemetrySpool

from apps.api.database import Base, get_db
from apps.api.main import app


@pytest.fixture
async def async_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, session_factory

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_three_agent_full_lifecycle_and_security_acceptance(async_client, tmp_path):
    """
    Milestone 7.1 Multi-Agent Integration & Security Acceptance Test:
    Proves:
    1. 3 distinct agents with independently generated private keys and CSRs
    2. Single-use enrollment tokens with transactional consumption
    3. Distinct signed X.509 certificates and device UUIDs
    4. Isolated heartbeat ingestion and sliding-window status derivation
    5. Isolated telemetry ingestion and querying
    6. Cross-device authorization rejection (Robot Alpha -> Robot Beta write blocked with 403)
    7. Offline SQLite spool queuing, reconnect, and replay
    8. Replay protection (duplicate message ID, stale timestamp, clock skew)
    9. Device revocation enforcement (immediate rejection of heartbeats and telemetry)
    """
    client, session_factory = async_client

    # -------------------------------------------------------------
    # 1. Generate 3 distinct private keys and CSRs
    # -------------------------------------------------------------
    devices_info = [
        {"name": "robot-alpha", "domain": "ugv", "robot_type": "rover", "dev_id": str(uuid.uuid4())},
        {"name": "robot-beta", "domain": "manipulation", "robot_type": "arm", "dev_id": str(uuid.uuid4())},
        {"name": "robot-gamma", "domain": "uav", "robot_type": "quadrotor", "dev_id": str(uuid.uuid4())},
    ]

    agent_crypto = {}
    for dev in devices_info:
        key_pem, csr_pem = generate_agent_key_and_csr(dev["dev_id"], dev["name"])
        agent_crypto[dev["name"]] = {
            "key_pem": key_pem,
            "csr_pem": csr_pem,
            "dev_id": dev["dev_id"],
            "domain": dev["domain"],
            "robot_type": dev["robot_type"],
        }

    # Verify 3 distinct private keys
    keys = [agent_crypto[d["name"]]["key_pem"] for d in devices_info]
    assert len(set(keys)) == 3, "Agent private keys must be independently generated and distinct"

    # -------------------------------------------------------------
    # 2. Issue 3 single-use enrollment tokens
    # -------------------------------------------------------------
    tokens = {}
    for dev in devices_info:
        res = await client.post(
            "/api/v1/fleet/enrollment-tokens",
            json={"device_name": dev["name"], "domain": dev["domain"], "robot_type": dev["robot_type"]}
        )
        assert res.status_code in [200, 201]
        data = res.json()
        tokens[dev["name"]] = data["token"]
        assert data["token"].startswith("orb_tok_")

    assert len(set(tokens.values())) == 3, "Enrollment tokens must be distinct"

    # -------------------------------------------------------------
    # 3. Enroll each device and obtain signed X.509 certificates
    # -------------------------------------------------------------
    enrolled_data = {}
    for dev in devices_info:
        name = dev["name"]
        res = await client.post(
            "/api/v1/fleet/enroll",
            json={
                "enrollment_token": tokens[name],
                "device_id": agent_crypto[name]["dev_id"],
                "csr_pem": agent_crypto[name]["csr_pem"],
                "hardware_fingerprint": f"sim-hw-fp-{name}"
            }
        )
        assert res.status_code == 200, f"Enrollment failed for {name}: {res.text}"
        data = res.json()
        assert data["device_id"] == agent_crypto[name]["dev_id"]
        assert data["status"] in ["ENROLLED", "ONLINE"]
        assert "BEGIN CERTIFICATE" in data["certificate_pem"]

        fingerprint = compute_certificate_fingerprint(data["certificate_pem"])
        enrolled_data[name] = {
            "cert_pem": data["certificate_pem"],
            "fingerprint": fingerprint,
            "device_id": data["device_id"],
            "ca_cert_pem": data["ca_certificate_pem"],
        }

    # Verify certificates and fingerprints are distinct
    fingerprints = [enrolled_data[d["name"]]["fingerprint"] for d in devices_info]
    assert len(set(fingerprints)) == 3, "Certificate fingerprints must be unique across all devices"

    # Verify single-use token consumption (cannot re-use token)
    for dev in devices_info:
        name = dev["name"]
        replay_enroll = await client.post(
            "/api/v1/fleet/enroll",
            json={
                "enrollment_token": tokens[name],
                "device_id": agent_crypto[name]["dev_id"],
                "csr_pem": agent_crypto[name]["csr_pem"],
            }
        )
        assert replay_enroll.status_code in [400, 409], "Single-use token must be rejected upon second attempt"

    # -------------------------------------------------------------
    # 4. Heartbeat Ingestion and Status Verification
    # -------------------------------------------------------------
    for dev in devices_info:
        name = dev["name"]
        dev_id = enrolled_data[name]["device_id"]
        fp = enrolled_data[name]["fingerprint"]

        envelope = MessageEnvelope(
            message_id=str(uuid.uuid4()),
            device_id=dev_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            message_type="HEARTBEAT",
            payload={
                "battery_percentage": 92.5,
                "cpu_percent": 12.0,
                "memory_used_mb": 1024,
                "memory_total_mb": 4096,
                "active_nodes_count": 5,
                "active_topics_count": 14,
                "ros_distro": "humble",
                "status": "ONLINE"
            }
        )

        res = await client.post(
            "/api/v1/fleet/agent/heartbeat",
            headers={"X-OpenRobo-Cert-Fingerprint": fp},
            json=envelope.model_dump(mode="json")
        )
        assert res.status_code == 200, f"Heartbeat failed for {name}: {res.text}"
        hb_resp = res.json()
        assert hb_resp["status"] == "ACK"
        assert hb_resp["device_id"] == dev_id

    # Verify device listing shows all 3 devices as ONLINE
    list_res = await client.get("/api/v1/fleet/devices")
    assert list_res.status_code == 200
    devices_list = list_res.json()
    assert len(devices_list) == 3
    for d in devices_list:
        assert d["status"] == "ONLINE"

    # -------------------------------------------------------------
    # 5. Telemetry Ingestion and Query Isolation
    # -------------------------------------------------------------
    # Send telemetry for robot-alpha
    alpha_id = enrolled_data["robot-alpha"]["device_id"]
    alpha_fp = enrolled_data["robot-alpha"]["fingerprint"]

    alpha_envelope = MessageEnvelope(
        message_id=str(uuid.uuid4()),
        device_id=alpha_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        message_type="TELEMETRY",
        payload={
            "stream": "diagnostics",
            "data": {"temperature_c": 38.5, "motor_rpm": 1200}
        }
    )
    res = await client.post(
        "/api/v1/fleet/agent/telemetry",
        headers={"X-OpenRobo-Cert-Fingerprint": alpha_fp},
        json=alpha_envelope.model_dump(mode="json")
    )
    assert res.status_code == 200

    # Query telemetry for robot-alpha
    tel_res = await client.get(f"/api/v1/fleet/devices/{alpha_id}/telemetry")
    assert tel_res.status_code == 200
    events = tel_res.json()
    assert len(events) == 1
    assert events[0]["payload"]["data"]["temperature_c"] == 38.5

    # Query telemetry for robot-beta (must be empty)
    beta_id = enrolled_data["robot-beta"]["device_id"]
    beta_tel_res = await client.get(f"/api/v1/fleet/devices/{beta_id}/telemetry")
    assert beta_tel_res.status_code == 200
    assert len(beta_tel_res.json()) == 0, "Robot Beta telemetry must be strictly isolated from Robot Alpha"

    # -------------------------------------------------------------
    # 6. Cross-Device Authorization Attack (Robot Alpha -> Robot Beta write)
    # -------------------------------------------------------------
    spoofed_envelope = MessageEnvelope(
        message_id=str(uuid.uuid4()),
        device_id=beta_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        message_type="TELEMETRY",
        payload={"stream": "diagnostics", "data": {"malicious_override": True}}
    )
    spoof_res = await client.post(
        "/api/v1/fleet/agent/telemetry",
        headers={"X-OpenRobo-Cert-Fingerprint": alpha_fp},
        json=spoofed_envelope.model_dump(mode="json")
    )
    assert spoof_res.status_code == 403, "Cross-device write must be rejected with 403 Forbidden"
    assert "Cross-device access forbidden" in spoof_res.json()["detail"]

    # -------------------------------------------------------------
    # 7. Replay Protection Verification
    # -------------------------------------------------------------
    valid_id = str(uuid.uuid4())
    msg_env = MessageEnvelope(
        message_id=valid_id,
        device_id=alpha_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        message_type="TELEMETRY",
        payload={"stream": "ros_graph", "data": {"nodes": ["/nav2"]}}
    )
    res1 = await client.post(
        "/api/v1/fleet/agent/telemetry",
        headers={"X-OpenRobo-Cert-Fingerprint": alpha_fp},
        json=msg_env.model_dump(mode="json")
    )
    assert res1.status_code == 200

    # Attempt to replay the exact same envelope
    res2 = await client.post(
        "/api/v1/fleet/agent/telemetry",
        headers={"X-OpenRobo-Cert-Fingerprint": alpha_fp},
        json=msg_env.model_dump(mode="json")
    )
    assert res2.status_code in [400, 409]
    assert "Replay detected" in res2.json()["detail"]

    # Test stale timestamp (> 60s ago)
    stale_env = MessageEnvelope(
        message_id=str(uuid.uuid4()),
        device_id=alpha_id,
        timestamp=(datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat(),
        message_type="TELEMETRY",
        payload={"stream": "ros_graph", "data": {}}
    )
    stale_res = await client.post(
        "/api/v1/fleet/agent/telemetry",
        headers={"X-OpenRobo-Cert-Fingerprint": alpha_fp},
        json=stale_env.model_dump(mode="json")
    )
    assert stale_res.status_code == 400
    assert "Timestamp is too stale" in stale_res.json()["detail"]

    # Test future timestamp clock skew (> 60s ahead)
    future_env = MessageEnvelope(
        message_id=str(uuid.uuid4()),
        device_id=alpha_id,
        timestamp=(datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat(),
        message_type="TELEMETRY",
        payload={"stream": "ros_graph", "data": {}}
    )
    future_res = await client.post(
        "/api/v1/fleet/agent/telemetry",
        headers={"X-OpenRobo-Cert-Fingerprint": alpha_fp},
        json=future_env.model_dump(mode="json")
    )
    assert future_res.status_code == 400
    assert "Timestamp is too far in the future" in future_res.json()["detail"]

    # -------------------------------------------------------------
    # 8. Offline Spool Queuing and Replay Test
    # -------------------------------------------------------------
    spool_db = tmp_path / "agent_spool.db"
    spool = OfflineTelemetrySpool(db_path=spool_db)

    # Enqueue 5 telemetry events while disconnected
    for i in range(5):
        spool_env = MessageEnvelope(
            message_id=str(uuid.uuid4()),
            device_id=alpha_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            message_type="TELEMETRY",
            payload={"stream": "offline_diagnostics", "step": i, "offline_reading": 100 + i}
        )
        assert spool.enqueue(spool_env) is True
    assert spool.count() == 5

    # Fetch pending events and drain to server
    pending = spool.peek(10)
    assert len(pending) == 5

    for item in pending:
        drain_res = await client.post(
            "/api/v1/fleet/agent/telemetry",
            headers={"X-OpenRobo-Cert-Fingerprint": alpha_fp},
            json=item.model_dump(mode="json")
        )
        assert drain_res.status_code == 200
        spool.acknowledge(item.message_id)

    assert spool.count() == 0, "Spool must be empty after successful batch drain"

    # -------------------------------------------------------------
    # 9. Revocation Enforcement Test (Revoking Robot Beta)
    # -------------------------------------------------------------
    revoke_res = await client.post(
        f"/api/v1/fleet/devices/{beta_id}/revoke",
        json={"reason": "Security vulnerability detected on manipulator firmware"}
    )
    assert revoke_res.status_code == 200
    assert revoke_res.json()["status"] == "REVOKED"

    beta_fp = enrolled_data["robot-beta"]["fingerprint"]

    # Attempt heartbeat from revoked Robot Beta -> 403
    beta_hb = MessageEnvelope(
        message_id=str(uuid.uuid4()),
        device_id=beta_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        message_type="HEARTBEAT",
        payload={"status": "ONLINE"}
    )
    beta_hb_res = await client.post(
        "/api/v1/fleet/agent/heartbeat",
        headers={"X-OpenRobo-Cert-Fingerprint": beta_fp},
        json=beta_hb.model_dump(mode="json")
    )
    assert beta_hb_res.status_code == 403
    assert "revoked" in beta_hb_res.json()["detail"].lower()

    # Attempt telemetry from revoked Robot Beta -> 403
    beta_tel = MessageEnvelope(
        message_id=str(uuid.uuid4()),
        device_id=beta_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        message_type="TELEMETRY",
        payload={"stream": "diagnostics", "data": {}}
    )
    beta_tel_res = await client.post(
        "/api/v1/fleet/agent/telemetry",
        headers={"X-OpenRobo-Cert-Fingerprint": beta_fp},
        json=beta_tel.model_dump(mode="json")
    )
    assert beta_tel_res.status_code == 403
    assert "revoked" in beta_tel_res.json()["detail"].lower()

    # Verify Robot Alpha and Robot Gamma remain unaffected and ONLINE
    alpha_status = await client.get(f"/api/v1/fleet/devices/{alpha_id}")
    assert alpha_status.status_code == 200
    assert alpha_status.json()["status"] == "ONLINE"

    gamma_id = enrolled_data["robot-gamma"]["device_id"]
    gamma_status = await client.get(f"/api/v1/fleet/devices/{gamma_id}")
    assert gamma_status.status_code == 200
    assert gamma_status.json()["status"] == "ONLINE"
