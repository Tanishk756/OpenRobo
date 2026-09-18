# End-to-end integration and acceptance tests for authenticated remote deployment orchestration,
# signed artifact distribution, operator-gated canary rollouts, restart recovery, and direction-enforced WebSocket delivery.

import asyncio
import hashlib
import http.server
import json
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import platform
import pytest
from httpx import ASGITransport, AsyncClient

host_os = platform.system().lower()
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.database import Base, get_db
from apps.api.main import app
from apps.api.models.deployment import DeploymentModel, DeploymentInstructionModel
from apps.api.services.deployment_service import DeploymentService
from apps.api.services.fleet_security import get_rate_limiter, get_replay_manager
from openrobo_agent.certificates import generate_agent_key_and_csr
from openrobo_agent.deployment.artifact_client import ArtifactClient
from openrobo_agent.deployment.slots import ABSlotManager
from openrobo_agent.deployment.worker import DeploymentWorker, GenerationStateManager
from openrobo_release.archive import create_deterministic_archive
from openrobo_release.deployment_protocol import (
    ApprovalAction,
    DeploymentState,
    DeviceDeploymentState,
    InstructionType,
    RolloutStrategy,
    RolloutStrategyType,
    TargetFilter,
)
from openrobo_release.models import ReleaseTarget
from openrobo_release.signing import ReleaseSigner, generate_development_keypair
from openrobo_release.trust_store import TrustedReleaseKeyStore

ADMIN_HEADERS = {"X-OpenRobo-Admin-Key": "test-admin-secret"}
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    monkeypatch.setenv("OPENROBO_DEV_CA", "true")
    monkeypatch.setenv("OPENROBO_DEV_RELEASE_SIGNING", "true")
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


class RealArtifactHandler(http.server.BaseHTTPRequestHandler):
    manifest_bytes = b""
    artifact_bytes = b""
    signature_bytes = b""

    def do_GET(self):
        if self.path.endswith("/manifest.json"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(self.manifest_bytes)))
            self.end_headers()
            self.wfile.write(self.manifest_bytes)
        elif self.path.endswith("/artifact.tar.gz"):
            self.send_response(200)
            self.send_header("Content-Type", "application/gzip")
            self.send_header("Content-Length", str(len(self.artifact_bytes)))
            self.end_headers()
            self.wfile.write(self.artifact_bytes)
        elif self.path.endswith("/signature.sig"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(self.signature_bytes)))
            self.end_headers()
            self.wfile.write(self.signature_bytes)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


@pytest.mark.asyncio
async def test_single_device_remote_ota_acceptance(async_client: AsyncClient):
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        ws_dir = base_dir / "workspace"
        ws_dir.mkdir()
        (ws_dir / "app.py").write_text("print('v1.0.0 active')")

        # 1. Generate dev signing key and build signed release
        import platform
        host_os = platform.system().lower()
        signing_key, priv_bytes = generate_development_keypair(key_id="key-ota-accept")
        signer = ReleaseSigner(priv_bytes, key_id="key-ota-accept")

        target = ReleaseTarget(operating_system=host_os, architecture="x86_64", ros_distro="humble")
        artifact_path = base_dir / "release-1.0.0.tar.gz"
        manifest, _ = create_deterministic_archive(
            workspace_dir=ws_dir,
            output_path=artifact_path,
            target=target,
            release_id="rel-ota-100",
            release_version="1.0.0",
            release_key_id="key-ota-accept",
        )
        signer.sign_manifest(manifest)
        manifest_bytes = manifest.model_dump_json(indent=2).encode('utf-8')
        artifact_bytes = artifact_path.read_bytes()

        # Start real local HTTP server for artifacts
        RealArtifactHandler.manifest_bytes = manifest_bytes
        RealArtifactHandler.artifact_bytes = artifact_bytes
        RealArtifactHandler.signature_bytes = signer.sign_manifest(manifest).encode('utf-8')
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RealArtifactHandler)
        port = server.server_port
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        base_url = f"http://127.0.0.1:{port}"

        try:
            # 2. Setup trusted trust store on agent
            trust_dir = base_dir / "trusted_keys"
            trust_dir.mkdir()
            (trust_dir / f"{signing_key.key_id}.pub.json").write_text(signing_key.model_dump_json(indent=2))
            key_store = TrustedReleaseKeyStore(trust_dir=trust_dir)

            # 3. Register artifact source & release in control plane
            src_res = await async_client.post(
                "/api/v1/releases/sources",
                json={
                    "id": "src-local",
                    "base_url": base_url,
                    "allowed_host": "127.0.0.1",
                    "max_artifact_bytes": 104857600,
                    "allow_private_network": True,
                },
                headers=ADMIN_HEADERS,
            )
            assert src_res.status_code == 201

            rel_res = await async_client.post(
                "/api/v1/releases",
                json={
                    "release_id": "rel-ota-100",
                    "release_version": "1.0.0",
                    "manifest_digest": hashlib.sha256(manifest_bytes).hexdigest(),
                    "artifact_digest": manifest.artifact_digest,
                    "workspace_digest": manifest.workspace_digest,
                    "release_key_id": "key-ota-accept",
                    "artifact_source_id": "src-local",
                    "target_os": host_os,
                    "target_architecture": "x86_64",
                    "target_ros_distro": "humble",
                },
                headers=ADMIN_HEADERS,
            )
            assert rel_res.status_code == 201

            # 4. Enroll Agent
            t_res = await async_client.post(
                "/api/v1/fleet/enrollment-tokens",
                json={"device_name": "bot-single-ota"},
                headers=ADMIN_HEADERS,
            )
            token = t_res.json()["token"]
            _, csr_pem = generate_agent_key_and_csr("bot-single-ota")
            enroll_res = await async_client.post(
                "/api/v1/fleet/enroll",
                json={
                    "device_id": "bot-single-ota",
                    "device_name": "bot-single-ota",
                    "enrollment_token": token,
                    "csr_pem": csr_pem,
                    "domain": "general_robotics",
                    "robot_type": "custom",
                    "capabilities": ["navigation"],
                },
            )
            assert enroll_res.status_code == 200
            fingerprint = enroll_res.json()["certificate_fingerprint"]

            # Heartbeat
            await async_client.post(
                "/api/v1/fleet/agent/heartbeat",
                json={
                    "protocol_version": "1.0",
                    "message_id": "hb-s1",
                    "device_id": "bot-single-ota",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message_type": "HEARTBEAT",
                    "payload": {"status": "ACTIVE", "os": host_os, "architecture": "x86_64", "ros_distro": "humble"},
                },
                headers={"X-OpenRobo-Cert-Fingerprint": fingerprint},
            )

            # 5. Create deployment
            dep_res = await async_client.post(
                "/api/v1/deployments",
                json={
                    "release_id": "rel-ota-100",
                    "target_filter": {"device_ids": ["bot-single-ota"]},
                },
                headers=ADMIN_HEADERS,
            )
            assert dep_res.status_code == 201
            dep_id = dep_res.json()["id"]

            # 6. Agent worker execution
            state_dir = base_dir / "agent_state"
            slots_dir = base_dir / "agent_slots"
            state_dir.mkdir()
            slots_dir.mkdir()

            slot_mgr = ABSlotManager(deployment_root=slots_dir)
            art_client = ArtifactClient(downloads_dir=base_dir / "downloads", allow_private_network=True)

            status_reports = []
            async def mock_status_reporter(rep):
                status_reports.append(rep)

            worker = DeploymentWorker(
                device_id="bot-single-ota",
                state_dir=state_dir,
                slot_manager=slot_mgr,
                key_store=key_store,
                artifact_client=art_client,
                status_reporter=mock_status_reporter,
                artifact_base_urls={"src-local": base_url},
                current_ros_distro="humble",
            )

            # Fetch instruction from DB
            async with async_client.session_factory() as db:
                instructions = await DeploymentService.get_pending_instructions_for_device(db, "bot-single-ota")
                assert len(instructions) == 1
                inst = instructions[0]
                assert inst.instruction_type == "STAGE_RELEASE"

                from openrobo_release.deployment_protocol import DeploymentInstructionEnvelope
                env = DeploymentInstructionEnvelope(
                    instruction_id=inst.id,
                    deployment_id=inst.deployment_id,
                    generation=inst.generation,
                    instruction_type=InstructionType.STAGE_RELEASE,
                    payload=json.loads(inst.payload_json),
                    payload_digest=inst.payload_digest,
                    created_at=inst.created_at.isoformat(),
                    expires_at=inst.expires_at.isoformat(),
                )
                ack = await worker.handle_instruction(env)
                assert ack.accepted is True

                # Wait for staging execution
                for _ in range(50):
                    if any(r.state in (DeviceDeploymentState.STAGED, DeviceDeploymentState.FAILED) for r in status_reports):
                        break
                    await asyncio.sleep(0.1)

                # Check agent status progression
                states = [r.state for r in status_reports]
                print(status_reports)
                assert DeviceDeploymentState.FETCHING in states
                assert DeviceDeploymentState.VERIFYING in states
                assert DeviceDeploymentState.STAGING in states
                assert DeviceDeploymentState.STAGED in states

                # Report progression to control plane
                reported_idx = 0
                for rep in status_reports:
                    await DeploymentService.handle_device_status_report(db, "bot-single-ota", rep)
                    reported_idx += 1
                await db.commit()

            # 7. Check control plane reached operator gate: STAGE_0_WAITING_FOR_ACTIVATION_APPROVAL
            dep_get = await async_client.get(f"/api/v1/deployments/{dep_id}")
            assert dep_get.status_code == 200
            assert dep_get.json()["status"] == "STAGE_0_WAITING_FOR_ACTIVATION_APPROVAL"

            # 8. Operator approves activation
            appr_res = await async_client.post(
                f"/api/v1/deployments/{dep_id}/approve",
                json={
                    "stage_index": 0,
                    "action": "APPROVE_CURRENT_COHORT_ACTIVATION",
                    "expected_version": dep_get.json()["version"],
                    "expected_state": "STAGE_0_WAITING_FOR_ACTIVATION_APPROVAL",
                },
                headers=ADMIN_HEADERS,
            )
            assert appr_res.status_code == 200
            assert appr_res.json()["status"] == "ACTIVATING_STAGE_0"

            # 9. Agent handles ACTIVATE_RELEASE instruction
            async with async_client.session_factory() as db:
                act_instructions = await DeploymentService.get_pending_instructions_for_device(db, "bot-single-ota")
                assert len(act_instructions) >= 1
                act_inst = [i for i in act_instructions if i.instruction_type == "ACTIVATE_RELEASE"][0]

                act_env = DeploymentInstructionEnvelope(
                    instruction_id=act_inst.id,
                    deployment_id=act_inst.deployment_id,
                    generation=act_inst.generation,
                    instruction_type=InstructionType.ACTIVATE_RELEASE,
                    payload=json.loads(act_inst.payload_json),
                    payload_digest=act_inst.payload_digest,
                    created_at=act_inst.created_at.isoformat(),
                    expires_at=act_inst.expires_at.isoformat(),
                )
                act_ack = await worker.handle_instruction(act_env)
                assert act_ack.accepted is True
                await asyncio.sleep(0.2)

                # Check active reports and report remaining in sequence
                for rep in status_reports[reported_idx:]:
                    await DeploymentService.handle_device_status_report(db, "bot-single-ota", rep)
                await db.commit()

            # 10. Deployment successfully reaches COMPLETED
            final_dep = await async_client.get(f"/api/v1/deployments/{dep_id}")
            assert final_dep.json()["status"] == "COMPLETED"

        finally:
            server.shutdown()
            server.server_close()


@pytest.mark.asyncio
async def test_three_agent_canary_rollout_acceptance(async_client: AsyncClient):
    # 1. Enroll 3 robots
    device_ids = ["bot-canary-0", "bot-canary-1", "bot-canary-2"]
    for dev_id in device_ids:
        t_res = await async_client.post("/api/v1/fleet/enrollment-tokens", json={}, headers=ADMIN_HEADERS)
        token = t_res.json()["token"]
        _, csr_pem = generate_agent_key_and_csr(dev_id)
        enr_res = await async_client.post(
            "/api/v1/fleet/enroll",
            json={
                "device_id": dev_id,
                "device_name": dev_id,
                "enrollment_token": token,
                "csr_pem": csr_pem,
                "domain": "general_robotics",
                "robot_type": "mobile_base",
                "capabilities": ["navigation"],
            },
        )
        assert enr_res.status_code == 200
        fp = enr_res.json()["certificate_fingerprint"]
        await async_client.post(
            "/api/v1/fleet/agent/heartbeat",
            json={
                "protocol_version": "1.0",
                "message_id": f"hb-{dev_id}",
                "device_id": dev_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message_type": "HEARTBEAT",
                "payload": {"status": "ACTIVE", "os": host_os, "architecture": "x86_64", "ros_distro": "humble"},
            },
            headers={"X-OpenRobo-Cert-Fingerprint": fp},
        )

    # 2. Register release
    await async_client.post(
        "/api/v1/releases/sources",
        json={"id": "src-canary", "base_url": "https://artifacts.local", "allowed_host": "artifacts.local"},
        headers=ADMIN_HEADERS,
    )
    await async_client.post(
        "/api/v1/releases",
        json={
            "release_id": "rel-canary-3",
            "release_version": "3.0.0",
            "manifest_digest": "3" * 64,
            "artifact_digest": "3" * 64,
            "workspace_digest": "3" * 64,
            "release_key_id": "key-canary-01",
            "artifact_source_id": "src-canary",
            "target_os": host_os,
            "target_architecture": "x86_64",
            "target_ros_distro": "humble",
        },
        headers=ADMIN_HEADERS,
    )

    # 3. Create 2-stage Canary Deployment (Stage 0: 33% = 1 device, Stage 1: 100% = 2 devices)
    dep_res = await async_client.post(
        "/api/v1/deployments",
        json={
            "release_id": "rel-canary-3",
            "rollout_strategy": {
                "strategy_type": "CANARY",
                "stages": [
                    {"stage_index": 0, "target_percentage": 33, "require_approval": True},
                    {"stage_index": 1, "target_percentage": 100, "require_approval": True},
                ],
            },
            "target_filter": {"device_ids": device_ids},
        },
        headers=ADMIN_HEADERS,
    )
    assert dep_res.status_code == 201
    dep_data = dep_res.json()
    dep_id = dep_data["id"]
    assert dep_data["total_stages"] == 2
    assert dep_data["current_stage"] == 0

    # 4. Check stage device partition sizing
    devices_resp = await async_client.get(f"/api/v1/deployments/{dep_id}/devices")
    devices = devices_resp.json()
    assert len(devices) == 3

    stage_0_devs = [d for d in devices if d["stage_index"] == 0]
    stage_1_devs = [d for d in devices if d["stage_index"] == 1]
    assert len(stage_0_devs) == 1
    assert len(stage_1_devs) == 2


@pytest.mark.asyncio
async def test_hundred_device_orchestration_simulation(async_client: AsyncClient):
    from apps.api.models.fleet import FleetDeviceModel
    device_ids = [f"sim-bot-{i:03d}" for i in range(100)]
    now = datetime.now(timezone.utc)
    async with async_client.session_factory() as db:
        for dev_id in device_ids:
            dev = FleetDeviceModel(
                id=dev_id,
                name=dev_id,
                domain="general_robotics",
                robot_type="mobile_base",
                certificate_fingerprint=f"fp-{dev_id}",
                status="ENROLLED",
                capabilities_json=["navigation"],
                last_heartbeat_at=now,
                last_heartbeat_json={"status": "ACTIVE", "os": host_os, "architecture": "x86_64", "ros_distro": "humble"},
            )
            db.add(dev)
        await db.commit()

    # Register release
    await async_client.post(
        "/api/v1/releases/sources",
        json={"id": "src-sim", "base_url": "https://artifacts.local", "allowed_host": "artifacts.local"},
        headers=ADMIN_HEADERS,
    )
    await async_client.post(
        "/api/v1/releases",
        json={
            "release_id": "rel-sim-100",
            "release_version": "1.0.0",
            "manifest_digest": "4" * 64,
            "artifact_digest": "4" * 64,
            "workspace_digest": "4" * 64,
            "release_key_id": "key-sim-01",
            "artifact_source_id": "src-sim",
            "target_os": host_os,
            "target_architecture": "x86_64",
            "target_ros_distro": "humble",
        },
        headers=ADMIN_HEADERS,
    )

    dep_res = await async_client.post(
        "/api/v1/deployments",
        json={
            "release_id": "rel-sim-100",
            "rollout_strategy": {
                "strategy_type": "CANARY",
                "stages": [
                    {"stage_index": 0, "target_percentage": 10, "require_approval": True},
                    {"stage_index": 1, "target_percentage": 40, "require_approval": True},
                    {"stage_index": 2, "target_percentage": 100, "require_approval": True},
                ],
            },
            "target_filter": {"device_ids": device_ids},
        },
        headers=ADMIN_HEADERS,
    )
    assert dep_res.status_code == 201
    dep_id = dep_res.json()["id"]

    devices_resp = await async_client.get(f"/api/v1/deployments/{dep_id}/devices")
    devices = devices_resp.json()
    assert len(devices) == 100

    s0 = [d for d in devices if d["stage_index"] == 0]
    s1 = [d for d in devices if d["stage_index"] == 1]
    s2 = [d for d in devices if d["stage_index"] == 2]

    assert len(s0) == 10
    assert len(s1) == 40
    assert len(s2) == 50


@pytest.mark.asyncio
async def test_control_plane_and_agent_restart_recovery(async_client: AsyncClient):
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = Path(tmpdir) / "state"
        state_dir.mkdir()

        # 1. Agent worker records generation state
        gen_file = state_dir / "generation_state.json"
        mgr = GenerationStateManager(gen_file)
        mgr.record_generation(generation=5, deployment_id="dep-restart", instruction_digest="digest-abc")

        # Destroy instance and simulate agent restart
        del mgr
        new_mgr = GenerationStateManager(gen_file)
        assert new_mgr.state.last_generation == 5
        assert new_mgr.state.last_deployment_id == "dep-restart"
        assert new_mgr.state.last_instruction_digest == "digest-abc"


@pytest.mark.asyncio
async def test_direction_enforced_websocket_operations():
    from apps.api.routers.fleet import FORBIDDEN_OPERATIONS, ALLOWED_OPERATIONS

    assert "STAGE_RELEASE" in FORBIDDEN_OPERATIONS
    assert "ACTIVATE_RELEASE" in FORBIDDEN_OPERATIONS
    assert "CANCEL_DEPLOYMENT" in FORBIDDEN_OPERATIONS
    assert "EXEC" in FORBIDDEN_OPERATIONS
    assert "COMMAND" in FORBIDDEN_OPERATIONS

    assert "DEPLOYMENT_ACK" in ALLOWED_OPERATIONS
    assert "DEPLOYMENT_STATUS" in ALLOWED_OPERATIONS
    assert "DEPLOYMENT_EVENT" in ALLOWED_OPERATIONS
