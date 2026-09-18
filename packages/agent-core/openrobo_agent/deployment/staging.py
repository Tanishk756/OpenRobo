"""Release staging workflow with quarantine extraction, evidence preservation, and trust store resolution."""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openrobo_release.extraction import SafeArtifactExtractor
from openrobo_release.models import (
    DeploymentSafetyPolicy,
    ReleaseManifest,
    TrustedReleaseKey,
)
from openrobo_release.policy import evaluate_deployment_safety_policy
from openrobo_release.signing import canonical_manifest_bytes
from openrobo_release.trust_store import TrustedReleaseKeyStore
from openrobo_release.verification import ReleaseVerifier

from openrobo_agent.deployment.models import SlotState
from openrobo_agent.deployment.slots import ABSlotManager


def stage_release_artifact(
    manager: ABSlotManager,
    archive_path: Path | str,
    manifest_path: Path | str,
    signature_path: Path | str,
    trust_store: TrustedReleaseKeyStore | None = None,
    dev_public_key: str | None = None,
    allow_dev_key: bool = False,
    safety_policy: DeploymentSafetyPolicy | None = None,
    telemetry: dict[str, Any] | None = None,
    current_ros_distro: str | None = None,
) -> tuple[bool, str]:
    """Stages a signed release archive into an inactive slot after full verification."""
    art_path = Path(archive_path).resolve()
    man_path = Path(manifest_path).resolve()
    sig_path = Path(signature_path).resolve()

    if not art_path.exists():
        return False, f"Archive file does not exist: {art_path}"
    if not man_path.exists():
        return False, f"Manifest file does not exist: {man_path}"
    if not sig_path.exists():
        return False, f"Signature file does not exist: {sig_path}"

    with open(man_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
    manifest = ReleaseManifest.model_validate(manifest_data)

    with open(sig_path, "r", encoding="utf-8") as f:
        detached_sig = f.read().strip()

    with open(art_path, "rb") as f:
        artifact_bytes = f.read()

    # Handle dev key override with strict environment gating (requires ALL 3 gates)
    trusted_keys_list: list[TrustedReleaseKey] = []
    if dev_public_key:
        env_mode = os.environ.get("ENVIRONMENT", "").lower()
        allow_dev_flag = os.environ.get("OPENROBO_ALLOW_DEV_RELEASE_KEY", "").lower() in ("true", "1", "yes")

        if not (allow_dev_key is True and env_mode == "development" and allow_dev_flag):
            return False, (
                "Arbitrary public key override rejected. Requires ENVIRONMENT=development, "
                "OPENROBO_ALLOW_DEV_RELEASE_KEY=true, and explicit allow_dev_key=True. "
                "Production releases must resolve keys from the local trusted release key store."
            )

        trusted_keys_list.append(
            TrustedReleaseKey(
                key_id=manifest.release_key_id,
                public_key=dev_public_key,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        )

    # 1. Pre-flight Cryptographic & Compatibility Verification
    verifier = ReleaseVerifier(trust_store=trust_store, trusted_keys=trusted_keys_list if dev_public_key else None)

    sig_res = verifier.verify_manifest_signature(manifest, detached_sig)
    if not sig_res.is_valid:
        return False, f"Signature verification failed: {sig_res.details} ({sig_res.status.value})"

    dig_res = verifier.verify_artifact_digest(artifact_bytes, manifest)
    if not dig_res.is_valid:
        return False, f"Artifact digest verification failed: {dig_res.details} ({dig_res.status.value})"

    detected_ros = current_ros_distro if current_ros_distro is not None else os.environ.get("ROS_DISTRO")
    tgt_res = verifier.verify_target_compatibility(manifest, current_ros_distro=detected_ros)
    if not tgt_res.is_valid:
        return False, f"Target environment incompatible: {tgt_res.details} ({tgt_res.status.value})"

    # 2. Safety Policy Pre-check
    if safety_policy:
        safe, reason = evaluate_deployment_safety_policy(safety_policy, telemetry)
        if not safe:
            return False, f"Deployment safety policy pre-check failed: {reason}"

    # 3. Safe Extraction into Inactive Slot
    inactive_slot = manager.get_inactive_slot_id()
    slot_dir = manager.get_slot_dir(inactive_slot)
    evidence_dir = manager.get_evidence_dir(inactive_slot)

    manager.update_slot_metadata(inactive_slot, state=SlotState.STAGING)

    extractor = SafeArtifactExtractor(allow_symlinks=False, allow_hardlinks=False)
    try:
        extractor.extract_and_verify(
            archive_path=art_path,
            target_dir=slot_dir,
            manifest=manifest,
            strict_mode=True,
        )
    except Exception as e:
        manager.update_slot_metadata(inactive_slot, state=SlotState.FAILED)
        return False, f"Extraction failed: {e}"

    # 4. Save Release Evidence for Future Rollback Integrity Verification
    try:
        with open(evidence_dir / "manifest.json", "w", encoding="utf-8") as f:
            f.write(manifest.model_dump_json(indent=2))
        with open(evidence_dir / "signature.sig", "w", encoding="utf-8") as f:
            f.write(detached_sig)
        with open(evidence_dir / "key_id", "w", encoding="utf-8") as f:
            f.write(manifest.release_key_id)
    except Exception as e:
        manager.update_slot_metadata(inactive_slot, state=SlotState.FAILED)
        return False, f"Failed to persist release evidence: {e}"

    # 5. Compute distinct manifest digest and mark slot as VERIFIED
    now_str = datetime.now(timezone.utc).isoformat()
    manifest_digest = hashlib.sha256(canonical_manifest_bytes(manifest)).hexdigest()

    manager.update_slot_metadata(
        inactive_slot,
        state=SlotState.VERIFIED,
        release_id=manifest.release_id,
        release_version=manifest.release_version,
        artifact_digest=manifest.artifact_digest,
        manifest_digest=manifest_digest,
        workspace_digest=manifest.workspace_digest,
        key_id=manifest.release_key_id,
        installed_at=now_str,
        verified_at=now_str,
    )

    return True, f"Release {manifest.release_id} staged and VERIFIED in {inactive_slot}"
