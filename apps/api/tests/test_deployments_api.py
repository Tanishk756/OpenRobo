# Unit and integration tests for release catalog, artifact distribution, and deployment orchestration APIs.

import json
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.database import Base, get_db
from apps.api.main import app
from apps.api.services.fleet_security import get_rate_limiter, get_replay_manager

VALID_DIGEST_1 = "a" * 64
VALID_DIGEST_2 = "b" * 64
VALID_DIGEST_3 = "c" * 64
ADMIN_HEADERS = {"X-OpenRobo-Admin-Key": "test-admin-secret"}
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
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
        yield client

    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_release_registration_and_validation(async_client: AsyncClient):
    # 1. Register artifact source
    src_resp = await async_client.post(
        "/api/v1/releases/sources",
        json={
            "id": "src-s3-prod",
            "base_url": "https://artifacts.openrobo.org",
            "allowed_host": "artifacts.openrobo.org",
            "max_artifact_bytes": 104857600,
            "allow_private_network": False,
        },
        headers=ADMIN_HEADERS,
    )
    assert src_resp.status_code == 201

    # 2. Register release with valid metadata
    rel_resp = await async_client.post(
        "/api/v1/releases",
        json={
            "release_id": "rel-v1.0.0",
            "release_version": "1.0.0",
            "manifest_digest": VALID_DIGEST_1,
            "artifact_digest": VALID_DIGEST_2,
            "workspace_digest": VALID_DIGEST_3,
            "release_key_id": "key-2026-prod-01",
            "artifact_source_id": "src-s3-prod",
            "target_os": "linux",
            "target_architecture": "x86_64",
            "target_ros_distro": "humble",
        },
        headers=ADMIN_HEADERS,
    )
    assert rel_resp.status_code == 201
    data = rel_resp.json()
    assert data["release_id"] == "rel-v1.0.0"
    assert data["status"] == "ACTIVE"

    # 3. Invalid digest format rejection
    bad_digest_resp = await async_client.post(
        "/api/v1/releases",
        json={
            "release_id": "rel-v1.0.1",
            "release_version": "1.0.1",
            "manifest_digest": "not-a-sha256",
            "artifact_digest": VALID_DIGEST_2,
            "workspace_digest": VALID_DIGEST_3,
            "release_key_id": "key-2026-prod-01",
            "artifact_source_id": "src-s3-prod",
        },
        headers=ADMIN_HEADERS,
    )
    assert bad_digest_resp.status_code == 422

    # 4. Non-existent artifact source rejection
    bad_src_resp = await async_client.post(
        "/api/v1/releases",
        json={
            "release_id": "rel-v1.0.2",
            "release_version": "1.0.2",
            "manifest_digest": VALID_DIGEST_1,
            "artifact_digest": VALID_DIGEST_2,
            "workspace_digest": VALID_DIGEST_3,
            "release_key_id": "key-2026-prod-01",
            "artifact_source_id": "non-existent-source",
        },
        headers=ADMIN_HEADERS,
    )
    assert bad_src_resp.status_code == 400


@pytest.mark.asyncio
async def test_deployment_creation_snapshot_and_approval(async_client: AsyncClient):
    # 1. Register artifact source and release
    await async_client.post(
        "/api/v1/releases/sources",
        json={
            "id": "src-s3-prod",
            "base_url": "https://artifacts.openrobo.org",
            "allowed_host": "artifacts.openrobo.org",
            "max_artifact_bytes": 104857600,
            "allow_private_network": False,
        },
        headers=ADMIN_HEADERS,
    )
    await async_client.post(
        "/api/v1/releases",
        json={
            "release_id": "rel-v1.0.0",
            "release_version": "1.0.0",
            "manifest_digest": VALID_DIGEST_1,
            "artifact_digest": VALID_DIGEST_2,
            "workspace_digest": VALID_DIGEST_3,
            "release_key_id": "key-2026-prod-01",
            "artifact_source_id": "src-s3-prod",
            "target_os": "linux",
            "target_architecture": "x86_64",
            "target_ros_distro": "humble",
        },
        headers=ADMIN_HEADERS,
    )

    # 2. Enroll test device
    token_resp = await async_client.post(
        "/api/v1/fleet/enrollment-tokens",
        json={"device_name": "bot-canary-01", "ttl_minutes": 15},
        headers=ADMIN_HEADERS,
    )
    assert token_resp.status_code == 201
    token = token_resp.json()["token"]

    from openrobo_agent.certificates import generate_agent_key_and_csr
    priv_pem, csr_pem = generate_agent_key_and_csr(device_id="bot-canary-01")

    enroll_resp = await async_client.post(
        "/api/v1/fleet/enroll",
        json={
            "device_id": "bot-canary-01",
            "device_name": "bot-canary-01",
            "enrollment_token": token,
            "csr_pem": csr_pem,
            "domain": "general_robotics",
            "robot_type": "mobile_base",
            "capabilities": ["navigation", "lidar"],
        },
    )
    assert enroll_resp.status_code == 200

    # Send heartbeat with ros_distro=humble
    from datetime import datetime, timezone
    hb_resp = await async_client.post(
        "/api/v1/fleet/agent/heartbeat",
        json={
            "protocol_version": "1.0",
            "message_id": "hb-canary-01",
            "device_id": "bot-canary-01",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message_type": "HEARTBEAT",
            "payload": {
                "status": "ACTIVE",
                "os": "linux",
                "architecture": "x86_64",
                "ros_distro": "humble",
            },
        },
        headers={"X-OpenRobo-Cert-Fingerprint": enroll_resp.json()["certificate_fingerprint"]},
    )
    assert hb_resp.status_code == 200

    # 3. Create deployment
    dep_resp = await async_client.post(
        "/api/v1/deployments",
        json={
            "release_id": "rel-v1.0.0",
            "rollout_strategy": {
                "strategy_type": "CANARY",
                "stages": [
                    {"stage_index": 0, "target_percentage": 50, "require_approval": True},
                    {"stage_index": 1, "target_percentage": 100, "require_approval": True},
                ],
            },
            "target_filter": {
                "device_ids": ["bot-canary-01"],
            },
            "idempotency_key": "idemp-test-01",
        },
        headers=ADMIN_HEADERS,
    )
    assert dep_resp.status_code == 201, f'Create deployment failed: {dep_resp.text}'
    dep_data = dep_resp.json()
    dep_id = dep_data["id"]
    assert dep_data["status"] == "STAGING_STAGE_0"
    assert dep_data["generation"] >= 1
    assert dep_data["version"] == 1
    assert dep_data["release_snapshot"]["manifest_digest"] == VALID_DIGEST_1

    # 4. Idempotent creation with same key returns existing
    dep_repeat = await async_client.post(
        "/api/v1/deployments",
        json={
            "release_id": "rel-v1.0.0",
            "idempotency_key": "idemp-test-01",
        },
        headers=ADMIN_HEADERS,
    )
    assert dep_repeat.status_code == 201
    assert dep_repeat.json()["id"] == dep_id

    # 5. Release is now immutable
    rel_mut_resp = await async_client.post(
        "/api/v1/releases",
        json={
            "release_id": "rel-v1.0.0",
            "release_version": "1.0.0",
            "manifest_digest": VALID_DIGEST_2,  # different digest
            "artifact_digest": VALID_DIGEST_2,
            "workspace_digest": VALID_DIGEST_3,
            "release_key_id": "key-2026-prod-01",
            "artifact_source_id": "src-s3-prod",
        },
        headers=ADMIN_HEADERS,
    )
    assert rel_mut_resp.status_code == 400

    # 6. Optimistic concurrency approval rejection on version mismatch
    bad_appr = await async_client.post(
        f"/api/v1/deployments/{dep_id}/approve",
        json={
            "stage_index": 0,
            "action": "APPROVE_CURRENT_COHORT_ACTIVATION",
            "expected_version": 999,  # Mismatched version
            "expected_state": "STAGE_0_WAITING_FOR_ACTIVATION_APPROVAL",
        },
        headers=ADMIN_HEADERS,
    )
    assert bad_appr.status_code == 409

    # 7. Check events
    ev_resp = await async_client.get(f"/api/v1/deployments/{dep_id}/events", headers=ADMIN_HEADERS)
    assert ev_resp.status_code == 200
    events = ev_resp.json()
    assert len(events) >= 1
    assert events[0]["event_type"] == "DEPLOYMENT_CREATED"
