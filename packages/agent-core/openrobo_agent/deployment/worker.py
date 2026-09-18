# Autonomous deployment execution worker, atomic generation persistence, and A/B staging/activation runner.

import asyncio
import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, Optional

from openrobo_release.deployment_protocol import (
    DeploymentAckEnvelope,
    DeploymentInstructionEnvelope,
    DeploymentStatusReport,
    DeviceDeploymentState,
    InstructionType,
)
from openrobo_release.models import ReleaseManifest
from openrobo_release.trust_store import TrustedReleaseKeyStore

from openrobo_agent.deployment.activation import activate_staged_slot
from openrobo_agent.deployment.artifact_client import ArtifactClient
from openrobo_agent.deployment.slots import ABSlotManager
from openrobo_agent.deployment.staging import stage_release_artifact

logger = logging.getLogger("openrobo.agent.worker")


class GenerationStateCorruptedError(RuntimeError):
    pass


@dataclass
class PersistedGenerationState:
    last_generation: int
    last_deployment_id: Optional[str]
    last_instruction_digest: Optional[str]
    updated_at: str


class GenerationStateManager:
    def __init__(self, state_file_path: Path):
        self.path = Path(state_file_path)
        self.state = self._load()

    def _load(self) -> PersistedGenerationState:
        if not self.path.exists():
            return PersistedGenerationState(
                last_generation=0,
                last_deployment_id=None,
                last_instruction_digest=None,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return PersistedGenerationState(
                last_generation=int(data["last_generation"]),
                last_deployment_id=data.get("last_deployment_id"),
                last_instruction_digest=data.get("last_instruction_digest"),
                updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            )
        except Exception as e:
            logger.error(f"Persisted generation state at {self.path} is corrupted: {e}")
            raise GenerationStateCorruptedError(f"Generation state file {self.path} is corrupt or unparseable. Fail-safe triggered.") from e

    def record_generation(self, generation: int, deployment_id: str, instruction_digest: str) -> None:
        self.state.last_generation = generation
        self.state.last_deployment_id = deployment_id
        self.state.last_instruction_digest = instruction_digest
        self.state.updated_at = datetime.now(timezone.utc).isoformat()

        self.path.parent.mkdir(parents=True, exist_ok=True)
        dir_name = str(self.path.parent)

        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
            temp_name = tf.name
            json.dump(asdict(self.state), tf, indent=2)
            tf.flush()
            os.fsync(tf.fileno())

        os.replace(temp_name, self.path)


class DeploymentWorker:
    def __init__(
        self,
        device_id: str,
        state_dir: Path,
        slot_manager: ABSlotManager,
        key_store: TrustedReleaseKeyStore,
        artifact_client: ArtifactClient,
        status_reporter: Optional[Callable[[DeploymentStatusReport], Coroutine[None, None, None]]] = None,
        artifact_base_urls: Optional[Dict[str, str]] = None,
        current_ros_distro: Optional[str] = None,
    ):
        self.device_id = device_id
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.slot_manager = slot_manager
        self.key_store = key_store
        self.artifact_client = artifact_client
        self.status_reporter = status_reporter
        self.artifact_base_urls = artifact_base_urls or {}
        self.current_ros_distro = current_ros_distro or os.environ.get("ROS_DISTRO")

        gen_file = self.state_dir / "generation_state.json"
        self.gen_manager = GenerationStateManager(gen_file)
        self.device_lock = asyncio.Lock()

    async def report_status(
        self,
        deployment_id: str,
        generation: int,
        state: DeviceDeploymentState,
        staged_slot: Optional[str] = None,
        active_slot: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        if not self.status_reporter:
            return

        report = DeploymentStatusReport(
            deployment_id=deployment_id,
            device_id=self.device_id,
            generation=generation,
            state=state,
            staged_slot=staged_slot,
            active_slot=active_slot,
            error_message=error_message,
        )
        try:
            await self.status_reporter(report)
        except Exception as e:
            logger.error(f"Failed to report deployment status: {e}")

    async def handle_instruction(
        self,
        envelope: DeploymentInstructionEnvelope,
    ) -> DeploymentAckEnvelope:
        last_gen = self.gen_manager.state.last_generation
        curr_gen = envelope.generation
        digest = envelope.payload_digest

        if curr_gen < last_gen:
            return DeploymentAckEnvelope(
                instruction_id=envelope.instruction_id,
                deployment_id=envelope.deployment_id,
                device_id=self.device_id,
                generation=curr_gen,
                accepted=False,
                reason="STALE_GENERATION",
            )

        if curr_gen == last_gen:
            if digest == self.gen_manager.state.last_instruction_digest:
                return DeploymentAckEnvelope(
                    instruction_id=envelope.instruction_id,
                    deployment_id=envelope.deployment_id,
                    device_id=self.device_id,
                    generation=curr_gen,
                    accepted=True,
                    reason="IDEMPOTENT_REPLAY",
                )
            else:
                return DeploymentAckEnvelope(
                    instruction_id=envelope.instruction_id,
                    deployment_id=envelope.deployment_id,
                    device_id=self.device_id,
                    generation=curr_gen,
                    accepted=False,
                    reason="REPLAY_CONFLICT",
                )

        self.gen_manager.record_generation(
            generation=curr_gen,
            deployment_id=envelope.deployment_id,
            instruction_digest=digest,
        )

        ack = DeploymentAckEnvelope(
            instruction_id=envelope.instruction_id,
            deployment_id=envelope.deployment_id,
            device_id=self.device_id,
            generation=curr_gen,
            accepted=True,
            reason="ACCEPTED",
        )

        asyncio.create_task(self._execute_instruction(envelope))
        return ack

    async def _execute_instruction(self, envelope: DeploymentInstructionEnvelope) -> None:
        async with self.device_lock:
            deployment_id = envelope.deployment_id
            generation = envelope.generation
            itype = envelope.instruction_type
            payload = envelope.payload

            try:
                if itype == InstructionType.STAGE_RELEASE:
                    await self._handle_stage_release(deployment_id, generation, payload)
                elif itype == InstructionType.ACTIVATE_RELEASE:
                    await self._handle_activate_release(deployment_id, generation, payload)
                elif itype == InstructionType.CANCEL_DEPLOYMENT:
                    await self._handle_cancel_deployment(deployment_id, generation, payload)
                else:
                    logger.warning(f"Unknown instruction type: {itype}")
            except Exception as e:
                logger.exception(f"Execution failed for instruction {itype.value}")
                await self.report_status(
                    deployment_id=deployment_id,
                    generation=generation,
                    state=DeviceDeploymentState.FAILED,
                    error_message=str(e),
                )

    async def _handle_stage_release(
        self,
        deployment_id: str,
        generation: int,
        payload: Dict[str, Any],
    ) -> None:
        await self.report_status(deployment_id, generation, DeviceDeploymentState.FETCHING)

        release_id = payload["release_id"]
        expected_manifest_digest = payload["manifest_digest"]
        expected_artifact_digest = payload["artifact_digest"]
        expected_key_id = payload["release_key_id"]
        source_id = payload["artifact_source_id"]

        base_url = self.artifact_base_urls.get(source_id, f"http://127.0.0.1:8000/artifacts/{source_id}")
        manifest_url = f"{base_url.rstrip('/')}/{release_id}/manifest.json"
        artifact_url = f"{base_url.rstrip('/')}/{release_id}/artifact.tar.gz"

        # 1. Fetch manifest
        manifest_bytes = await self.artifact_client.fetch_manifest_bytes(
            url=manifest_url,
            expected_manifest_digest=expected_manifest_digest,
        )

        # 2. Fetch artifact
        artifact_path = await self.artifact_client.download_and_verify(
            url=artifact_url,
            expected_digest=expected_artifact_digest,
            deployment_id=deployment_id,
        )

        # 3. Fetch signature
        sig_url = f"{base_url.rstrip('/')}/{release_id}/signature.sig"
        sig_text = await self.artifact_client.fetch_signature_text(url=sig_url)

        await self.report_status(deployment_id, generation, DeviceDeploymentState.VERIFYING)

        # 4. Parse manifest
        manifest = ReleaseManifest.model_validate_json(manifest_bytes)
        if manifest.release_id != release_id:
            raise ValueError(f"Manifest release_id '{manifest.release_id}' mismatch with expected '{release_id}'")
        if manifest.artifact_digest.lower() != expected_artifact_digest.lower():
            raise ValueError(f"Manifest artifact digest mismatch with expected '{expected_artifact_digest}'")
        if manifest.release_key_id != expected_key_id:
            raise ValueError(f"Manifest key_id '{manifest.release_key_id}' mismatch with expected '{expected_key_id}'")

        # 5. Save manifest and signature files for staging workflow
        dep_dir = self.state_dir / "staging_evidence" / deployment_id
        dep_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = dep_dir / f"{release_id}.manifest.json"
        sig_path = dep_dir / f"{release_id}.sig"

        manifest_path.write_bytes(manifest_bytes)
        sig_path.write_text(sig_text, encoding="utf-8")

        await self.report_status(deployment_id, generation, DeviceDeploymentState.STAGING)

        # 6. Extract and stage into inactive slot
        success, msg = stage_release_artifact(
            manager=self.slot_manager,
            archive_path=artifact_path,
            manifest_path=manifest_path,
            signature_path=sig_path,
            trust_store=self.key_store,
            current_ros_distro=self.current_ros_distro,
        )

        if not success:
            raise ValueError(f"Staging release artifact failed: {msg}")

        # The staged slot is the slot that just transitioned to VERIFIED
        staged_slot = "slot-b" if self.slot_manager.get_active_slot_id() == "slot-a" else "slot-a"

        await self.report_status(
            deployment_id=deployment_id,
            generation=generation,
            state=DeviceDeploymentState.STAGED,
            staged_slot=staged_slot,
        )

    async def _handle_activate_release(
        self,
        deployment_id: str,
        generation: int,
        payload: Dict[str, Any],
    ) -> None:
        await self.report_status(deployment_id, generation, DeviceDeploymentState.ACTIVATING)

        target_slot = payload.get("target_slot")
        if target_slot and not target_slot.startswith("slot-"):
            target_slot = f"slot-{target_slot.lower()}"

        success, msg = activate_staged_slot(
            manager=self.slot_manager,
            slot_id=target_slot,
        )

        if not success:
            raise ValueError(f"Activation failed: {msg}")

        active_slot = self.slot_manager.get_active_slot_id()

        await self.report_status(
            deployment_id=deployment_id,
            generation=generation,
            state=DeviceDeploymentState.ACTIVE,
            active_slot=active_slot,
        )

    async def _handle_cancel_deployment(
        self,
        deployment_id: str,
        generation: int,
        payload: Dict[str, Any],
    ) -> None:
        await self.report_status(
            deployment_id=deployment_id,
            generation=generation,
            state=DeviceDeploymentState.CANCELLED,
        )
