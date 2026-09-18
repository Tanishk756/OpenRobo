"""Release artifact staging workflow into inactive A/B workspace partitions."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from openrobo_release.extraction import SafeArtifactExtractor
from openrobo_release.models import DeploymentSafetyPolicy, ReleaseManifest
from openrobo_release.policy import evaluate_deployment_safety_policy
from openrobo_release.verification import ReleaseVerifier

from openrobo_agent.deployment.models import SlotMetadata, SlotState
from openrobo_agent.deployment.slots import ABSlotManager


def stage_release_artifact(
    slot_manager: ABSlotManager,
    archive_path: Path,
    manifest: ReleaseManifest,
    signature_b64: str,
    verifier: ReleaseVerifier,
    agent_capabilities: Optional[Dict[str, Any]] = None,
    safety_policy: Optional[DeploymentSafetyPolicy] = None,
    telemetry_state: Optional[Dict[str, Any]] = None,
    extractor: Optional[SafeArtifactExtractor] = None,
) -> Tuple[bool, str, Optional[SlotMetadata]]:
    """
    Execute full pre-flight verification, safe quarantine extraction, and post-extraction validation
    into the inactive workspace slot.
    """
    # 1. Pre-Extraction Cryptographic & Compatibility Verification
    verify_res = verifier.verify_release(
        manifest=manifest,
        signature_b64=signature_b64,
        artifact_path=archive_path,
        agent_capabilities=agent_capabilities,
    )
    if not verify_res.is_valid:
        return False, f"Staging blocked: {verify_res.message}", None

    # 2. Pre-Flight Safety Policy Evaluation (if configured)
    if safety_policy is not None:
        state = telemetry_state or {}
        safe_ok, safe_msg, safe_details = evaluate_deployment_safety_policy(safety_policy, state)
        if not safe_ok:
            return False, f"Staging blocked by safety policy: {safe_msg}", None

    # 3. Select Inactive Slot and Prepare Directory
    inactive_slot_id = slot_manager.get_inactive_slot()
    staging_dir = slot_manager.prepare_staging_slot(inactive_slot_id)

    # 4. Safe Archive Extraction with Strict File-List Verification
    ext = extractor or SafeArtifactExtractor()
    ext_ok, ext_msg, ext_details = ext.extract_archive(
        archive_path=archive_path,
        target_dir=staging_dir,
        manifest=manifest,
        strict_file_list=True,
    )
    if not ext_ok:
        # Mark slot as FAILED on extraction error
        fail_meta = SlotMetadata(
            slot_id=inactive_slot_id,
            release_id=manifest.release_id,
            release_version=manifest.release_version,
            status=SlotState.FAILED,
            details={"error": ext_msg, "details": ext_details},
        )
        slot_manager.update_slot_metadata(fail_meta)
        return False, f"Extraction failed: {ext_msg}", fail_meta

    # 5. Transition Slot Metadata to STAGED / VERIFIED
    now_iso = datetime.now(timezone.utc).isoformat()
    meta = SlotMetadata(
        slot_id=inactive_slot_id,
        release_id=manifest.release_id,
        release_version=manifest.release_version,
        artifact_digest=manifest.artifact_digest,
        manifest_digest=verify_res.manifest_digest,
        workspace_digest=manifest.workspace_digest,
        installed_at=now_iso,
        verified_at=now_iso,
        status=SlotState.STAGED,
        details={
            "files_count": len(manifest.files),
            "target": manifest.target.model_dump(),
        },
    )
    slot_manager.update_slot_metadata(meta)

    return True, f"Release '{manifest.release_id}' successfully staged into {inactive_slot_id}.", meta
