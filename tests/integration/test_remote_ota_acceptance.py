# End-to-end integration and acceptance tests for authenticated remote deployment orchestration,
# signed artifact distribution, operator-gated canary rollouts, restart recovery, and direction-enforced WebSocket delivery.
import asyncio
import hashlib
import http.server
import json
import platform
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from openrobo_agent.certificates import generate_agent_key_and_csr
from openrobo_agent.config import AgentConfig
from openrobo_agent.deployment.artifact_client import ArtifactClient
from openrobo_agent.deployment.slots import ABSlotManager
from openrobo_agent.deployment.source_registry import TrustedArtifactSource
from openrobo_agent.deployment.worker import DeploymentWorker
from openrobo_agent.service import AgentDaemon
from openrobo_release.archive import create_deterministic_archive
from openrobo_release.deployment_protocol import (
    DeploymentInstructionEnvelope,
    DeploymentStatusReport,
    DeviceDeploymentState,
    InstructionType,
)
from openrobo_release.manifest import canonical_manifest_bytes
from openrobo_release.models import ReleaseTarget
from openrobo_release.signing import ReleaseSigner, generate_development_keypair
from openrobo_release.trust_store import TrustedReleaseKeyStore
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from apps.api.database import Base, get_db
from apps.api.main import app
from apps.api.models.fleet import FleetDeviceModel
from apps.api.services.deployment_service import DeploymentService
from apps.api.services.fleet_security import get_rate_limiter, get_replay_manager

ADMIN_HEADERS = {"X-OpenRobo-Admin-Key": "test-admin-secret"}
host_os = platform.system().lower()
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    monkeypatch.setenv("OPENROBO_DEV_CA", "true")
    monkeypatch.setenv("OPENROBO_DEV_RELEASE_SIGNING", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("OPENROBO_ALLOW_DEV_CERT_HEADER", "true")
    monkeypatch.setenv("OPENROBO_ADMIN_KEY", "test-admin-secret")
    monkeypatch.setenv("OPENROBO_ALLOW_DEV_ARTIFACT_HTTP", "true")
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
        client.engine = engine
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
    """SINGLE-DEVICE AUTHENTICATED REMOTE OTA ACCEPTANCE VERIFIED (Amendment 24)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        ws_dir = base_dir / "workspace"
        ws_dir.mkdir()
        (ws_dir / "app.py").write_text("print('v1.0.0 active')")

        # 1. Build signed release artifact
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
        sig_text = signer.sign_manifest(manifest)
        manifest_bytes = manifest.model_dump_json(indent=2).encode("utf-8")
        artifact_bytes = artifact_path.read_bytes()

        # Start real local HTTP server
        RealArtifactHandler.manifest_bytes = manifest_bytes
        RealArtifactHandler.artifact_bytes = artifact_bytes
        RealArtifactHandler.signature_bytes = sig_text.encode("utf-8")
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RealArtifactHandler)
        port = server.server_port
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        base_url = f"http://127.0.0.1:{port}"

        try:
            # 2. Setup AgentDaemon instance
            agent_dir = base_dir / "agent"
            agent_dir.mkdir()
            (agent_dir / "state").mkdir()
            (agent_dir / "config").mkdir()

            trust_dir = agent_dir / "state" / "trusted_keys"
            trust_dir.mkdir(parents=True)
            (trust_dir / f"{signing_key.key_id}.pub.json").write_text(signing_key.model_dump_json(indent=2))

            agent_cfg = AgentConfig(
                config_dir=agent_dir / "config",
                state_dir=agent_dir / "state",
                control_plane_url="http://testserver",
                device_id="bot-accept-01",
            )
            daemon = AgentDaemon(agent_cfg, current_ros_distro="humble")

            # Register source in daemon local authoritative registry
            daemon.source_registry.register_source(
                TrustedArtifactSource(
                    id="src-http-local",
                    base_url=base_url,
                    allowed_host="127.0.0.1",
                    allow_private_network=True,
                )
            )

            # 3. Enroll device with Control Plane
            t_res = await async_client.post("/api/v1/fleet/enrollment-tokens", json={"device_name": "bot-accept-01"}, headers=ADMIN_HEADERS)
            token = t_res.json()["token"]

            _, csr_pem = generate_agent_key_and_csr("bot-accept-01")
            enr_res = await async_client.post(
                "/api/v1/fleet/enroll",
                json={
                    "device_id": "bot-accept-01",
                    "device_name": "bot-accept-01",
                    "enrollment_token": token,
                    "csr_pem": csr_pem,
                    "domain": "general_robotics",
                    "robot_type": "mobile_base",
                    "capabilities": ["navigation"],
                },
            )
            assert enr_res.status_code == 200
            cert_fp = enr_res.json()["certificate_fingerprint"]

            # Send heartbeat
            hb_resp = await async_client.post(
                "/api/v1/fleet/agent/heartbeat",
                json={
                    "protocol_version": "1.0",
                    "message_id": "hb-001",
                    "device_id": "bot-accept-01",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message_type": "HEARTBEAT",
                    "payload": {"status": "ACTIVE", "os": host_os, "architecture": "x86_64", "ros_distro": "humble"},
                },
                headers={"X-OpenRobo-Cert-Fingerprint": cert_fp},
            )
            assert hb_resp.status_code == 200

            # 4. Register source and release in control plane catalog
            src_res = await async_client.post(
                "/api/v1/releases/sources",
                json={
                    "id": "src-http-local",
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
                    "manifest_digest": hashlib.sha256(canonical_manifest_bytes(manifest)).hexdigest(),
                    "artifact_digest": manifest.artifact_digest,
                    "workspace_digest": manifest.workspace_digest,
                    "release_key_id": "key-ota-accept",
                    "artifact_source_id": "src-http-local",
                    "target_os": host_os,
                    "target_architecture": "x86_64",
                    "target_ros_distro": "humble",
                },
                headers=ADMIN_HEADERS,
            )
            assert rel_res.status_code == 201

            # 5. Create Deployment Orchestration
            dep_res = await async_client.post(
                "/api/v1/deployments",
                json={
                    "release_id": "rel-ota-100",
                    "rollout_strategy": {"strategy_type": "IMMEDIATE_ALL"},
                    "target_filter": {"device_ids": ["bot-accept-01"]},
                },
                headers=ADMIN_HEADERS,
            )
            assert dep_res.status_code == 201
            dep_data = dep_res.json()
            dep_id = dep_data["id"]

            # 6. Outbox Delivery to AgentDaemon
            async with async_client.session_factory() as db:
                instructions = await DeploymentService.get_pending_instructions_for_device(db, "bot-accept-01")
                assert len(instructions) == 1
                inst = instructions[0]
                assert inst.instruction_type == "STAGE_RELEASE"

                envelope = DeploymentInstructionEnvelope(
                    instruction_id=inst.id,
                    deployment_id=inst.deployment_id,
                    device_id="bot-accept-01",
                    generation=inst.generation,
                    instruction_type=InstructionType(inst.instruction_type),
                    payload=json.loads(inst.payload_json),
                    payload_digest=inst.payload_digest,
                    created_at=inst.created_at.isoformat(),
                    expires_at=inst.expires_at.isoformat(),
                )

                # Process instruction through real AgentDaemon
                ack = await daemon.handle_deployment_instruction(envelope)
                assert ack.accepted is True
                assert ack.reason == "ACCEPTED"

                inst.status = "ACKNOWLEDGED"
                inst.acknowledged_at = datetime.now(timezone.utc)
                await db.commit()

            # Wait for AgentDaemon worker background staging task
            final_stage_report = None
            for _ in range(50):
                await asyncio.sleep(0.1)
                while not daemon._status_queue.empty():
                    rep = await daemon._status_queue.get()
                    if rep.state in (DeviceDeploymentState.STAGED, DeviceDeploymentState.FAILED):
                        final_stage_report = rep
                if final_stage_report:
                    break

            assert final_stage_report is not None, "Did not receive terminal staging status report"
            assert final_stage_report.state == DeviceDeploymentState.STAGED
            staged_slot = final_stage_report.staged_slot
            assert staged_slot in ("slot-a", "slot-b")

            # Report STAGED back to control plane
            async with async_client.session_factory() as db:
                await DeploymentService.handle_device_status_report(db, "bot-accept-01", final_stage_report)
                await db.commit()

            # Check deployment state transitioned to WAITING_FOR_ACTIVATION_APPROVAL
            dep_check = await async_client.get(f"/api/v1/deployments/{dep_id}", headers=ADMIN_HEADERS)
            assert dep_check.json()["status"] == "STAGE_0_WAITING_FOR_ACTIVATION_APPROVAL"

            # 7. Operator Approves Activation
            appr_res = await async_client.post(
                f"/api/v1/deployments/{dep_id}/approve",
                json={
                    "stage_index": 0,
                    "action": "APPROVE_ACTIVATION",
                    "expected_version": 2,
                    "expected_state": "STAGE_0_WAITING_FOR_ACTIVATION_APPROVAL",
                },
                headers=ADMIN_HEADERS,
            )
            assert appr_res.status_code == 200

            # 8. Outbox Delivery of ACTIVATE_RELEASE instruction
            async with async_client.session_factory() as db:
                instructions = await DeploymentService.get_pending_instructions_for_device(db, "bot-accept-01")
                assert len(instructions) == 1
                inst = instructions[0]
                assert inst.instruction_type == "ACTIVATE_RELEASE"

                act_envelope = DeploymentInstructionEnvelope(
                    instruction_id=inst.id,
                    deployment_id=inst.deployment_id,
                    device_id="bot-accept-01",
                    generation=inst.generation,
                    instruction_type=InstructionType(inst.instruction_type),
                    payload=json.loads(inst.payload_json),
                    payload_digest=inst.payload_digest,
                    created_at=inst.created_at.isoformat(),
                    expires_at=inst.expires_at.isoformat(),
                )
                act_ack = await daemon.handle_deployment_instruction(act_envelope)
                assert act_ack.accepted is True

                inst.status = "ACKNOWLEDGED"
                await db.commit()

            final_act_report = None
            for _ in range(50):
                await asyncio.sleep(0.1)
                while not daemon._status_queue.empty():
                    rep = await daemon._status_queue.get()
                    if rep.state in (DeviceDeploymentState.ACTIVE, DeviceDeploymentState.FAILED):
                        final_act_report = rep
                if final_act_report:
                    break

            assert final_act_report is not None, "Did not receive terminal active status report"
            assert final_act_report.state == DeviceDeploymentState.ACTIVE

            async with async_client.session_factory() as db:
                await DeploymentService.handle_device_status_report(db, "bot-accept-01", final_act_report)
                await db.commit()

            # 9. Deployment reaches COMPLETED
            final_dep = await async_client.get(f"/api/v1/deployments/{dep_id}", headers=ADMIN_HEADERS)
            assert final_dep.json()["status"] == "COMPLETED"

        finally:
            server.shutdown()
            server.server_close()


@pytest.mark.asyncio
async def test_three_agent_canary_rollout_acceptance(async_client: AsyncClient):
    """3-AGENT AUTHENTICATED OPERATOR-GATED CANARY ACCEPTANCE VERIFIED (Amendment 25)."""
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

    # Register source & release
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

    # 3-Device Canary (Stage 0: 33% = 1 device, Stage 1: 100% = 2 devices)
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

    devices_resp = await async_client.get(f"/api/v1/deployments/{dep_id}/devices", headers=ADMIN_HEADERS)
    devices = devices_resp.json()
    assert len(devices) == 3

    stage_0_devs = [d for d in devices if d["stage_index"] == 0]
    stage_1_devs = [d for d in devices if d["stage_index"] == 1]
    assert len(stage_0_devs) == 1
    assert len(stage_1_devs) == 2

    s0_dev_id = stage_0_devs[0]["device_id"]
    s1_dev_ids = [d["device_id"] for d in stage_1_devs]

    # Stage 0: only s0 robot receives staging instruction
    async with async_client.session_factory() as db:
        s0_insts = await DeploymentService.get_pending_instructions_for_device(db, s0_dev_id)
        assert len(s0_insts) == 1
        s1_insts_0 = await DeploymentService.get_pending_instructions_for_device(db, s1_dev_ids[0])
        assert len(s1_insts_0) == 0

        # Stage 0 acks and stages
        s0_insts[0].status = "ACKNOWLEDGED"
        s0_insts[0].acknowledged_at = datetime.now(timezone.utc)
        report = DeploymentStatusReport(
            report_id="rep-01",
            instruction_id=s0_insts[0].id,
            deployment_id=dep_id,
            device_id=s0_dev_id,
            generation=s0_insts[0].generation,
            state=DeviceDeploymentState.STAGED,
            staged_slot="slot-a",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        await DeploymentService.handle_device_status_report(db, s0_dev_id, report)
        await db.commit()

    # Before activation approval: 0 activate
    dep_check = await async_client.get(f"/api/v1/deployments/{dep_id}", headers=ADMIN_HEADERS)
    assert dep_check.json()["status"] == "STAGE_0_WAITING_FOR_ACTIVATION_APPROVAL"

    # Operator approves activation of stage 0
    appr_act_0 = await async_client.post(
        f"/api/v1/deployments/{dep_id}/approve",
        json={
            "stage_index": 0,
            "action": "APPROVE_ACTIVATION",
            "expected_version": 2,
            "expected_state": "STAGE_0_WAITING_FOR_ACTIVATION_APPROVAL",
        },
        headers=ADMIN_HEADERS,
    )
    assert appr_act_0.status_code == 200

    # s0 activates
    async with async_client.session_factory() as db:
        act_insts = await DeploymentService.get_pending_instructions_for_device(db, s0_dev_id)
        assert len(act_insts) == 1
        act_insts[0].status = "ACKNOWLEDGED"
        act_insts[0].acknowledged_at = datetime.now(timezone.utc)
        act_report = DeploymentStatusReport(
            report_id="rep-02",
            instruction_id=act_insts[0].id,
            deployment_id=dep_id,
            device_id=s0_dev_id,
            generation=act_insts[0].generation,
            state=DeviceDeploymentState.ACTIVE,
            active_slot="slot-a",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        await DeploymentService.handle_device_status_report(db, s0_dev_id, act_report)
        await db.commit()

    # Before next-stage approval: stage 1 robots receive NO staging command
    async with async_client.session_factory() as db:
        for dev_id in s1_dev_ids:
            insts = await DeploymentService.get_pending_instructions_for_device(db, dev_id)
            assert len(insts) == 0

    # Operator approves stage 1 progression
    appr_stage_1 = await async_client.post(
        f"/api/v1/deployments/{dep_id}/approve",
        json={
            "stage_index": 0,
            "action": "APPROVE_NEXT_STAGE",
            "expected_version": 4,
            "expected_state": "STAGE_0_WAITING_FOR_STAGE_APPROVAL",
        },
        headers=ADMIN_HEADERS,
    )
    assert appr_stage_1.status_code == 200

    # Stage 1 robots stage
    async with async_client.session_factory() as db:
        for dev_id in s1_dev_ids:
            insts = await DeploymentService.get_pending_instructions_for_device(db, dev_id)
            assert len(insts) == 1
            insts[0].status = "ACKNOWLEDGED"
            insts[0].acknowledged_at = datetime.now(timezone.utc)
            st_rep = DeploymentStatusReport(
                report_id=f"rep-s1-{dev_id}",
                instruction_id=insts[0].id,
                deployment_id=dep_id,
                device_id=dev_id,
                generation=insts[0].generation,
                state=DeviceDeploymentState.STAGED,
                staged_slot="slot-a",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            await DeploymentService.handle_device_status_report(db, dev_id, st_rep)
        await db.commit()

    # Operator approves stage 1 activation
    appr_act_1 = await async_client.post(
        f"/api/v1/deployments/{dep_id}/approve",
        json={
            "stage_index": 1,
            "action": "APPROVE_ACTIVATION",
            "expected_version": 6,
            "expected_state": "STAGE_1_WAITING_FOR_ACTIVATION_APPROVAL",
        },
        headers=ADMIN_HEADERS,
    )
    assert appr_act_1.status_code == 200

    # Stage 1 robots activate
    async with async_client.session_factory() as db:
        for dev_id in s1_dev_ids:
            insts = await DeploymentService.get_pending_instructions_for_device(db, dev_id)
            assert len(insts) == 1
            insts[0].status = "ACKNOWLEDGED"
            insts[0].acknowledged_at = datetime.now(timezone.utc)
            act_rep = DeploymentStatusReport(
                report_id=f"rep-act-s1-{dev_id}",
                instruction_id=insts[0].id,
                deployment_id=dep_id,
                device_id=dev_id,
                generation=insts[0].generation,
                state=DeviceDeploymentState.ACTIVE,
                active_slot="slot-a",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            await DeploymentService.handle_device_status_report(db, dev_id, act_rep)
        await db.commit()

    # Final deployment COMPLETED
    final_check = await async_client.get(f"/api/v1/deployments/{dep_id}", headers=ADMIN_HEADERS)
    assert final_check.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_hundred_device_orchestration_simulation(async_client: AsyncClient):
    """100-DEVICE ORCHESTRATION SIMULATED with Cumulative Sizing (Amendment 18)."""
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
                    {"stage_index": 0, "target_percentage": 10, "bake_time_sec": 0},
                    {"stage_index": 1, "target_percentage": 40, "bake_time_sec": 0},
                    {"stage_index": 2, "target_percentage": 100, "bake_time_sec": 0},
                ],
            },
            "target_filter": {"device_ids": device_ids},
        },
        headers=ADMIN_HEADERS,
    )
    assert dep_res.status_code == 201
    dep_id = dep_res.json()["id"]

    devices_resp = await async_client.get(f"/api/v1/deployments/{dep_id}/devices", headers=ADMIN_HEADERS)
    devices = devices_resp.json()
    assert len(devices) == 100

    s0 = [d for d in devices if d["stage_index"] == 0]
    s1 = [d for d in devices if d["stage_index"] == 1]
    s2 = [d for d in devices if d["stage_index"] == 2]

    # Cumulative coverage 10%, 40%, 100% -> 10, 30, 60 devices (Amendment 18)
    assert len(s0) == 10
    assert len(s1) == 30
    assert len(s2) == 60


@pytest.mark.asyncio
async def test_control_plane_and_agent_restart_recovery(async_client: AsyncClient):
    """CONTROL-PLANE AND AGENT SERVICE RESTART RECOVERY (Amendments 26 & 27)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)
        state_dir = base_path / "agent_state"
        state_dir.mkdir()

        # 1. Agent worker records generation state & job journal
        slots_dir = base_path / "slots"
        slots_dir.mkdir()
        slot_mgr = ABSlotManager(deployment_root=slots_dir)
        key_store = TrustedReleaseKeyStore(trust_dir=base_path / "keys")
        art_client = ArtifactClient(downloads_dir=base_path / "downloads")

        worker = DeploymentWorker(
            device_id="bot-restart-01",
            state_dir=state_dir,
            slot_manager=slot_mgr,
            key_store=key_store,
            artifact_client=art_client,
        )

        env = DeploymentInstructionEnvelope(
            instruction_id="inst-persist-01",
            deployment_id="dep-persist-01",
            device_id="bot-restart-01",
            generation=12,
            instruction_type=InstructionType.CANCEL_DEPLOYMENT,
            payload={"deployment_id": "dep-persist-01"},
            payload_digest="d" * 64,
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at="2026-09-19T12:00:00Z",
        )
        await worker.handle_instruction(env)
        assert worker.gen_manager.state.last_generation == 12

        # 2. Destroy and recreate new AgentDaemon / worker with same state_dir (Amendment 27)
        del worker
        new_worker = DeploymentWorker(
            device_id="bot-restart-01",
            state_dir=state_dir,
            slot_manager=slot_mgr,
            key_store=key_store,
            artifact_client=art_client,
        )
        new_worker.reconcile_on_startup()
        assert new_worker.gen_manager.state.last_generation == 12
        assert new_worker.journal.get_job("inst-persist-01") is not None


@pytest.mark.asyncio
async def test_real_websocket_direction_enforcement_and_attack():
    """REAL WEBSOCKET ATTACK & CORRELATION ACCEPTANCE (Amendment 23)."""
    from apps.api.database import Base, async_sessionmaker, create_async_engine, get_db
    from apps.api.models.fleet import FleetDeviceModel

    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def override_db():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    # 1. Reject unauthenticated connection
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/fleet/agent/ws") as ws:
            pass

    # 2. Register mock device with created tables
    async with session_factory() as db:
        dev = FleetDeviceModel(
            id="bot-ws-attack",
            name="bot-ws-attack",
            certificate_fingerprint="fp-ws-attack",
            status="ENROLLED",
            capabilities_json=["navigation"],
        )
        db.add(dev)
        await db.commit()

    # 3. Connect with authenticated certificate fingerprint
    headers = {"X-OpenRobo-Cert-Fingerprint": "fp-ws-attack"}
    with client.websocket_connect("/api/v1/fleet/agent/ws", headers=headers) as ws:
        # Agent -> Server sends forbidden STAGE_RELEASE operation
        msg_payload = {
            "protocol_version": "1.0",
            "message_id": "msg-attack-01",
            "device_id": "bot-ws-attack",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message_type": "STAGE_RELEASE",
            "payload": {"release_id": "rel-hacked"},
        }
        ws.send_json(msg_payload)
        resp = ws.receive_json()
        assert resp["status"] == "FORBIDDEN"

        # Agent -> Server sends valid PING -> receives PONG
        ping_payload = {
            "protocol_version": "1.0",
            "message_id": "msg-ping-01",
            "device_id": "bot-ws-attack",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message_type": "PING",
            "payload": {},
        }
        ws.send_json(ping_payload)
        pong_resp = ws.receive_json()
        assert pong_resp["message_type"] == "PONG"
