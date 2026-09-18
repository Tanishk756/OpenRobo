"""Rollback primitive with stored release signature re-verification, revocation checks, and content hashing."""

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

from openrobo_release.models import (
    DeploymentSafetyPolicy,
    KeyStatus,
    ReleaseManifest,
)
from openrobo_release.policy import evaluate_deployment_safety_policy
from openrobo_release.trust_store import TrustedReleaseKeyStore
from openrobo_release.verification import ReleaseVerifier

from openrobo_agent.deployment.models import ActivationIntent, SlotState
from openrobo_agent.deployment.slots import ABSlotManager


def rollback_to_previous(
    manager: ABSlotManager,
    trust_store: TrustedReleaseKeyStore,
    safety_policy: DeploymentSafetyPolicy | None = None,
    telemetry: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Rolls back the active partition to the PREVIOUS slot after comprehensive integrity and revocation verification."""
    current_active = manager.get_active_slot_id()
    if not current_active:
        return False, "Cannot rollback: no active slot is currently identified."

    # Identify previous slot
    prev_slot_id: str | None = None
    for sid, meta in manager.state.slots.items():
        if sid != current_active and meta.state == SlotState.PREVIOUS:
            prev_slot_id = sid
            break

    if not prev_slot_id:
        return False, "Cannot rollback: no valid PREVIOUS slot partition found."

    prev_slot_dir = manager.get_slot_dir(prev_slot_id)  # type: ignore
    prev_evidence_dir = manager.get_evidence_dir(prev_slot_id)  # type: ignore

    manifest_file = prev_evidence_dir / "manifest.json"
    sig_file = prev_evidence_dir / "signature.sig"

    if not manifest_file.exists() or not sig_file.exists():
        manager.update_slot_metadata(prev_slot_id, state=SlotState.FAILED)
        return False, f"Rollback blocked: missing release verification evidence in {prev_evidence_dir}"

    # 1. Load Stored Manifest & Signature
    try:
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
        manifest = ReleaseManifest.model_validate(manifest_data)
        with open(sig_file, "r", encoding="utf-8") as f:
            detached_sig = f.read().strip()
    except Exception as e:
        manager.update_slot_metadata(prev_slot_id, state=SlotState.FAILED)
        return False, f"Rollback blocked: failed to parse stored release evidence: {e}"

    # 2. Check Key Revocation in Trust Store
    trusted_key = trust_store.get_trusted_key(manifest.release_key_id)
    if not trusted_key:
        manager.update_slot_metadata(prev_slot_id, state=SlotState.QUARANTINED)
        return False, f"Rollback blocked: signing key '{manifest.release_key_id}' is no longer in the trusted release key store."

    if trusted_key.status == KeyStatus.REVOKED:
        manager.update_slot_metadata(prev_slot_id, state=SlotState.QUARANTINED)
        return False, f"Rollback blocked: signing key '{manifest.release_key_id}' for previous release has been revoked."

    # 3. Cryptographic Signature Re-verification
    verifier = ReleaseVerifier(trust_store=trust_store)
    sig_res = verifier.verify_manifest_signature(manifest, detached_sig)
    if not sig_res.is_valid:
        manager.update_slot_metadata(prev_slot_id, state=SlotState.FAILED)
        return False, f"Rollback blocked: signature verification of previous manifest failed: {sig_res.details}"

    # 4. Full File-by-File Hash Re-verification of Previous Slot Directory
    manifest_map = {f.path.replace("\\", "/"): f.sha256 for f in manifest.files}
    for rel_path, expected_sha in manifest_map.items():
        file_path = prev_slot_dir / rel_path
        if not file_path.exists():
            manager.update_slot_metadata(prev_slot_id, state=SlotState.QUARANTINED)
            return False, f"Rollback blocked: previous slot is corrupted; missing file '{rel_path}'."
        with open(file_path, "rb") as fp:
            content = fp.read()
        actual_sha = hashlib.sha256(content).hexdigest()
        if actual_sha != expected_sha:
            manager.update_slot_metadata(prev_slot_id, state=SlotState.QUARANTINED)
            return False, f"Rollback blocked: previous slot content tampered; hash mismatch on '{rel_path}'."

    # 5. Fresh Safety Evaluation
    if safety_policy:
        safe, reason = evaluate_deployment_safety_policy(safety_policy, telemetry)
        if not safe:
            return False, f"Rollback blocked by safety policy: {reason}"

    # 6. Execute Crash-Consistent Pointer Switch
    now_str = datetime.now(timezone.utc).isoformat()
    journal_file = manager.intent_journal_file
    temp_journal = manager.deployment_root / f"activation.intent.json.tmp.{os.getpid()}"

    intent = ActivationIntent(
        transaction_id=f"tx-rollback-{os.getpid()}",
        from_slot=current_active,
        to_slot=prev_slot_id,
        release_id=manifest.release_id,
        state="PENDING",
        created_at=now_str,
    )

    with open(temp_journal, "w", encoding="utf-8") as f:
        f.write(intent.model_dump_json(indent=2))
    os.replace(temp_journal, journal_file)

    current_link = manager.current_link
    current_next = manager.deployment_root / "current.next"

    if manager.is_windows:
        with open(manager.current_ptr_file, "w", encoding="utf-8") as f:
            f.write(prev_slot_id)
    else:
        if current_next.exists() or current_next.is_symlink():
            current_next.unlink()
        os.symlink(prev_slot_dir, current_next)
        os.replace(current_next, current_link)

    # 7. Update Metadata
    manager.state.active_slot = prev_slot_id
    manager.state.slots[current_active].state = SlotState.FAILED
    manager.update_slot_metadata(
        prev_slot_id,
        state=SlotState.ACTIVE,
        activated_at=now_str,
    )

    journal_file.unlink(missing_ok=True)
    return True, f"Successfully rolled back from '{current_active}' to '{prev_slot_id}' (release: {manifest.release_id})"
