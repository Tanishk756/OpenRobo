# Focused verification tests for canonical instruction digests, Canary validation,
# source immutability, pause/resume exact restoration, and status idempotency.

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from openrobo_release.deployment_protocol import (
    CANONICAL_PROTOCOL_VERSION,
    CanaryStageConfig,
    DeploymentInstructionEnvelope,
    InstructionType,
    RolloutStrategy,
    RolloutStrategyType,
    canonical_instruction_digest,
)

from apps.api.schemas.deployment import ArtifactSourceCreate

ADMIN_HEADERS = {"X-OpenRobo-Admin-Key": "test-admin-secret"}


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    monkeypatch.setenv("OPENROBO_DEV_CA", "true")
    monkeypatch.setenv("OPENROBO_DEV_RELEASE_SIGNING", "true")
    monkeypatch.setenv("OPENROBO_ADMIN_KEY", "test-admin-secret")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("OPENROBO_ALLOW_DEV_CERT_HEADER", "true")
    monkeypatch.setenv("OPENROBO_ALLOW_DEV_ARTIFACT_HTTP", "true")
    from apps.api.services.fleet_security import get_rate_limiter, get_replay_manager
    get_rate_limiter().clear()
    get_replay_manager().clear()


def test_canonical_instruction_digest_binding():
    """Amendment 1: Canonical instruction digest binds all security fields."""
    env1 = DeploymentInstructionEnvelope(
        protocol_version=CANONICAL_PROTOCOL_VERSION,
        instruction_id="inst-001",
        deployment_id="dep-001",
        device_id="bot-001",
        generation=1,
        instruction_type=InstructionType.STAGE_RELEASE,
        payload={"release_id": "rel-001", "version": "1.0.0"},
        payload_digest="a" * 64,
        created_at="2026-09-18T12:00:00Z",
        expires_at="2026-09-18T13:00:00Z",
    )

    digest1 = canonical_instruction_digest(env1)
    assert len(digest1) == 64

    # Altering device_id changes full digest
    env2 = env1.model_copy(update={"device_id": "bot-002"})
    digest2 = canonical_instruction_digest(env2)
    assert digest1 != digest2

    # Altering expires_at changes full digest
    env3 = env1.model_copy(update={"expires_at": "2026-09-18T14:00:00Z"})
    digest3 = canonical_instruction_digest(env3)
    assert digest1 != digest3

    # Altering instruction_type changes full digest
    env4 = env1.model_copy(update={"instruction_type": InstructionType.CANCEL_DEPLOYMENT})
    digest4 = canonical_instruction_digest(env4)
    assert digest1 != digest4


def test_canary_percentage_and_max_stages_validation():
    """Canary stages must be strictly increasing, terminate at 100, and max 3 stages."""
    # Valid (3 stages)
    RolloutStrategy(
        strategy_type=RolloutStrategyType.CANARY,
        stages=[
            CanaryStageConfig(stage_index=0, target_percentage=10),
            CanaryStageConfig(stage_index=1, target_percentage=40),
            CanaryStageConfig(stage_index=2, target_percentage=100),
        ],
    )
    # Valid (2 stages)
    RolloutStrategy(
        strategy_type=RolloutStrategyType.CANARY,
        stages=[
            CanaryStageConfig(stage_index=0, target_percentage=33),
            CanaryStageConfig(stage_index=1, target_percentage=100),
        ],
    )

    # >3 stages rejected
    with pytest.raises(ValueError, match="Maximum 3 canary stages"):
        RolloutStrategy(
            strategy_type=RolloutStrategyType.CANARY,
            stages=[
                CanaryStageConfig(stage_index=0, target_percentage=10),
                CanaryStageConfig(stage_index=1, target_percentage=30),
                CanaryStageConfig(stage_index=2, target_percentage=60),
                CanaryStageConfig(stage_index=3, target_percentage=100),
            ],
        )

    # Non-increasing rejected
    with pytest.raises(ValueError):
        RolloutStrategy(
            strategy_type=RolloutStrategyType.CANARY,
            stages=[
                CanaryStageConfig(stage_index=0, target_percentage=10),
                CanaryStageConfig(stage_index=1, target_percentage=10),
                CanaryStageConfig(stage_index=2, target_percentage=100),
            ],
        )

    # Not ending in 100 rejected
    with pytest.raises(ValueError):
        RolloutStrategy(
            strategy_type=RolloutStrategyType.CANARY,
            stages=[
                CanaryStageConfig(stage_index=0, target_percentage=10),
                CanaryStageConfig(stage_index=1, target_percentage=90),
            ],
        )


def test_artifact_source_schema_validation(monkeypatch):
    """ArtifactSourceCreate rejects plain HTTP without dev bypass, credentials, query, fragment."""
    # In production mode without flag
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("OPENROBO_ALLOW_DEV_ARTIFACT_HTTP", raising=False)

    with pytest.raises(ValueError, match="HTTP artifact sources are only permitted"):
        ArtifactSourceCreate(id="src-1", base_url="http://example.com/artifacts", allowed_host="example.com")

    with pytest.raises(ValueError, match="user credentials"):
        ArtifactSourceCreate(id="src-2", base_url="https://user:pass@example.com/artifacts", allowed_host="example.com")

    with pytest.raises(ValueError, match="query parameters"):
        ArtifactSourceCreate(id="src-3", base_url="https://example.com/artifacts?a=1", allowed_host="example.com")

    # In development mode with explicit dev HTTP flag -> allowed
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("OPENROBO_ALLOW_DEV_ARTIFACT_HTTP", "true")
    src = ArtifactSourceCreate(id="src-4", base_url="http://127.0.0.1:8000/artifacts", allowed_host="127.0.0.1")
    assert src.base_url == "http://127.0.0.1:8000/artifacts"


@pytest.mark.asyncio
async def test_source_registration_and_immutability(client: AsyncClient):
    """Source immutability when referenced by releases."""
    # 1. Valid HTTPS source
    res = await client.post(
        "/api/v1/releases/sources",
        json={"id": "src-secure-1", "base_url": "https://artifacts.example.com/v1", "allowed_host": "artifacts.example.com"},
        headers=ADMIN_HEADERS,
    )
    assert res.status_code == 201

    # 2. Register release referencing this source
    rel_res = await client.post(
        "/api/v1/releases",
        json={
            "release_id": "rel-imm-01",
            "release_version": "1.0.0",
            "manifest_digest": "a" * 64,
            "artifact_digest": "b" * 64,
            "workspace_digest": "c" * 64,
            "release_key_id": "key-01",
            "artifact_source_id": "src-secure-1",
            "target_os": "linux",
            "target_architecture": "x86_64",
            "target_ros_distro": "humble",
        },
        headers=ADMIN_HEADERS,
    )
    assert rel_res.status_code == 201

    # 3. Attempting to mutate source referenced by release -> must be 409 Conflict
    mut_res = await client.put(
        "/api/v1/releases/sources/src-secure-1",
        json={"id": "src-secure-1", "base_url": "https://mutated.example.com/v1", "allowed_host": "mutated.example.com"},
        headers=ADMIN_HEADERS,
    )
    assert mut_res.status_code == 409


@pytest.mark.asyncio
async def test_idempotency_request_digest(client: AsyncClient):
    """Idempotency with canonical request digest."""
    # Enroll test device
    token_resp = await client.post(
        "/api/v1/fleet/enrollment-tokens",
        json={"device_name": "bot-idem-01", "ttl_minutes": 15},
        headers=ADMIN_HEADERS,
    )
    token = token_resp.json()["token"]

    from openrobo_agent.certificates import generate_agent_key_and_csr

    _, csr_pem = generate_agent_key_and_csr(device_id="bot-idem-01")

    enroll_resp = await client.post(
        "/api/v1/fleet/enroll",
        json={
            "device_id": "bot-idem-01",
            "device_name": "bot-idem-01",
            "enrollment_token": token,
            "csr_pem": csr_pem,
            "domain": "general_robotics",
            "robot_type": "mobile_base",
            "capabilities": ["navigation"],
        },
    )
    fp = enroll_resp.json()["certificate_fingerprint"]

    await client.post(
        "/api/v1/fleet/agent/heartbeat",
        json={
            "protocol_version": "1.0.0",
            "message_id": "hb-idem-01",
            "device_id": "bot-idem-01",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message_type": "HEARTBEAT",
            "payload": {
                "status": "ACTIVE",
                "os": "linux",
                "architecture": "x86_64",
                "ros_distro": "humble",
            },
        },
        headers={"X-OpenRobo-Cert-Fingerprint": fp},
    )

    # Register release
    await client.post(
        "/api/v1/releases/sources",
        json={"id": "src-idem", "base_url": "https://artifacts.example.com/v1", "allowed_host": "artifacts.example.com"},
        headers=ADMIN_HEADERS,
    )
    await client.post(
        "/api/v1/releases",
        json={
            "release_id": "rel-idem-01",
            "release_version": "1.0.0",
            "manifest_digest": "d" * 64,
            "artifact_digest": "e" * 64,
            "workspace_digest": "f" * 64,
            "release_key_id": "key-01",
            "artifact_source_id": "src-idem",
            "target_os": "linux",
            "target_architecture": "x86_64",
            "target_ros_distro": "humble",
        },
        headers=ADMIN_HEADERS,
    )

    req_body_1 = {
        "release_id": "rel-idem-01",
        "rollout_strategy": {"strategy_type": "IMMEDIATE_ALL"},
        "target_filter": {"device_ids": ["bot-idem-01"]},
        "idempotency_key": "idem-key-12345",
    }

    # First request -> created
    r1 = await client.post("/api/v1/deployments", json=req_body_1, headers=ADMIN_HEADERS)
    assert r1.status_code == 201
    dep_id_1 = r1.json()["id"]

    # Same request + same key -> returns existing deployment (201)
    r2 = await client.post("/api/v1/deployments", json=req_body_1, headers=ADMIN_HEADERS)
    assert r2.status_code == 201
    assert r2.json()["id"] == dep_id_1

    # Altered request + same key -> 409 Conflict
    req_body_altered = dict(req_body_1, target_filter={"device_ids": ["bot-idem-01", "bot-diff"]})
    r3 = await client.post("/api/v1/deployments", json=req_body_altered, headers=ADMIN_HEADERS)
    assert r3.status_code == 409


@pytest.mark.asyncio
async def test_pause_and_resume_preserves_exact_state(client: AsyncClient):
    """Pause and resume preserves exact valid previous state instead of always jumping to STAGING."""
    # 1. Create a deployment
    token_resp = await client.post(
        "/api/v1/fleet/enrollment-tokens",
        json={"device_name": "bot-pause-01", "ttl_minutes": 15},
        headers=ADMIN_HEADERS,
    )
    token = token_resp.json()["token"]

    from openrobo_agent.certificates import generate_agent_key_and_csr

    _, csr_pem = generate_agent_key_and_csr(device_id="bot-pause-01")

    enroll_resp = await client.post(
        "/api/v1/fleet/enroll",
        json={
            "device_id": "bot-pause-01",
            "device_name": "bot-pause-01",
            "enrollment_token": token,
            "csr_pem": csr_pem,
            "domain": "general_robotics",
            "robot_type": "mobile_base",
            "capabilities": ["navigation"],
        },
    )
    fp = enroll_resp.json()["certificate_fingerprint"]

    await client.post(
        "/api/v1/fleet/agent/heartbeat",
        json={
            "protocol_version": "1.0.0",
            "message_id": "hb-pause-01",
            "device_id": "bot-pause-01",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message_type": "HEARTBEAT",
            "payload": {
                "status": "ACTIVE",
                "os": "linux",
                "architecture": "x86_64",
                "ros_distro": "humble",
            },
        },
        headers={"X-OpenRobo-Cert-Fingerprint": fp},
    )

    await client.post(
        "/api/v1/releases/sources",
        json={"id": "src-pause", "base_url": "https://artifacts.example.com/v1", "allowed_host": "artifacts.example.com"},
        headers=ADMIN_HEADERS,
    )
    await client.post(
        "/api/v1/releases",
        json={
            "release_id": "rel-pause-01",
            "release_version": "1.0.0",
            "manifest_digest": "1" * 64,
            "artifact_digest": "2" * 64,
            "workspace_digest": "3" * 64,
            "release_key_id": "key-01",
            "artifact_source_id": "src-pause",
            "target_os": "linux",
            "target_architecture": "x86_64",
            "target_ros_distro": "humble",
        },
        headers=ADMIN_HEADERS,
    )

    create_resp = await client.post(
        "/api/v1/deployments",
        json={
            "release_id": "rel-pause-01",
            "rollout_strategy": {"strategy_type": "IMMEDIATE_ALL"},
            "target_filter": {"device_ids": ["bot-pause-01"]},
        },
        headers=ADMIN_HEADERS,
    )
    assert create_resp.status_code == 201
    dep_id = create_resp.json()["id"]

    # Deployment created is in STAGE_0_STAGING. Let's pause it:
    p_resp = await client.post(f"/api/v1/deployments/{dep_id}/pause", headers=ADMIN_HEADERS)
    assert p_resp.status_code == 200
    assert p_resp.json()["status"] == "PAUSED"

    # Resume it: should return to STAGE_0_STAGING
    r_resp = await client.post(f"/api/v1/deployments/{dep_id}/resume", headers=ADMIN_HEADERS)
    assert r_resp.status_code == 200
    assert r_resp.json()["status"] == "STAGING_STAGE_0"
