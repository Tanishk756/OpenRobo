# Unit tests for DeploymentWorker, atomic generation state persistence, replay defense, and execution.

import hashlib
import json
import tempfile
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

        payload_1 = {
            "release_id": "rel-1",
            "manifest_digest": "a" * 64,
            "artifact_digest": "b" * 64,
            "workspace_digest": "c" * 64,
            "release_key_id": "key-01",
            "artifact_source_id": "src-1",
        }
        digest_1 = hashlib.sha256(json.dumps(payload_1, sort_keys=True).encode("utf-8")).hexdigest()

        # 1. Generation 5 -> Accepted
        env5 = DeploymentInstructionEnvelope(
            instruction_id="inst-5",
            deployment_id="dep-5",
            generation=5,
            instruction_type=InstructionType.CANCEL_DEPLOYMENT,
            payload=payload_1,
            payload_digest=digest_1,
            created_at="2026-09-18T12:00:00Z",
            expires_at="2026-09-19T12:00:00Z",
        )
        ack5 = await worker.handle_instruction(env5)
        assert ack5.accepted is True
        assert ack5.reason == "ACCEPTED"

        # 2. Generation 5 with same digest -> IDEMPOTENT_REPLAY
        ack5_replay = await worker.handle_instruction(env5)
        assert ack5_replay.accepted is True
        assert ack5_replay.reason == "IDEMPOTENT_REPLAY"

        # 3. Generation 5 with different digest -> REPLAY_CONFLICT
        env5_conflict = DeploymentInstructionEnvelope(
            instruction_id="inst-5-diff",
            deployment_id="dep-5",
            generation=5,
            instruction_type=InstructionType.CANCEL_DEPLOYMENT,
            payload={"release_id": "rel-MUTATED"},
            payload_digest="f" * 64,
            created_at="2026-09-18T12:00:00Z",
            expires_at="2026-09-19T12:00:00Z",
        )
        ack5_conflict = await worker.handle_instruction(env5_conflict)
        assert ack5_conflict.accepted is False
        assert ack5_conflict.reason == "REPLAY_CONFLICT"

        # 4. Stale generation (2 < 5) -> STALE_GENERATION
        env_stale = DeploymentInstructionEnvelope(
            instruction_id="inst-2",
            deployment_id="dep-2",
            generation=2,
            instruction_type=InstructionType.CANCEL_DEPLOYMENT,
            payload=payload_1,
            payload_digest=digest_1,
            created_at="2026-09-18T12:00:00Z",
            expires_at="2026-09-19T12:00:00Z",
        )
        ack_stale = await worker.handle_instruction(env_stale)
        assert ack_stale.accepted is False
        assert ack_stale.reason == "STALE_GENERATION"

        # 5. Generation 6 -> Accepted
        env6 = DeploymentInstructionEnvelope(
            instruction_id="inst-6",
            deployment_id="dep-6",
            generation=6,
            instruction_type=InstructionType.CANCEL_DEPLOYMENT,
            payload={"target_slot": "B"},
            payload_digest="b" * 64,
            created_at="2026-09-18T12:00:00Z",
            expires_at="2026-09-19T12:00:00Z",
        )
        ack6 = await worker.handle_instruction(env6)
        assert ack6.accepted is True
        assert ack6.reason == "ACCEPTED"
        assert worker.gen_manager.state.last_generation == 6
