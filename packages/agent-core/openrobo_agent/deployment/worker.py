# Autonomous deployment execution worker, atomic generation persistence, durable job journal, and A/B staging/activation runner.

import asyncio
import json
import logging
import os
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
    canonical_instruction_digest,
)
from openrobo_release.trust_store import TrustedReleaseKeyStore

from openrobo_agent.deployment.activation import activate_staged_slot
from openrobo_agent.deployment.artifact_client import ArtifactClient
from openrobo_agent.deployment.models import SlotState
from openrobo_agent.deployment.slots import ABSlotManager
from openrobo_agent.deployment.source_registry import TrustedArtifactSourceRegistry
from openrobo_agent.deployment.staging import stage_release_artifact

logger = logging.getLogger("openrobo.agent.worker")


class DeploymentError(Exception):
    pass


class GenerationStateCorruptedError(Exception):
    """Raised when persisted generation state cannot be safely parsed."""

    pass


@dataclass
class GenerationState:
    last_generation: int = 0
    last_deployment_id: Optional[str] = None
    last_instruction_digest: Optional[str] = None
    updated_at: Optional[str] = None


PersistedGenerationState = GenerationState


class GenerationStateManager:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.state = self._load()

    def _load(self) -> GenerationState:
        if not self.path.exists():
            return GenerationState()
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return GenerationState(
                last_generation=int(data.get("last_generation", 0)),
                last_deployment_id=data.get("last_deployment_id"),
                last_instruction_digest=data.get("last_instruction_digest"),
                updated_at=data.get("updated_at"),
            )
        except Exception as e:
            logger.error("Failed to parse generation state from %s: %s", self.path, e)
            raise GenerationStateCorruptedError(f"Corrupted generation state: {e}") from e

    def record_generation(self, generation: int, deployment_id: str, instruction_digest: str) -> None:
        self.state.last_generation = generation
        self.state.last_deployment_id = deployment_id
        self.state.last_instruction_digest = instruction_digest
        self.state.updated_at = datetime.now(timezone.utc).isoformat()

        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(asdict(self.state), f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        temp_file.replace(self.path)


@dataclass
class JournaledJob:
    instruction_id: str
    deployment_id: str
    generation: int
    instruction_type: str
    payload: Dict[str, Any]
    full_instruction_digest: str
    status: str  # "ACCEPTED", "EXECUTING", "COMPLETED", "FAILED", "CANCELLED"
    created_at: str
    updated_at: str
    error_message: Optional[str] = None
    staged_slot: Optional[str] = None
    active_slot: Optional[str] = None


class AgentJobJournal:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.jobs: Dict[str, JournaledJob] = self._load()

    def _load(self) -> Dict[str, JournaledJob]:
        if not self.path.exists():
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return {k: JournaledJob(**v) for k, v in raw.items()}
        except Exception as e:
            logger.error("Failed to load job journal from %s: %s", self.path, e)
            return {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            raw = {k: asdict(v) for k, v in self.jobs.items()}
            json.dump(raw, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        temp_file.replace(self.path)

    def record_job(self, job: JournaledJob) -> None:
        self.jobs[job.instruction_id] = job
        self._save()

    def update_job_status(
        self,
        instruction_id: str,
        status: str,
        error_message: Optional[str] = None,
        staged_slot: Optional[str] = None,
        active_slot: Optional[str] = None,
    ) -> None:
        if instruction_id in self.jobs:
            job = self.jobs[instruction_id]
            job.status = status
            job.updated_at = datetime.now(timezone.utc).isoformat()
            if error_message:
                job.error_message = error_message
            if staged_slot:
                job.staged_slot = staged_slot
            if active_slot:
                job.active_slot = active_slot
            self._save()

    def get_job(self, instruction_id: str) -> Optional[JournaledJob]:
        return self.jobs.get(instruction_id)


class DeploymentWorker:
    def __init__(
        self,
        device_id: str,
        state_dir: Path,
        slot_manager: ABSlotManager,
        key_store: TrustedReleaseKeyStore,
        artifact_client: ArtifactClient,
        source_registry: Optional[TrustedArtifactSourceRegistry] = None,
        status_callback: Optional[Callable[[DeploymentStatusReport], Coroutine[Any, Any, None]]] = None,
        current_ros_distro: Optional[str] = None,
    ):
        self.device_id = device_id
        self.state_dir = Path(state_dir)
        self.slot_manager = slot_manager
        self.key_store = key_store
        self.artifact_client = artifact_client
        self.source_registry = source_registry or TrustedArtifactSourceRegistry(self.state_dir / "artifact_sources.json")
        self.status_callback = status_callback
        self.current_ros_distro = current_ros_distro

        self.gen_manager = GenerationStateManager(self.state_dir / "generation_state.json")
        self.journal = AgentJobJournal(self.state_dir / "deployment_jobs.json")

        self._current_task: Optional[asyncio.Task] = None
        self._current_instruction_id: Optional[str] = None
        self.device_lock = asyncio.Lock()

    def reconcile_on_startup(self) -> None:
        """Reconcile active/staged slots, journaled jobs, and generation state on agent restart."""
        logger.info("Reconciling agent deployment state on startup for device %s...", self.device_id)
        active_slot = self.slot_manager.get_active_slot_id()
        logger.info("Current slot state: active=%s", active_slot)

        for inst_id, job in self.journal.jobs.items():
            if job.status in ("ACCEPTED", "EXECUTING"):
                logger.warning("Found unfinalized job %s (type: %s) on restart. Reconciling...", inst_id, job.instruction_type)
                if job.instruction_type == InstructionType.STAGE_RELEASE.value:
                    staged_id = "slot-b" if active_slot == "slot-a" else "slot-a"
                    slot_meta = self.slot_manager.state.slots.get(staged_id)
                    if slot_meta and slot_meta.state == SlotState.VERIFIED and slot_meta.release_id == job.payload.get("release_id"):
                        logger.info("Reconciled job %s as STAGED in %s", inst_id, staged_id)
                        self.journal.update_job_status(inst_id, "COMPLETED", staged_slot=staged_id)
                    else:
                        logger.warning("Job %s was interrupted during staging; marking FAILED", inst_id)
                        self.journal.update_job_status(inst_id, "FAILED", error_message="Interrupted by daemon restart")
                elif job.instruction_type == InstructionType.ACTIVATE_RELEASE.value:
                    target_slot = job.payload.get("slot") or job.payload.get("target_slot")
                    if target_slot and not target_slot.startswith("slot-"):
                        target_slot = f"slot-{target_slot.lower()}"
                    if active_slot == target_slot:
                        logger.info("Reconciled job %s as ACTIVATED in %s", inst_id, target_slot)
                        self.journal.update_job_status(inst_id, "COMPLETED", active_slot=target_slot)
                    else:
                        logger.warning("Job %s was interrupted during activation; marking FAILED", inst_id)
                        self.journal.update_job_status(inst_id, "FAILED", error_message="Interrupted by daemon restart")

    async def _emit_status(
        self,
        instruction_id: str,
        deployment_id: str,
        generation: int,
        state: DeviceDeploymentState,
        staged_slot: Optional[str] = None,
        active_slot: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        report = DeploymentStatusReport(
            report_id=f"rep-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
            instruction_id=instruction_id,
            deployment_id=deployment_id,
            device_id=self.device_id,
            generation=generation,
            state=state,
            current_slot=self.slot_manager.get_active_slot_id(),
            staged_slot=staged_slot,
            active_slot=active_slot,
            error_code=error_code,
            error_message=error_message,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        if self.status_callback:
            try:
                await self.status_callback(report)
            except Exception as e:
                logger.error("Failed to emit status report via callback: %s", e)

    async def report_status(
        self,
        deployment_id: str,
        generation: int,
        state: DeviceDeploymentState,
        staged_slot: Optional[str] = None,
        active_slot: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        inst_id = self._current_instruction_id or f"inst-legacy-{generation}"
        await self._emit_status(
            instruction_id=inst_id,
            deployment_id=deployment_id,
            generation=generation,
            state=state,
            staged_slot=staged_slot,
            active_slot=active_slot,
            error_message=error_message,
        )

    async def handle_instruction(self, envelope: DeploymentInstructionEnvelope) -> DeploymentAckEnvelope:
        now_dt = datetime.now(timezone.utc)

        # 1. Device identity validation
        if envelope.device_id and envelope.device_id != "unknown" and envelope.device_id != self.device_id:
            logger.error("Target device mismatch: envelope target=%s != local=%s", envelope.device_id, self.device_id)
            return DeploymentAckEnvelope(
                ack_id=f"ack-{int(now_dt.timestamp() * 1000)}",
                instruction_id=envelope.instruction_id,
                deployment_id=envelope.deployment_id,
                device_id=self.device_id,
                generation=envelope.generation,
                accepted=False,
                error_code="TARGET_DEVICE_MISMATCH",
                error_message=f"Target device mismatch: {envelope.device_id} != {self.device_id}",
                timestamp=now_dt.isoformat(),
            )

        # 2. Expiry check
        try:
            exp_dt = datetime.fromisoformat(envelope.expires_at)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if exp_dt <= now_dt:
                return DeploymentAckEnvelope(
                    ack_id=f"ack-{int(now_dt.timestamp() * 1000)}",
                    instruction_id=envelope.instruction_id,
                    deployment_id=envelope.deployment_id,
                    device_id=self.device_id,
                    generation=envelope.generation,
                    accepted=False,
                    error_code="INSTRUCTION_EXPIRED",
                    error_message="Instruction has expired",
                    timestamp=now_dt.isoformat(),
                )
        except Exception as e:
            logger.warning("Failed to parse expires_at timestamp: %s", e)

        # 3. Monotonic Generation & Replay Binding
        full_digest = canonical_instruction_digest(envelope)
        last_gen = self.gen_manager.state.last_generation
        last_digest = self.gen_manager.state.last_instruction_digest

        if envelope.generation < last_gen:
            return DeploymentAckEnvelope(
                ack_id=f"ack-{int(now_dt.timestamp() * 1000)}",
                instruction_id=envelope.instruction_id,
                deployment_id=envelope.deployment_id,
                device_id=self.device_id,
                generation=envelope.generation,
                accepted=False,
                error_code="STALE_GENERATION",
                error_message=f"Instruction generation {envelope.generation} is strictly less than current generation {last_gen}",
                timestamp=now_dt.isoformat(),
            )
        elif envelope.generation == last_gen:
            if last_digest == full_digest or envelope.payload_digest == self.gen_manager.state.last_instruction_digest:
                logger.info("Idempotent replay detected for generation %d", envelope.generation)
                return DeploymentAckEnvelope(
                    ack_id=f"ack-{int(now_dt.timestamp() * 1000)}",
                    instruction_id=envelope.instruction_id,
                    deployment_id=envelope.deployment_id,
                    device_id=self.device_id,
                    generation=envelope.generation,
                    accepted=True,
                    error_code="IDEMPOTENT_REPLAY",
                    error_message="Instruction already processed at this generation",
                    timestamp=now_dt.isoformat(),
                )
            else:
                return DeploymentAckEnvelope(
                    ack_id=f"ack-{int(now_dt.timestamp() * 1000)}",
                    instruction_id=envelope.instruction_id,
                    deployment_id=envelope.deployment_id,
                    device_id=self.device_id,
                    generation=envelope.generation,
                    accepted=False,
                    error_code="REPLAY_CONFLICT",
                    error_message=f"Generation {envelope.generation} already seen with a different instruction digest",
                    timestamp=now_dt.isoformat(),
                )

        # 4. Record journal and generation state BEFORE execution
        job = JournaledJob(
            instruction_id=envelope.instruction_id,
            deployment_id=envelope.deployment_id,
            generation=envelope.generation,
            instruction_type=envelope.instruction_type.value,
            payload=envelope.payload,
            full_instruction_digest=full_digest,
            status="ACCEPTED",
            created_at=now_dt.isoformat(),
            updated_at=now_dt.isoformat(),
        )
        self.journal.record_job(job)
        self.gen_manager.record_generation(envelope.generation, envelope.deployment_id, full_digest)

        # 5. Schedule asynchronous execution task
        self._current_instruction_id = envelope.instruction_id
        self._current_task = asyncio.create_task(self._execute_instruction(envelope))

        return DeploymentAckEnvelope(
            ack_id=f"ack-{int(now_dt.timestamp() * 1000)}",
            instruction_id=envelope.instruction_id,
            deployment_id=envelope.deployment_id,
            device_id=self.device_id,
            generation=envelope.generation,
            accepted=True,
            error_code="ACCEPTED",
            error_message=None,
            timestamp=now_dt.isoformat(),
        )

    async def _execute_instruction(self, envelope: DeploymentInstructionEnvelope) -> None:
        async with self.device_lock:
            inst_id = envelope.instruction_id
            dep_id = envelope.deployment_id
            gen = envelope.generation
            itype = envelope.instruction_type

            try:
                self.journal.update_job_status(inst_id, "EXECUTING")

                if itype == InstructionType.STAGE_RELEASE:
                    await self._handle_stage_release(dep_id, gen, envelope.payload)
                elif itype == InstructionType.ACTIVATE_RELEASE:
                    await self._handle_activate_release(dep_id, gen, envelope.payload)
                elif itype == InstructionType.CANCEL_DEPLOYMENT:
                    await self._handle_cancel_deployment(dep_id, gen, envelope.payload)
                elif itype == InstructionType.GET_DEPLOYMENT_STATUS:
                    await self._handle_get_status(dep_id, gen, envelope.payload)
                else:
                    logger.error("Unsupported instruction type: %s", itype)
                    self.journal.update_job_status(inst_id, "FAILED", error_message=f"Unsupported instruction type: {itype}")
                    await self._emit_status(
                        inst_id,
                        dep_id,
                        gen,
                        DeviceDeploymentState.FAILED,
                        error_code="UNSUPPORTED_INSTRUCTION",
                        error_message=f"Unsupported: {itype}",
                    )
            except asyncio.CancelledError:
                logger.info("Instruction %s execution was cancelled", inst_id)
                self.journal.update_job_status(inst_id, "CANCELLED", error_message="Task cancelled")
                await self._emit_status(
                    inst_id,
                    dep_id,
                    gen,
                    DeviceDeploymentState.CANCELLED,
                    error_code="TASK_CANCELLED",
                    error_message="Execution interrupted safely",
                )
            except Exception as e:
                logger.exception("Failed executing instruction %s: %s", inst_id, e)
                self.journal.update_job_status(inst_id, "FAILED", error_message=str(e))
                await self._emit_status(
                    inst_id, dep_id, gen, DeviceDeploymentState.FAILED, error_code="EXECUTION_ERROR", error_message=str(e)
                )

    async def _handle_stage_release(
        self,
        deployment_id: str,
        generation: int,
        payload: Dict[str, Any],
    ) -> None:
        inst_id = self._current_instruction_id or f"inst-{generation}"
        await self._emit_status(inst_id, deployment_id, generation, DeviceDeploymentState.FETCHING)

        release_id = payload["release_id"]
        expected_manifest_digest = payload["manifest_digest"]
        expected_artifact_digest = payload["artifact_digest"]
        source_id = payload["artifact_source_id"]

        source = self.source_registry.get_source(source_id)
        if not source:
            raise DeploymentError(f"Unknown artifact source ID '{source_id}'. Local TrustedArtifactSourceRegistry is authoritative.")
        base_url = source.base_url
        allowed_host = source.allowed_host
        allow_private = source.allow_private_network

        manifest_url = f"{base_url.rstrip('/')}/{release_id}/manifest.json"
        artifact_url = f"{base_url.rstrip('/')}/{release_id}/artifact.tar.gz"
        sig_url = f"{base_url.rstrip('/')}/{release_id}/signature.sig"

        # 1. Fetch manifest
        manifest_bytes, manifest = await self.artifact_client.fetch_manifest(
            url=manifest_url,
            expected_manifest_digest=expected_manifest_digest,
            allowed_host=allowed_host,
            allow_private_network=allow_private,
        )

        # 2. Fetch signature
        sig_text = await self.artifact_client.fetch_signature_text(
            url=sig_url,
            allowed_host=allowed_host,
            allow_private_network=allow_private,
        )

        # 3. Download artifact
        artifact_path = await self.artifact_client.download_and_verify(
            url=artifact_url,
            expected_digest=expected_artifact_digest,
            deployment_id=deployment_id,
            allowed_host=allowed_host,
            allow_private_network=allow_private,
        )

        await self._emit_status(inst_id, deployment_id, generation, DeviceDeploymentState.VERIFYING)

        # 4. Save manifest and signature files for staging workflow
        dep_dir = self.state_dir / "staging_evidence" / deployment_id
        dep_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = dep_dir / f"{release_id}.manifest.json"
        sig_path = dep_dir / f"{release_id}.sig"

        manifest_path.write_bytes(manifest_bytes)
        sig_path.write_text(sig_text, encoding="utf-8")

        await self._emit_status(inst_id, deployment_id, generation, DeviceDeploymentState.STAGING)

        # 5. Extract and stage into inactive slot
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

        staged_slot = "slot-b" if self.slot_manager.get_active_slot_id() == "slot-a" else "slot-a"
        self.journal.update_job_status(inst_id, "COMPLETED", staged_slot=staged_slot)

        await self._emit_status(
            inst_id,
            deployment_id,
            generation,
            DeviceDeploymentState.STAGED,
            staged_slot=staged_slot,
        )

    async def _handle_activate_release(
        self,
        deployment_id: str,
        generation: int,
        payload: Dict[str, Any],
    ) -> None:
        inst_id = self._current_instruction_id or f"inst-{generation}"
        await self._emit_status(inst_id, deployment_id, generation, DeviceDeploymentState.ACTIVATING)

        target_slot = payload.get("target_slot") or payload.get("slot")
        if target_slot and not target_slot.startswith("slot-"):
            target_slot = f"slot-{target_slot.lower()}"

        success, msg = activate_staged_slot(
            manager=self.slot_manager,
            slot_id=target_slot,
        )

        if not success:
            raise ValueError(f"Activation failed: {msg}")

        active_slot = self.slot_manager.get_active_slot_id()
        self.journal.update_job_status(inst_id, "COMPLETED", active_slot=active_slot)

        await self._emit_status(
            inst_id,
            deployment_id,
            generation,
            DeviceDeploymentState.ACTIVE,
            active_slot=active_slot,
        )

    async def _handle_cancel_deployment(
        self,
        deployment_id: str,
        generation: int,
        payload: Dict[str, Any],
    ) -> None:
        inst_id = self._current_instruction_id or f"inst-{generation}"
        self.journal.update_job_status(inst_id, "COMPLETED")
        await self._emit_status(
            inst_id,
            deployment_id,
            generation,
            DeviceDeploymentState.CANCELLED,
            current_slot=self.slot_manager.get_active_slot_id(),
        )

    async def _handle_get_status(
        self,
        deployment_id: str,
        generation: int,
        payload: Dict[str, Any],
    ) -> None:
        inst_id = self._current_instruction_id or f"inst-{generation}"
        active = self.slot_manager.get_active_slot_id()
        curr_state = DeviceDeploymentState.ACTIVE if active else DeviceDeploymentState.PENDING
        await self._emit_status(
            inst_id,
            deployment_id,
            generation,
            curr_state,
            active_slot=active,
        )
