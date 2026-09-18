"""Authoritative deployment orchestration, release catalog, outbox management, and canary progression service."""

import hashlib
import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from openrobo_release.deployment_protocol import (
    ApprovalAction,
    DeploymentState,
    DeploymentStatusReport,
    DeviceDeploymentState,
    InstructionStatus,
    InstructionType,
    ReleaseSnapshot,
    RolloutStrategy,
    RolloutStrategyType,
    TargetFilter,
    validate_deployment_transition,
    validate_device_transition,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models import (
    ArtifactSourceModel,
    DeploymentApprovalModel,
    DeploymentCounterModel,
    DeploymentEventModel,
    DeploymentInstructionModel,
    DeploymentModel,
    DeviceDeploymentModel,
    FleetDeviceModel,
    ReleaseArtifactModel,
)
from apps.api.schemas.deployment import (
    ArtifactSourceCreate,
    DeploymentApprovalRequest,
    DeploymentCreate,
    ReleaseArtifactCreate,
    StageSummary,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DeploymentService:
    @staticmethod
    async def get_next_generation(session: AsyncSession) -> int:
        # Atomically fetch and increment the global deployment generation counter.
        stmt = select(DeploymentCounterModel).where(DeploymentCounterModel.counter_name == "global_generation").with_for_update()
        res = await session.execute(stmt)
        counter = res.scalar_one_or_none()
        if not counter:
            counter = DeploymentCounterModel(counter_name="global_generation", current_val=1)
            session.add(counter)
            await session.flush()
            return 1
        counter.current_val += 1
        await session.flush()
        return counter.current_val

    @staticmethod
    async def register_artifact_source(
        session: AsyncSession,
        req: ArtifactSourceCreate,
    ) -> ArtifactSourceModel:
        # Register or update an artifact distribution endpoint.
        stmt = select(ArtifactSourceModel).where(ArtifactSourceModel.id == req.id)
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            existing.base_url = req.base_url
            existing.allowed_host = req.allowed_host
            existing.ca_policy = req.ca_policy
            existing.max_artifact_bytes = req.max_artifact_bytes
            existing.allow_private_network = req.allow_private_network
            await session.flush()
            return existing

        source = ArtifactSourceModel(
            id=req.id,
            base_url=req.base_url,
            allowed_host=req.allowed_host,
            ca_policy=req.ca_policy,
            max_artifact_bytes=req.max_artifact_bytes,
            allow_private_network=req.allow_private_network,
        )
        session.add(source)
        await session.flush()
        return source

    @staticmethod
    async def register_release(
        session: AsyncSession,
        req: ReleaseArtifactCreate,
        registered_by: str = "configured-admin",
    ) -> ReleaseArtifactModel:
        # Register release metadata into authoritative catalog.
        source_stmt = select(ArtifactSourceModel).where(ArtifactSourceModel.id == req.artifact_source_id)
        source_res = await session.execute(source_stmt)
        source = source_res.scalar_one_or_none()
        if not source:
            raise ValueError(f"Artifact source '{req.artifact_source_id}' does not exist")

        stmt = select(ReleaseArtifactModel).where(ReleaseArtifactModel.release_id == req.release_id)
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            if existing.immutable_after_deployment:
                raise ValueError(f"Release '{req.release_id}' is immutable because it was used in active deployments")
            if (
                existing.manifest_digest != req.manifest_digest
                or existing.artifact_digest != req.artifact_digest
                or existing.workspace_digest != req.workspace_digest
                or existing.release_key_id != req.release_key_id
            ):
                raise ValueError(f"Release '{req.release_id}' already registered with different digests or key")
            return existing

        release = ReleaseArtifactModel(
            release_id=req.release_id,
            release_version=req.release_version,
            manifest_digest=req.manifest_digest,
            artifact_digest=req.artifact_digest,
            workspace_digest=req.workspace_digest,
            release_key_id=req.release_key_id,
            artifact_source_id=req.artifact_source_id,
            target_os=req.target_os,
            target_architecture=req.target_architecture,
            target_ros_distro=req.target_ros_distro,
            registered_by=registered_by,
        )
        session.add(release)
        await session.flush()
        return release

    @staticmethod
    async def resolve_target_devices(
        session: AsyncSession,
        deployment_id: str,
        target_filter: TargetFilter,
        release: ReleaseArtifactModel,
        rollout_strategy: RolloutStrategy,
    ) -> List[Tuple[FleetDeviceModel, int]]:
        # Resolve fleet devices, filter compatibility, partition deterministically into cohorts.
        stmt = select(FleetDeviceModel).where(FleetDeviceModel.status == "ENROLLED")
        res = await session.execute(stmt)
        all_devices = list(res.scalars().all())

        matched_devices: List[FleetDeviceModel] = []
        for dev in all_devices:
            if target_filter.device_ids and dev.id not in target_filter.device_ids:
                continue
            if target_filter.domains and dev.domain not in target_filter.domains:
                continue
            if target_filter.robot_types and dev.robot_type not in target_filter.robot_types:
                continue
            if target_filter.capabilities:
                dev_caps = dev.capabilities_json if isinstance(dev.capabilities_json, list) else []
                if not all(c in dev_caps for c in target_filter.capabilities):
                    continue

            hb = dev.last_heartbeat_json if isinstance(dev.last_heartbeat_json, dict) else {}
            dev_os = hb.get("os", "linux")
            dev_arch = hb.get("architecture", "x86_64")
            dev_ros = hb.get("ros_distro", None)

            if release.target_os and dev_os != release.target_os:
                continue
            if release.target_architecture and dev_arch != release.target_architecture:
                continue
            if release.target_ros_distro and dev_ros != release.target_ros_distro:
                continue

            matched_devices.append(dev)

        if not matched_devices:
            return []

        def device_sort_key(dev: FleetDeviceModel) -> str:
            raw = f"{deployment_id}:{dev.id}".encode("utf-8")
            return hashlib.sha256(raw).hexdigest()

        matched_devices.sort(key=device_sort_key)
        total_matched = len(matched_devices)

        device_stage_assignments: List[Tuple[FleetDeviceModel, int]] = []
        if rollout_strategy.strategy_type == RolloutStrategyType.IMMEDIATE_ALL or not rollout_strategy.stages:
            for dev in matched_devices:
                device_stage_assignments.append((dev, 0))
            return device_stage_assignments

        curr_idx = 0
        for s_idx, stage_cfg in enumerate(rollout_strategy.stages):
            if curr_idx >= total_matched:
                break
            if s_idx == len(rollout_strategy.stages) - 1:
                stage_devices = matched_devices[curr_idx:]
                curr_idx = total_matched
            else:
                pct = stage_cfg.target_percentage
                count = math.ceil(total_matched * pct / 100.0)
                stage_devices = matched_devices[curr_idx : curr_idx + count]
                curr_idx += count

            for dev in stage_devices:
                device_stage_assignments.append((dev, s_idx))

        return device_stage_assignments

    @staticmethod
    async def create_deployment(
        session: AsyncSession,
        req: DeploymentCreate,
        created_by: str = "configured-admin",
    ) -> DeploymentModel:
        # Create a new deployment, snapshot release metadata, assign devices, persist instructions.
        if req.idempotency_key:
            stmt = select(DeploymentModel).where(DeploymentModel.idempotency_key == req.idempotency_key)
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                return existing

        rel_stmt = select(ReleaseArtifactModel).where(ReleaseArtifactModel.release_id == req.release_id)
        rel_res = await session.execute(rel_stmt)
        release = rel_res.scalar_one_or_none()
        if not release:
            raise ValueError(f"Release '{req.release_id}' is not registered in the control plane catalog")
        if release.status != "ACTIVE":
            raise ValueError(f"Release '{req.release_id}' is {release.status} and cannot be deployed")

        snapshot = ReleaseSnapshot(
            release_id=release.release_id,
            release_version=release.release_version,
            manifest_digest=release.manifest_digest,
            artifact_digest=release.artifact_digest,
            workspace_digest=release.workspace_digest,
            release_key_id=release.release_key_id,
            artifact_source_id=release.artifact_source_id,
            target_os=release.target_os,
            target_architecture=release.target_architecture,
            target_ros_distro=release.target_ros_distro,
        )

        deployment_id = str(uuid.uuid4())
        generation = await DeploymentService.get_next_generation(session)

        assignments = await DeploymentService.resolve_target_devices(
            session=session,
            deployment_id=deployment_id,
            target_filter=req.target_filter,
            release=release,
            rollout_strategy=req.rollout_strategy,
        )

        if not assignments:
            raise ValueError("Target filter matched 0 eligible devices in the fleet")

        total_stages = (
            len(req.rollout_strategy.stages)
            if req.rollout_strategy.strategy_type == RolloutStrategyType.CANARY and req.rollout_strategy.stages
            else 1
        )

        deployment = DeploymentModel(
            id=deployment_id,
            release_id=release.release_id,
            release_snapshot_json=snapshot.model_dump_json(),
            manifest_digest=release.manifest_digest,
            artifact_digest=release.artifact_digest,
            workspace_digest=release.workspace_digest,
            release_key_id=release.release_key_id,
            artifact_source_id=release.artifact_source_id,
            target_os=release.target_os,
            target_architecture=release.target_architecture,
            target_ros_distro=release.target_ros_distro,
            rollout_strategy=req.rollout_strategy.model_dump_json(),
            target_filter=req.target_filter.model_dump_json(),
            status=DeploymentState.STAGING_STAGE_0.value,
            current_stage=0,
            total_stages=total_stages,
            generation=generation,
            version=1,
            idempotency_key=req.idempotency_key,
            created_by=created_by,
        )
        session.add(deployment)
        release.immutable_after_deployment = True

        for dev, stage_idx in assignments:
            dev_dep = DeviceDeploymentModel(
                deployment_id=deployment_id,
                device_id=dev.id,
                stage_index=stage_idx,
                status=DeviceDeploymentState.PENDING.value,
                generation=generation,
                target_snapshot_json=json.dumps(
                    {
                        "name": dev.name,
                        "domain": dev.domain,
                        "robot_type": dev.robot_type,
                        "matched_stage": stage_idx,
                    }
                ),
            )
            session.add(dev_dep)

            if stage_idx == 0:
                payload = {
                    "release_id": release.release_id,
                    "manifest_digest": release.manifest_digest,
                    "artifact_digest": release.artifact_digest,
                    "workspace_digest": release.workspace_digest,
                    "release_key_id": release.release_key_id,
                    "artifact_source_id": release.artifact_source_id,
                    "target_os": release.target_os,
                    "target_architecture": release.target_architecture,
                    "target_ros_distro": release.target_ros_distro,
                }
                canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
                payload_digest = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

                instruction = DeploymentInstructionModel(
                    deployment_id=deployment_id,
                    device_id=dev.id,
                    generation=generation,
                    instruction_type=InstructionType.STAGE_RELEASE.value,
                    payload_json=canonical_payload,
                    payload_digest=payload_digest,
                    status=InstructionStatus.PENDING.value,
                    expires_at=utc_now() + timedelta(hours=24),
                )
                session.add(instruction)

        event = DeploymentEventModel(
            deployment_id=deployment_id,
            event_type="DEPLOYMENT_CREATED",
            details=json.dumps(
                {
                    "release_id": release.release_id,
                    "total_devices": len(assignments),
                    "total_stages": total_stages,
                    "generation": generation,
                }
            ),
        )
        session.add(event)

        await session.flush()
        return deployment

    @staticmethod
    async def get_deployment_summary(session: AsyncSession, deployment_id: str) -> Optional[Dict[str, Any]]:
        stmt = select(DeploymentModel).where(DeploymentModel.id == deployment_id)
        res = await session.execute(stmt)
        deployment = res.scalar_one_or_none()
        if not deployment:
            return None

        dev_stmt = select(DeviceDeploymentModel).where(DeviceDeploymentModel.deployment_id == deployment_id)
        dev_res = await session.execute(dev_stmt)
        device_deployments = list(dev_res.scalars().all())

        stages_dict: Dict[int, Dict[str, int]] = {}
        strategy = RolloutStrategy.model_validate_json(deployment.rollout_strategy)

        for s_idx in range(deployment.total_stages):
            pct = 100
            if strategy.stages and s_idx < len(strategy.stages):
                pct = strategy.stages[s_idx].target_percentage
            stages_dict[s_idx] = {
                "stage_index": s_idx,
                "target_percentage": pct,
                "total_devices": 0,
                "pending": 0,
                "fetching": 0,
                "verifying": 0,
                "staging": 0,
                "staged": 0,
                "activating": 0,
                "active": 0,
                "failed": 0,
                "cancelled": 0,
            }

        for dd in device_deployments:
            s_idx = dd.stage_index
            if s_idx in stages_dict:
                stages_dict[s_idx]["total_devices"] += 1
                status_lower = dd.status.lower()
                if status_lower in stages_dict[s_idx]:
                    stages_dict[s_idx][status_lower] += 1

        stage_summaries = [StageSummary(**data) for data in stages_dict.values()]
        return {
            "deployment": deployment,
            "stages": stage_summaries,
            "device_deployments": device_deployments,
        }

    @staticmethod
    async def approve_stage_progression(
        session: AsyncSession,
        deployment_id: str,
        req: DeploymentApprovalRequest,
        approved_by: str = "configured-admin",
    ) -> DeploymentModel:
        stmt = select(DeploymentModel).where(DeploymentModel.id == deployment_id).with_for_update()
        res = await session.execute(stmt)
        deployment = res.scalar_one_or_none()
        if not deployment:
            raise ValueError(f"Deployment '{deployment_id}' not found")

        if deployment.version != req.expected_version:
            raise ValueError(
                f"Deployment version mismatch (expected {req.expected_version}, current {deployment.version}). Optimistic conflict."
            )

        if deployment.status != req.expected_state.value:
            raise ValueError(f"Deployment state mismatch (expected {req.expected_state.value}, current {deployment.status}).")

        current_stage = deployment.current_stage
        if current_stage != req.stage_index:
            raise ValueError(f"Approval stage index {req.stage_index} does not match current deployment stage {current_stage}.")

        generation = await DeploymentService.get_next_generation(session)
        deployment.generation = generation
        target_state: DeploymentState

        if req.action == ApprovalAction.APPROVE_CURRENT_COHORT_ACTIVATION:
            target_state = DeploymentState[f"ACTIVATING_STAGE_{current_stage}"]
            validate_deployment_transition(DeploymentState(deployment.status), target_state)

            dev_stmt = select(DeviceDeploymentModel).where(
                DeviceDeploymentModel.deployment_id == deployment_id,
                DeviceDeploymentModel.stage_index == current_stage,
            )
            dev_res = await session.execute(dev_stmt)
            for dd in dev_res.scalars().all():
                payload = {
                    "release_id": deployment.release_id,
                    "target_slot": dd.staged_slot or "B",
                }
                canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
                payload_digest = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

                instruction = DeploymentInstructionModel(
                    deployment_id=deployment_id,
                    device_id=dd.device_id,
                    generation=generation,
                    instruction_type=InstructionType.ACTIVATE_RELEASE.value,
                    payload_json=canonical_payload,
                    payload_digest=payload_digest,
                    status=InstructionStatus.PENDING.value,
                    expires_at=utc_now() + timedelta(hours=24),
                )
                session.add(instruction)

        elif req.action == ApprovalAction.APPROVE_NEXT_COHORT_STAGING:
            next_stage = current_stage + 1
            if next_stage >= deployment.total_stages:
                raise ValueError("No next stage available; deployment is at final stage.")
            target_state = DeploymentState[f"STAGING_STAGE_{next_stage}"]
            validate_deployment_transition(DeploymentState(deployment.status), target_state)

            deployment.current_stage = next_stage

            dev_stmt = select(DeviceDeploymentModel).where(
                DeviceDeploymentModel.deployment_id == deployment_id,
                DeviceDeploymentModel.stage_index == next_stage,
            )
            dev_res = await session.execute(dev_stmt)
            release_snapshot = ReleaseSnapshot.model_validate_json(deployment.release_snapshot_json)

            for dd in dev_res.scalars().all():
                payload = {
                    "release_id": deployment.release_id,
                    "manifest_digest": release_snapshot.manifest_digest,
                    "artifact_digest": release_snapshot.artifact_digest,
                    "workspace_digest": release_snapshot.workspace_digest,
                    "release_key_id": release_snapshot.release_key_id,
                    "artifact_source_id": release_snapshot.artifact_source_id,
                    "target_os": release_snapshot.target_os,
                    "target_architecture": release_snapshot.target_architecture,
                    "target_ros_distro": release_snapshot.target_ros_distro,
                }
                canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
                payload_digest = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

                instruction = DeploymentInstructionModel(
                    deployment_id=deployment_id,
                    device_id=dd.device_id,
                    generation=generation,
                    instruction_type=InstructionType.STAGE_RELEASE.value,
                    payload_json=canonical_payload,
                    payload_digest=payload_digest,
                    status=InstructionStatus.PENDING.value,
                    expires_at=utc_now() + timedelta(hours=24),
                )
                session.add(instruction)

        elif req.action == ApprovalAction.APPROVE_COMPLETION:
            target_state = DeploymentState.COMPLETED
            validate_deployment_transition(DeploymentState(deployment.status), target_state)
            deployment.completed_at = utc_now()

        elif req.action == ApprovalAction.REJECT_AND_CANCEL:
            target_state = DeploymentState.CANCELLED
            validate_deployment_transition(DeploymentState(deployment.status), target_state)
            deployment.cancelled_at = utc_now()
            await DeploymentService.cancel_remaining_devices(session, deployment_id, generation)
        else:
            raise ValueError(f"Unsupported approval action: {req.action}")

        deployment.status = target_state.value
        deployment.version += 1

        approval = DeploymentApprovalModel(
            deployment_id=deployment_id,
            stage_index=current_stage,
            action=req.action.value,
            approved_by=approved_by,
            previous_state=req.expected_state.value,
            new_state=target_state.value,
            notes=req.notes,
        )
        session.add(approval)

        event = DeploymentEventModel(
            deployment_id=deployment_id,
            event_type="STAGE_APPROVAL_GRANTED",
            details=json.dumps(
                {
                    "action": req.action.value,
                    "approved_by": approved_by,
                    "new_state": target_state.value,
                    "stage_index": current_stage,
                    "version": deployment.version,
                }
            ),
        )
        session.add(event)

        await session.flush()
        return deployment

    @staticmethod
    async def cancel_remaining_devices(session: AsyncSession, deployment_id: str, generation: int) -> None:
        dev_stmt = select(DeviceDeploymentModel).where(
            DeviceDeploymentModel.deployment_id == deployment_id,
            DeviceDeploymentModel.status.notin_(
                [
                    DeviceDeploymentState.ACTIVE.value,
                    DeviceDeploymentState.CANCELLED.value,
                    DeviceDeploymentState.FAILED.value,
                ]
            ),
        )
        dev_res = await session.execute(dev_stmt)
        for dd in dev_res.scalars().all():
            dd.status = DeviceDeploymentState.CANCELLED.value
            payload = {"deployment_id": deployment_id}
            canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            payload_digest = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

            instruction = DeploymentInstructionModel(
                deployment_id=deployment_id,
                device_id=dd.device_id,
                generation=generation,
                instruction_type=InstructionType.CANCEL_DEPLOYMENT.value,
                payload_json=canonical_payload,
                payload_digest=payload_digest,
                status=InstructionStatus.PENDING.value,
                expires_at=utc_now() + timedelta(hours=24),
            )
            session.add(instruction)

    @staticmethod
    async def handle_device_status_report(
        session: AsyncSession,
        device_id: str,
        report: DeploymentStatusReport,
    ) -> DeviceDeploymentModel:
        stmt = (
            select(DeviceDeploymentModel)
            .where(
                DeviceDeploymentModel.deployment_id == report.deployment_id,
                DeviceDeploymentModel.device_id == device_id,
            )
            .with_for_update()
        )
        res = await session.execute(stmt)
        dd = res.scalar_one_or_none()
        if not dd:
            raise ValueError(f"Device deployment assignment not found for device '{device_id}' and deployment '{report.deployment_id}'")

        current_state = DeviceDeploymentState(dd.status)
        new_state = report.state
        validate_device_transition(current_state, new_state)

        dd.status = new_state.value
        dd.generation = report.generation
        if report.staged_slot:
            dd.staged_slot = report.staged_slot
        if report.active_slot:
            dd.active_slot = report.active_slot
        if report.error_message:
            dd.error_message = report.error_message

        await DeploymentService.evaluate_stage_progression(session, report.deployment_id, dd.stage_index)

        event = DeploymentEventModel(
            deployment_id=report.deployment_id,
            device_id=device_id,
            event_type="DEVICE_STATUS_TRANSITION",
            details=json.dumps(
                {
                    "previous_state": current_state.value,
                    "new_state": new_state.value,
                    "generation": report.generation,
                    "staged_slot": report.staged_slot,
                    "active_slot": report.active_slot,
                    "error_message": report.error_message,
                }
            ),
        )
        session.add(event)

        await session.flush()
        return dd

    @staticmethod
    async def evaluate_stage_progression(session: AsyncSession, deployment_id: str, stage_index: int) -> None:
        dep_stmt = select(DeploymentModel).where(DeploymentModel.id == deployment_id).with_for_update()
        dep_res = await session.execute(dep_stmt)
        deployment = dep_res.scalar_one_or_none()
        if not deployment or deployment.current_stage != stage_index:
            return

        dev_stmt = select(DeviceDeploymentModel).where(
            DeviceDeploymentModel.deployment_id == deployment_id,
            DeviceDeploymentModel.stage_index == stage_index,
        )
        dev_res = await session.execute(dev_stmt)
        devices = list(dev_res.scalars().all())
        if not devices:
            return

        all_staged = all(d.status in (DeviceDeploymentState.STAGED.value, DeviceDeploymentState.ACTIVE.value) for d in devices)
        all_active = all(d.status == DeviceDeploymentState.ACTIVE.value for d in devices)
        any_failed = any(d.status == DeviceDeploymentState.FAILED.value for d in devices)

        curr_state = DeploymentState(deployment.status)

        if curr_state == DeploymentState[f"STAGING_STAGE_{stage_index}"] and all_staged:
            next_state = DeploymentState[f"STAGE_{stage_index}_WAITING_FOR_ACTIVATION_APPROVAL"]
            deployment.status = next_state.value
            deployment.version += 1
        elif curr_state == DeploymentState[f"ACTIVATING_STAGE_{stage_index}"] and all_active:
            if stage_index + 1 < deployment.total_stages:
                next_state = DeploymentState[f"STAGE_{stage_index}_WAITING_FOR_STAGE_APPROVAL"]
                deployment.status = next_state.value
                deployment.version += 1
            else:
                deployment.status = DeploymentState.COMPLETED.value
                deployment.completed_at = utc_now()
                deployment.version += 1
        elif any_failed and not curr_state.value.endswith("_FAILED"):
            deployment.status = DeploymentState[f"STAGE_{stage_index}_FAILED"].value
            deployment.version += 1

    @staticmethod
    async def get_pending_instructions_for_device(
        session: AsyncSession,
        device_id: str,
    ) -> List[DeploymentInstructionModel]:
        stmt = (
            select(DeploymentInstructionModel)
            .where(
                DeploymentInstructionModel.device_id == device_id,
                DeploymentInstructionModel.status == InstructionStatus.PENDING.value,
                DeploymentInstructionModel.expires_at > utc_now(),
            )
            .order_by(DeploymentInstructionModel.generation.asc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())
