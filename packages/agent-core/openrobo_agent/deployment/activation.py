"""Atomic, crash-consistent slot activation with pre-switch safety re-evaluation and transaction journaling."""

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from openrobo_release.models import DeploymentSafetyPolicy
from openrobo_release.policy import evaluate_deployment_safety_policy

from openrobo_agent.deployment.models import ActivationIntent, SlotState
from openrobo_agent.deployment.slots import ABSlotManager


def activate_staged_slot(
    manager: ABSlotManager,
    slot_id: Literal["slot-a", "slot-b"] | None = None,
    safety_policy: DeploymentSafetyPolicy | None = None,
    telemetry: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Atomically activates a VERIFIED slot partition using a crash-consistent transaction journal."""
    target_slot = slot_id or manager.get_inactive_slot_id()
    metadata = manager.get_slot_metadata(target_slot)

    if not metadata or metadata.state != SlotState.VERIFIED:
        curr_st = metadata.state if metadata else "NOT_FOUND"
        return False, f"Slot '{target_slot}' cannot be activated: state is '{curr_st}', expected 'VERIFIED'."

    # 1. Fresh Safety Evaluation immediately before switch
    if safety_policy:
        safe, reason = evaluate_deployment_safety_policy(safety_policy, telemetry)
        if not safe:
            return False, f"Activation blocked by fresh safety policy evaluation: {reason}"

    from_slot = manager.get_active_slot_id()
    release_id = metadata.release_id or "unknown"
    transaction_id = f"tx-{uuid.uuid4().hex[:12]}"
    now_str = datetime.now(timezone.utc).isoformat()

    intent = ActivationIntent(
        transaction_id=transaction_id,
        from_slot=from_slot,
        to_slot=target_slot,
        release_id=release_id,
        state="PENDING",
        created_at=now_str,
    )

    # 2. Write Transaction Journal
    journal_file = manager.intent_journal_file
    temp_journal = manager.deployment_root / f"activation.intent.json.tmp.{os.getpid()}"
    with open(temp_journal, "w", encoding="utf-8") as f:
        f.write(intent.model_dump_json(indent=2))
    os.replace(temp_journal, journal_file)

    target_dir = manager.get_slot_dir(target_slot)
    current_link = manager.current_link
    current_next = manager.deployment_root / "current.next"

    # 3. Perform Atomic Filesystem Switch
    switched_pointer = False
    try:
        if manager.is_windows:
            # Windows fallback pointer
            with open(manager.current_ptr_file, "w", encoding="utf-8") as f:
                f.write(target_slot)
            switched_pointer = True
        else:
            # POSIX atomic symlink replacement
            if current_next.exists() or current_next.is_symlink():
                current_next.unlink()
            os.symlink(target_dir, current_next)
            os.replace(current_next, current_link)
            switched_pointer = True
    except Exception:
        if not switched_pointer:
            # Attempt Windows fallback pointer if symlink failed
            try:
                with open(manager.current_ptr_file, "w", encoding="utf-8") as f:
                    f.write(target_slot)
                switched_pointer = True
            except Exception as e2:
                journal_file.unlink(missing_ok=True)
                return False, f"Filesystem pointer switch failed: {e2}"

    # 4. Update Journal to SWITCHED
    intent.state = "SWITCHED"
    with open(temp_journal, "w", encoding="utf-8") as f:
        f.write(intent.model_dump_json(indent=2))
    os.replace(temp_journal, journal_file)

    # 5. Update Partition Slot Metadata
    manager.state.active_slot = target_slot
    if from_slot and from_slot in manager.state.slots:
        manager.state.slots[from_slot].state = SlotState.PREVIOUS

    manager.update_slot_metadata(
        target_slot,
        state=SlotState.ACTIVE,
        activated_at=now_str,
        previous_release_id=manager.state.slots[from_slot].release_id if from_slot and from_slot in manager.state.slots else None,
    )

    # 6. Clean up Completed Journal
    journal_file.unlink(missing_ok=True)

    return True, f"Slot '{target_slot}' atomically activated (release: {release_id})"
