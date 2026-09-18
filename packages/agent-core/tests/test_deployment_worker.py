import asyncio

# Unit tests for DeploymentWorker, atomic generation state persistence, replay defense, and execution.
import hashlib
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from openrobo_agent.deployment.artifact_client import ArtifactClient
from openrobo_agent.deployment.slots import ABSlotManager
from openrobo_agent.deployment.worker import (
    DeploymentWorker,
    GenerationStateCorruptedError,
    GenerationStateManager,
)
from openrobo_release.deployment_protocol import (
    CANONICAL_PROTOCOL_VERSION,
    DeploymentInstructionEnvelope,
    InstructionType,
)
from openrobo_release.trust_store import TrustedReleaseKeyStore


def test_generation_state_manager_and_corruption_fail_safe():
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "generation_state.json"
        mgr = GenerationStateManager(state_file)
        assert mgr.state.last_generation == 0

        mgr.record_generation(1, "dep-1", "digest-1")
        assert mgr.state.last_generation == 1
        assert mgr.state.last_deployment_id == "dep-1"

        # Reload
        mgr2 = GenerationStateManager(state_file)
        assert mgr2.state.last_generation == 1
        assert mgr2.state.last_instruction_digest == "digest-1"

        # Corrupt file
        state_file.write_text("NOT_JSON_DATA", encoding="utf-8")
        with pytest.raises(GenerationStateCorruptedError):
            GenerationStateManager(state_file)


@pytest.mark.asyncio
async def test_worker_generation_replay_protection():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        state_dir = base / "state"
        slots_dir = base / "slots"
        trust_dir = base / "trusted_keys"
        state_dir.mkdir()
        slots_dir.mkdir()
        trust_dir.mkdir()

        slot_mgr = ABSlotManager(deployment_root=slots_dir)
        key_store = TrustedReleaseKeyStore(trust_dir=trust_dir)
        art_client = ArtifactClient(downloads_dir=base / "downloads")

        worker = DeploymentWorker(
            device_id="dev-01",
            state_dir=state_dir,
            slot_manager=slot_mgr,
            key_store=key_store,
            artifact_client=art_client,
        )

        now = datetime.now(timezone.utc)
        created_at = (now - timedelta(seconds=10)).isoformat()
        expires_at = (now + timedelta(hours=1)).isoformat()

        payload_1 = {"deployment_id": "dep-5"}
        digest_1 = hashlib.sha256(json.dumps(payload_1, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

        # 1. Generation 5 -> Accepted
        env5 = DeploymentInstructionEnvelope(
            protocol_version=CANONICAL_PROTOCOL_VERSION,
            instruction_id="inst-5",
            deployment_id="dep-5",
            device_id="dev-01",
            generation=5,
            instruction_type=InstructionType.CANCEL_DEPLOYMENT,
            payload=payload_1,
            payload_digest=digest_1,
            created_at=created_at,
            expires_at=expires_at,
        )
        ack5 = await worker.handle_instruction(env5)
        assert ack5.accepted is True
        assert ack5.reason == "ACCEPTED"

        # 2. Generation 5 with same whole instruction -> IDEMPOTENT_REPLAY
        ack5_replay = await worker.handle_instruction(env5)
        assert ack5_replay.accepted is True
        assert ack5_replay.reason == "REPLAY_IDEMPOTENT"

        # 3. Generation 5 with different instruction_id / altered payload -> REPLAY_CONFLICT
        payload_alt = {"deployment_id": "dep-5-mutated"}
        digest_alt = hashlib.sha256(json.dumps(payload_alt, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        env5_conflict = DeploymentInstructionEnvelope(
            protocol_version=CANONICAL_PROTOCOL_VERSION,
            instruction_id="inst-5-diff",
            deployment_id="dep-5",
            device_id="dev-01",
            generation=5,
            instruction_type=InstructionType.CANCEL_DEPLOYMENT,
            payload=payload_alt,
            payload_digest=digest_alt,
            created_at=created_at,
            expires_at=expires_at,
        )
        ack5_conflict = await worker.handle_instruction(env5_conflict)
        assert ack5_conflict.accepted is False
        assert ack5_conflict.reason == "REPLAY_CONFLICT"

        # 4. Stale generation (2 < 5) -> STALE_GENERATION
        env_stale = DeploymentInstructionEnvelope(
            protocol_version=CANONICAL_PROTOCOL_VERSION,
            instruction_id="inst-2",
            deployment_id="dep-2",
            device_id="dev-01",
            generation=2,
            instruction_type=InstructionType.CANCEL_DEPLOYMENT,
            payload=payload_1,
            payload_digest=digest_1,
            created_at=created_at,
            expires_at=expires_at,
        )
        ack_stale = await worker.handle_instruction(env_stale)
        assert ack_stale.accepted is False
        assert ack_stale.reason == "STALE_GENERATION"

        # 5. Generation 6 -> Accepted
        payload_6 = {"deployment_id": "dep-6"}
        digest_6 = hashlib.sha256(json.dumps(payload_6, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        env6 = DeploymentInstructionEnvelope(
            protocol_version=CANONICAL_PROTOCOL_VERSION,
            instruction_id="inst-6",
            deployment_id="dep-6",
            device_id="dev-01",
            generation=6,
            instruction_type=InstructionType.CANCEL_DEPLOYMENT,
            payload=payload_6,
            payload_digest=digest_6,
            created_at=created_at,
            expires_at=expires_at,
        )
        ack6 = await worker.handle_instruction(env6)
        assert ack6.accepted is True
        assert ack6.reason == "ACCEPTED"
        assert worker.gen_manager.state.last_generation == 6


@pytest.mark.asyncio
async def test_worker_fail_closed_validations():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        state_dir = base / "state"
        slots_dir = base / "slots"
        trust_dir = base / "trusted_keys"
        state_dir.mkdir()
        slots_dir.mkdir()
        trust_dir.mkdir()

        slot_mgr = ABSlotManager(deployment_root=slots_dir)
        key_store = TrustedReleaseKeyStore(trust_dir=trust_dir)
        art_client = ArtifactClient(downloads_dir=base / "downloads")

        worker = DeploymentWorker(
            device_id="dev-01",
            state_dir=state_dir,
            slot_manager=slot_mgr,
            key_store=key_store,
            artifact_client=art_client,
        )

        now = datetime.now(timezone.utc)
        created_at = now.isoformat()
        expires_at = (now + timedelta(hours=1)).isoformat()
        payload = {"deployment_id": "dep-1"}
        payload_digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

        # 1. Wrong device_id
        env_wrong_dev = DeploymentInstructionEnvelope(
            protocol_version=CANONICAL_PROTOCOL_VERSION,
            instruction_id="inst-1",
            deployment_id="dep-1",
            device_id="dev-WRONG",
            generation=1,
            instruction_type=InstructionType.CANCEL_DEPLOYMENT,
            payload=payload,
            payload_digest=payload_digest,
            created_at=created_at,
            expires_at=expires_at,
        )
        ack = await worker.handle_instruction(env_wrong_dev)
        assert ack.accepted is False
        assert ack.reason == "DEVICE_MISMATCH"

        # 2. Unsupported protocol version
        env_bad_proto = DeploymentInstructionEnvelope(
            protocol_version="9.9.9",
            instruction_id="inst-2",
            deployment_id="dep-1",
            device_id="dev-01",
            generation=1,
            instruction_type=InstructionType.CANCEL_DEPLOYMENT,
            payload=payload,
            payload_digest=payload_digest,
            created_at=created_at,
            expires_at=expires_at,
        )
        ack = await worker.handle_instruction(env_bad_proto)
        assert ack.accepted is False
        assert ack.reason == "UNSUPPORTED_PROTOCOL_VERSION"

        # 3. Malformed created_at
        env_bad_created = DeploymentInstructionEnvelope(
            protocol_version=CANONICAL_PROTOCOL_VERSION,
            instruction_id="inst-3",
            deployment_id="dep-1",
            device_id="dev-01",
            generation=1,
            instruction_type=InstructionType.CANCEL_DEPLOYMENT,
            payload=payload,
            payload_digest=payload_digest,
            created_at="NOT_ISO_DATE",
            expires_at=expires_at,
        )
        ack = await worker.handle_instruction(env_bad_created)
        assert ack.accepted is False
        assert ack.reason == "MALFORMED_CREATED_AT"

        # 4. Future created_at beyond clock skew
        future_created = (now + timedelta(seconds=1000)).isoformat()
        env_future_created = DeploymentInstructionEnvelope(
            protocol_version=CANONICAL_PROTOCOL_VERSION,
            instruction_id="inst-4",
            deployment_id="dep-1",
            device_id="dev-01",
            generation=1,
            instruction_type=InstructionType.CANCEL_DEPLOYMENT,
            payload=payload,
            payload_digest=payload_digest,
            created_at=future_created,
            expires_at=(now + timedelta(hours=2)).isoformat(),
        )
        ack = await worker.handle_instruction(env_future_created)
        assert ack.accepted is False
        assert ack.reason == "CLOCK_SKEW_EXCEEDED"

        # 5. Expired instruction
        past_created = (now - timedelta(hours=2)).isoformat()
        past_expires = (now - timedelta(hours=1)).isoformat()
        env_expired = DeploymentInstructionEnvelope(
            protocol_version=CANONICAL_PROTOCOL_VERSION,
            instruction_id="inst-5",
            deployment_id="dep-1",
            device_id="dev-01",
            generation=1,
            instruction_type=InstructionType.CANCEL_DEPLOYMENT,
            payload=payload,
            payload_digest=payload_digest,
            created_at=past_created,
            expires_at=past_expires,
        )
        ack = await worker.handle_instruction(env_expired)
        assert ack.accepted is False
        assert ack.reason == "INSTRUCTION_EXPIRED"

        # 6. expires_at <= created_at
        env_bad_order = DeploymentInstructionEnvelope(
            protocol_version=CANONICAL_PROTOCOL_VERSION,
            instruction_id="inst-6",
            deployment_id="dep-1",
            device_id="dev-01",
            generation=1,
            instruction_type=InstructionType.CANCEL_DEPLOYMENT,
            payload=payload,
            payload_digest=payload_digest,
            created_at=now.isoformat(),
            expires_at=(now - timedelta(seconds=10)).isoformat(),
        )
        ack = await worker.handle_instruction(env_bad_order)
        assert ack.accepted is False
        assert ack.reason == "INVALID_EXPIRY_ORDERING"

        # 7. Tampered payload with old payload_digest
        env_tampered = DeploymentInstructionEnvelope(
            protocol_version=CANONICAL_PROTOCOL_VERSION,
            instruction_id="inst-7",
            deployment_id="dep-1",
            device_id="dev-01",
            generation=1,
            instruction_type=InstructionType.CANCEL_DEPLOYMENT,
            payload={"deployment_id": "dep-TAMPERED"},
            payload_digest=payload_digest,
            created_at=created_at,
            expires_at=expires_at,
        )
        ack = await worker.handle_instruction(env_tampered)
        assert ack.accepted is False
        assert ack.reason == "PAYLOAD_DIGEST_MISMATCH"

        # 8. Extra unknown payload fields (ConfigDict extra="forbid")
        extra_payload = {"deployment_id": "dep-1", "unauthorized_extra_field": "malicious"}
        extra_digest = hashlib.sha256(json.dumps(extra_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        env_extra = DeploymentInstructionEnvelope(
            protocol_version=CANONICAL_PROTOCOL_VERSION,
            instruction_id="inst-8",
            deployment_id="dep-1",
            device_id="dev-01",
            generation=1,
            instruction_type=InstructionType.CANCEL_DEPLOYMENT,
            payload=extra_payload,
            payload_digest=extra_digest,
            created_at=created_at,
            expires_at=expires_at,
        )
        ack = await worker.handle_instruction(env_extra)
        assert ack.accepted is False
        assert ack.reason == "INVALID_PAYLOAD_SCHEMA"


@pytest.mark.asyncio
async def test_worker_cancel_deployment_execution_no_type_error():
    """Prove CANCEL_DEPLOYMENT does not raise TypeError (current_slot argument defect fix)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        state_dir = base / "state"
        slots_dir = base / "slots"
        trust_dir = base / "trusted_keys"
        state_dir.mkdir()
        slots_dir.mkdir()
        trust_dir.mkdir()

        slot_mgr = ABSlotManager(deployment_root=slots_dir)
        key_store = TrustedReleaseKeyStore(trust_dir=trust_dir)
        art_client = ArtifactClient(downloads_dir=base / "downloads")

        emitted_reports = []

        async def callback(report):
            emitted_reports.append(report)

        worker = DeploymentWorker(
            device_id="dev-01",
            state_dir=state_dir,
            slot_manager=slot_mgr,
            key_store=key_store,
            artifact_client=art_client,
            status_callback=callback,
        )

        now = datetime.now(timezone.utc)
        payload = {"deployment_id": "dep-cancel-test"}
        payload_digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

        env = DeploymentInstructionEnvelope(
            protocol_version=CANONICAL_PROTOCOL_VERSION,
            instruction_id="inst-cancel-1",
            deployment_id="dep-cancel-test",
            device_id="dev-01",
            generation=1,
            instruction_type=InstructionType.CANCEL_DEPLOYMENT,
            payload=payload,
            payload_digest=payload_digest,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(hours=1)).isoformat(),
        )

        ack = await worker.handle_instruction(env)
        assert ack.accepted is True
        # Let async worker task complete
        await asyncio.sleep(0.1)

        # Check emitted reports
        assert any(r.state.value == "CANCELLED" for r in emitted_reports)
