"""Authoritative deployment orchestration, release catalog, outbox management, and canary progression service."""

import hashlib
import json
import math
import os
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
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models import (
    ArtifactSourceModel,
    DeploymentApprovalModel,
    DeploymentCounterModel,
    DeploymentEventModel,
    DeploymentInstructionModel,
    DeploymentModel,
    DeviceDeploymentLeaseModel,
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


def normalize_arch(arch: Optional[str]) -> Optional[str]:
    """Normalize architecture aliases according to Amendment 11."""
    if not arch:
        return None
    a = arch.strip().lower()
    if a in ("x86_64", "amd64", "x64"):
        return "x86_64"
    if a in ("aarch64", "arm64"):
        return "aarch64"
    return a


def redact_secrets(obj: Any) -> Any:
    """Recursively redact sensitive keys (Amendment 21)."""
    SENSITIVE_KEYS = {"authorization", "token", "key", "password", "secret", "cookie", "credential", "admin_key"}
    if isinstance(obj, dict):
        res = {}
        for k, v in obj.items():
            if any(s in str(k).lower() for s in SENSITIVE_KEYS):
                res[k] = "[REDACTED]"
            else:
                res[k] = redact_secrets(v)
        return res
    elif isinstance(obj, list):
        return [redact_secrets(item) for item in obj]
    return obj


def format_bounded_event_details(details: Any) -> str:
    """Format and bound JSON details to <= 64 KiB with secret redaction."""
    redacted = redact_secrets(details)
    raw = json.dumps(redacted, sort_keys=True, separators=(",", ":"))
    if len(raw.encode("utf-8")) > 65536:
        # Bounded truncation
        truncated = {"truncated": True, "error": "Event details exceeded 64 KiB maximum bound"}
        return json.dumps(truncated)
    return raw


class DeploymentService:
    @staticmethod
    async def get_next_generation(session: AsyncSession) -> int:
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
        stmt = select(ArtifactSourceModel).where(ArtifactSourceModel.id == req.id)
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            # Amendment 6: Artifact source immutability if referenced by releases
            ref_stmt = select(ReleaseArtifactModel).where(ReleaseArtifactModel.artifact_source_id == req.id)
            ref_res = await session.execute(ref_stmt)
            referencing_release = ref_res.scalars().first()
            if referencing_release:
                if (
                    existing.base_url != req.base_url
                    or existing.allowed_host != req.allowed_host
                    or existing.ca_policy != req.ca_policy
                    or existing.max_artifact_bytes != req.max_artifact_bytes
                    or existing.allow_private_network != req.allow_private_network
                ):
                    msg = (
                        f"Artifact source '{req.id}' is referenced by existing releases "
                        "and its security properties cannot be altered (source immutability enforced)"
                    )
                    raise ValueError(msg)

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
            target_architecture=normalize_arch(req.target_architecture) or "x86_64",
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
    ) -> List[Tuple[FleetDeviceModel, int, Dict[str, Any]]]:
        # Amendment 9, 10, 11, 12: Fail-closed target filtering, inventory freshness, arch normalization & evidence logging
        freshness_threshold = int(os.getenv("OPENROBO_INVENTORY_FRESHNESS_SEC", "300"))
        now_dt = utc_now()

        stmt = select(FleetDeviceModel).where(FleetDeviceModel.status == "ENROLLED")
        res = await session.execute(stmt)
        all_devices = list(res.scalars().all())

        matched_device_tuples: List[Tuple[FleetDeviceModel, Dict[str, Any]]] = []

        for dev in all_devices:
            # 1. Target Filter explicit match
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

            # 2. Heartbeat Inventory & Freshness Check
            is_fresh = False
            if dev.last_heartbeat_at:
                hb_dt = dev.last_heartbeat_at
                if hb_dt.tzinfo is None:
                    hb_dt = hb_dt.replace(tzinfo=timezone.utc)
                diff_sec = (now_dt - hb_dt).total_seconds()
                is_fresh = diff_sec <= freshness_threshold

            hb = dev.last_heartbeat_json if (is_fresh and isinstance(dev.last_heartbeat_json, dict)) else {}

            dev_os = hb.get("os", "UNKNOWN") if is_fresh else "UNKNOWN"
            dev_arch_raw = hb.get("architecture", "UNKNOWN") if is_fresh else "UNKNOWN"
            dev_arch = normalize_arch(dev_arch_raw) if dev_arch_raw != "UNKNOWN" else "UNKNOWN"
            dev_ros = hb.get("ros_distro", None) if is_fresh else None

            # 3. Fail-Closed Target Compatibility Verification
            req_os = release.target_os
            req_arch = normalize_arch(release.target_architecture)
            req_ros = release.target_ros_distro

            if req_os and (dev_os == "UNKNOWN" or dev_os != req_os):
                continue
            if req_arch and (dev_arch == "UNKNOWN" or dev_arch != req_arch):
                continue
            if req_ros and (dev_ros is None or dev_ros != req_ros):
                continue

            # Target filter OS / arch / ros filters if explicitly set
            if target_filter.os and (dev_os == "UNKNOWN" or dev_os != target_filter.os):
                continue
            if target_filter.architecture and (dev_arch == "UNKNOWN" or dev_arch != normalize_arch(target_filter.architecture)):
                continue
            if target_filter.ros_distro and (dev_ros is None or dev_ros != target_filter.ros_distro):
                continue

            evidence = {
                "device_id": dev.id,
                "domain": dev.domain,
                "robot_type": dev.robot_type,
                "capabilities": dev.capabilities_json or [],
                "os": dev_os,
                "architecture": dev_arch,
                "ros_distro": dev_ros,
                "inventory_observed_at": dev.last_heartbeat_at.isoformat() if dev.last_heartbeat_at else None,
                "matched_selector": "compatibility_verified",
            }
            matched_device_tuples.append((dev, evidence))

        if not matched_device_tuples:
            return []

        def device_sort_key(item: Tuple[FleetDeviceModel, Dict[str, Any]]) -> str:
            raw = f"{deployment_id}:{item[0].id}".encode("utf-8")
            return hashlib.sha256(raw).hexdigest()

        matched_device_tuples.sort(key=device_sort_key)
        total_matched = len(matched_device_tuples)

        device_stage_assignments: List[Tuple[FleetDeviceModel, int, Dict[str, Any]]] = []

        if rollout_strategy.strategy_type == RolloutStrategyType.IMMEDIATE_ALL or not rollout_strategy.stages:
            for dev, ev in matched_device_tuples:
                ev["matched_stage"] = 0
                device_stage_assignments.append((dev, 0, ev))
            return device_stage_assignments

        # Cumulative Canary stage sizing (Amendment 18)
        curr_idx = 0
        for s_idx, stage_cfg in enumerate(rollout_strategy.stages):
            if curr_idx >= total_matched:
                break
            if s_idx == len(rollout_strategy.stages) - 1:
                stage_items = matched_device_tuples[curr_idx:]
                curr_idx = total_matched
            else:
                pct = stage_cfg.target_percentage
                target_cumulative_count = math.ceil(total_matched * pct / 100.0)
                stage_count = max(0, target_cumulative_count - curr_idx)
                stage_items = matched_device_tuples[curr_idx : curr_idx + stage_count]
                curr_idx += stage_count

            for dev, ev in stage_items:
                ev["matched_stage"] = s_idx
                device_stage_assignments.append((dev, s_idx, ev))

        return device_stage_assignments

    @staticmethod
    async def create_deployment(
        session: AsyncSession,
        req: DeploymentCreate,
        created_by: str = "configured-admin",
    ) -> DeploymentModel:
        computed_request_digest = req.compute_request_digest()

        # Amendment 13: Idempotency Request Digest validation
        if req.idempotency_key:
            stmt = select(DeploymentModel).where(DeploymentModel.idempotency_key == req.idempotency_key)
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                if existing.request_digest and existing.request_digest != computed_request_digest:
                    msg = (
                        f"IDEMPOTENCY_CONFLICT: Idempotency key '{req.idempotency_key}' was previously used with "
                        "different deployment request parameters"
                    )
                    raise ValueError(msg)
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
            raise ValueError("No enrolled fleet devices matched the release target requirements and target filter")

        # Amendment 14: Persistent Device Mutation Lease Acquisition
        for dev, _, _ in assignments:
            lease_stmt = select(DeviceDeploymentLeaseModel).where(DeviceDeploymentLeaseModel.device_id == dev.id).with_for_update()
            lease_res = await session.execute(lease_stmt)
            existing_lease = lease_res.scalar_one_or_none()
            if existing_lease:
                dep_check = select(DeploymentModel).where(DeploymentModel.id == existing_lease.deployment_id)
                dep_check_res = await session.execute(dep_check)
                holder_dep = dep_check_res.scalar_one_or_none()
                if holder_dep and holder_dep.status not in (
                    DeploymentState.COMPLETED.value,
                    DeploymentState.CANCELLED.value,
                    DeploymentState.FAILED.value,
                ):
                    raise ValueError(
                        f"Device '{dev.id}' is locked by active deployment '{existing_lease.deployment_id}' (status: {holder_dep.status})"
                    )
                else:
                    await session.delete(existing_lease)

            lease = DeviceDeploymentLeaseModel(
                device_id=dev.id,
                deployment_id=deployment_id,
                generation=generation,
                acquired_at=utc_now(),
                updated_at=utc_now(),
            )
            session.add(lease)

        total_stages = len(req.rollout_strategy.stages) if req.rollout_strategy.stages else 1

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
            status=DeploymentState.STAGE_0_STAGING.value,
            current_stage=0,
            total_stages=total_stages,
            generation=generation,
            version=1,
            idempotency_key=req.idempotency_key,
            request_digest=computed_request_digest,
            created_by=created_by,
        )
        session.add(deployment)
        release.immutable_after_deployment = True

        for dev, stage_idx, ev in assignments:
            dd = DeviceDeploymentModel(
                deployment_id=deployment_id,
                device_id=dev.id,
                stage_index=stage_idx,
                status=DeviceDeploymentState.PENDING.value,
                generation=generation,
                target_snapshot_json=json.dumps(ev, sort_keys=True),
            )
            session.add(dd)

            if stage_idx == 0:
                payload = {
                    "deployment_id": deployment_id,
                    "release_id": release.release_id,
                    "release_version": release.release_version,
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
            details=format_bounded_event_details(
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
                f"Optimistic conflict: expected version {req.expected_version}, but deployment is currently version {deployment.version}"
            )
        if deployment.status != req.expected_state.value:
            raise ValueError(
                f"State mismatch: expected deployment state {req.expected_state.value}, but deployment is currently in {deployment.status}"
            )

        current_stage = deployment.current_stage
        target_state: DeploymentState
        generation = await DeploymentService.get_next_generation(session)
        deployment.generation = generation

        if req.action in (ApprovalAction.APPROVE_ACTIVATION, ApprovalAction.APPROVE_CURRENT_COHORT_ACTIVATION):
            target_state = DeploymentState[f"ACTIVATING_STAGE_{current_stage}"]
            validate_deployment_transition(DeploymentState(deployment.status), target_state)

            dev_stmt = select(DeviceDeploymentModel).where(
                DeviceDeploymentModel.deployment_id == deployment_id,
                DeviceDeploymentModel.stage_index == current_stage,
                DeviceDeploymentModel.status == DeviceDeploymentState.STAGED.value,
            )
            dev_res = await session.execute(dev_stmt)
            for dd in dev_res.scalars().all():
                payload = {
                    "deployment_id": deployment_id,
                    "slot": dd.staged_slot or "slot-b",
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

        elif req.action == ApprovalAction.APPROVE_NEXT_STAGE:
            next_stage = current_stage + 1
            if next_stage >= deployment.total_stages:
                raise ValueError("No further canary stages configured to approve")

            target_state = DeploymentState[f"STAGE_{next_stage}_STAGING"]
            validate_deployment_transition(DeploymentState(deployment.status), target_state)
            deployment.current_stage = next_stage

            snapshot = ReleaseSnapshot.model_validate_json(deployment.release_snapshot_json)

            dev_stmt = select(DeviceDeploymentModel).where(
                DeviceDeploymentModel.deployment_id == deployment_id,
                DeviceDeploymentModel.stage_index == next_stage,
            )
            dev_res = await session.execute(dev_stmt)
            for dd in dev_res.scalars().all():
                payload = {
                    "deployment_id": deployment_id,
                    "release_id": snapshot.release_id,
                    "release_version": snapshot.release_version,
                    "manifest_digest": snapshot.manifest_digest,
                    "artifact_digest": snapshot.artifact_digest,
                    "workspace_digest": snapshot.workspace_digest,
                    "release_key_id": snapshot.release_key_id,
                    "artifact_source_id": snapshot.artifact_source_id,
                    "target_os": snapshot.target_os,
                    "target_architecture": snapshot.target_architecture,
                    "target_ros_distro": snapshot.target_ros_distro,
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
            # Release mutation leases on completion
            await session.execute(delete(DeviceDeploymentLeaseModel).where(DeviceDeploymentLeaseModel.deployment_id == deployment_id))

        elif req.action == ApprovalAction.REJECT_AND_CANCEL:
            target_state = DeploymentState.CANCELLING
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
            details=format_bounded_event_details(
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
    async def pause_deployment(session: AsyncSession, deployment_id: str) -> DeploymentModel:
        stmt = select(DeploymentModel).where(DeploymentModel.id == deployment_id).with_for_update()
        res = await session.execute(stmt)
        deployment = res.scalar_one_or_none()
        if not deployment:
            raise ValueError(f"Deployment '{deployment_id}' not found")

        curr_state = DeploymentState(deployment.status)
        if curr_state in (DeploymentState.COMPLETED, DeploymentState.CANCELLED, DeploymentState.FAILED, DeploymentState.PAUSED):
            raise ValueError(f"Cannot pause deployment in state {curr_state.value}")

        deployment.status = DeploymentState.PAUSED.value
        deployment.version += 1

        event = DeploymentEventModel(
            deployment_id=deployment_id,
            event_type="DEPLOYMENT_PAUSED",
            details=format_bounded_event_details({"previous_state": curr_state.value, "version": deployment.version}),
        )
        session.add(event)
        await session.flush()
        return deployment

    @staticmethod
    async def resume_deployment(session: AsyncSession, deployment_id: str) -> DeploymentModel:
        stmt = select(DeploymentModel).where(DeploymentModel.id == deployment_id).with_for_update()
        res = await session.execute(stmt)
        deployment = res.scalar_one_or_none()
        if not deployment:
            raise ValueError(f"Deployment '{deployment_id}' not found")

        if deployment.status != DeploymentState.PAUSED.value:
            raise ValueError(f"Deployment is not paused (current: {deployment.status})")

        # Resume to current stage state
        curr_stage = deployment.current_stage
        resumed_state = DeploymentState[f"STAGE_{curr_stage}_STAGING"]
        deployment.status = resumed_state.value
        deployment.version += 1

        event = DeploymentEventModel(
            deployment_id=deployment_id,
            event_type="DEPLOYMENT_RESUMED",
            details=format_bounded_event_details({"new_state": resumed_state.value, "version": deployment.version}),
        )
        session.add(event)
        await session.flush()
        return deployment

    @staticmethod
    async def handle_device_status_report(
        session: AsyncSession,
        device_id: str,
        report: DeploymentStatusReport,
    ) -> DeviceDeploymentModel:
        # Amendment 2: Validate instruction_id, deployment_id, device_id, generation
        inst_stmt = select(DeploymentInstructionModel).where(
            DeploymentInstructionModel.id == report.instruction_id,
            DeploymentInstructionModel.deployment_id == report.deployment_id,
            DeploymentInstructionModel.device_id == device_id,
        )
        inst_res = await session.execute(inst_stmt)
        inst = inst_res.scalar_one_or_none()
        if not inst:
            raise ValueError(
                f"No instruction found correlating to report instruction_id '{report.instruction_id}' for device '{device_id}'"
            )

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
            details=format_bounded_event_details(
                {
                    "instruction_id": report.instruction_id,
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
        if not deployment:
            return

        dev_stmt = select(DeviceDeploymentModel).where(
            DeviceDeploymentModel.deployment_id == deployment_id,
        )
        dev_res = await session.execute(dev_stmt)
        all_deployment_devices = list(dev_res.scalars().all())
        if not all_deployment_devices:
            return

        stage_devices = [d for d in all_deployment_devices if d.stage_index == stage_index]
        all_staged = stage_devices and all(
            d.status in (DeviceDeploymentState.STAGED.value, DeviceDeploymentState.ACTIVE.value) for d in stage_devices
        )
        all_active = stage_devices and all(d.status == DeviceDeploymentState.ACTIVE.value for d in stage_devices)
        any_failed = any(d.status == DeviceDeploymentState.FAILED.value for d in stage_devices)

        curr_state = DeploymentState(deployment.status)

        # Handling CANCELLING state
        if curr_state == DeploymentState.CANCELLING:
            all_terminal = all(
                d.status in (DeviceDeploymentState.ACTIVE.value, DeviceDeploymentState.CANCELLED.value, DeviceDeploymentState.FAILED.value)
                for d in all_deployment_devices
            )
            if all_terminal:
                deployment.status = DeploymentState.CANCELLED.value
                deployment.version += 1
                await session.execute(delete(DeviceDeploymentLeaseModel).where(DeviceDeploymentLeaseModel.deployment_id == deployment_id))
            return

        if curr_state == DeploymentState[f"STAGE_{stage_index}_STAGING"] and all_staged:
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
                await session.execute(delete(DeviceDeploymentLeaseModel).where(DeviceDeploymentLeaseModel.deployment_id == deployment_id))
        elif any_failed and not curr_state.value.endswith("_FAILED") and curr_state != DeploymentState.FAILED:
            deployment.status = DeploymentState[f"STAGE_{stage_index}_FAILED"].value
            deployment.version += 1
            await session.execute(delete(DeviceDeploymentLeaseModel).where(DeviceDeploymentLeaseModel.deployment_id == deployment_id))

    @staticmethod
    async def get_pending_instructions_for_device(
        session: AsyncSession,
        device_id: str,
    ) -> List[DeploymentInstructionModel]:
        now_dt = utc_now()
        # Amendment 4: Query PENDING or unacknowledged non-expired retryable SENT
        stmt = (
            select(DeploymentInstructionModel)
            .where(
                DeploymentInstructionModel.device_id == device_id,
                DeploymentInstructionModel.expires_at > now_dt,
                (
                    (DeploymentInstructionModel.status == InstructionStatus.PENDING.value)
                    | (
                        (DeploymentInstructionModel.status == InstructionStatus.SENT.value)
                        & (DeploymentInstructionModel.acknowledged_at.is_(None))
                        & ((DeploymentInstructionModel.next_attempt_at.is_(None)) | (DeploymentInstructionModel.next_attempt_at <= now_dt))
                    )
                ),
            )
            .order_by(DeploymentInstructionModel.generation.asc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_deployment_summary(session: AsyncSession, deployment_id: str) -> Optional[Dict[str, Any]]:
        stmt = select(DeploymentModel).where(DeploymentModel.id == deployment_id)
        res = await session.execute(stmt)
        dep = res.scalar_one_or_none()
        if not dep:
            return None

        dev_stmt = select(DeviceDeploymentModel).where(DeviceDeploymentModel.deployment_id == deployment_id)
        dev_res = await session.execute(dev_stmt)
        devices = list(dev_res.scalars().all())

        strategy = RolloutStrategy.model_validate_json(dep.rollout_strategy)
        total_stages = dep.total_stages

        stages_map: Dict[int, StageSummary] = {}
        for s_idx in range(total_stages):
            target_pct = strategy.stages[s_idx].target_percentage if strategy.stages and s_idx < len(strategy.stages) else 100
            stages_map[s_idx] = StageSummary(stage_index=s_idx, target_percentage=target_pct, total_devices=0)

        for dev in devices:
            s_idx = dev.stage_index
            if s_idx not in stages_map:
                stages_map[s_idx] = StageSummary(stage_index=s_idx, target_percentage=100, total_devices=0)
            stage_sum = stages_map[s_idx]
            stage_sum.total_devices += 1

            st = dev.status.lower()
            if hasattr(stage_sum, st):
                setattr(stage_sum, st, getattr(stage_sum, st) + 1)

        return {
            "deployment": dep,
            "stages": [stages_map[i] for i in sorted(stages_map.keys())],
        }
