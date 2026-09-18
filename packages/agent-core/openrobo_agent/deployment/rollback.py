"""Mechanical rollback primitive to previous known-good workspace slot."""

from datetime import datetime, timezone
from typing import Optional, Tuple

from openrobo_agent.deployment.models import SlotMetadata, SlotState
from openrobo_agent.deployment.slots import ABSlotManager


def rollback_to_previous(
    slot_manager: ABSlotManager,
) -> Tuple[bool, str, Optional[SlotMetadata]]:
    """
    Execute local mechanical rollback to the preserved PREVIOUS workspace slot.

    Guarantees:
    - Verifies previous slot metadata and directory existence
    - Performs atomic pointer switch
    - Marks previous slot as ACTIVE
    - Marks faulted slot as FAILED
    """
    prev_slot_id = slot_manager.get_previous_slot()
    if not prev_slot_id:
        return False, "Rollback failed: No slot with 'PREVIOUS' status available.", None

    prev_meta = slot_manager.get_slot_metadata(prev_slot_id)
    prev_dir = slot_manager.slot_paths[prev_slot_id]

    if not prev_dir.exists() or not any(prev_dir.iterdir()):
        return False, f"Rollback failed: Previous slot '{prev_slot_id}' directory is empty or missing.", None

    current_active_id = slot_manager.get_active_slot()
    current_meta = slot_manager.get_slot_metadata(current_active_id) if current_active_id else None

    # Perform Atomic Pointer Switch back to previous slot
    try:
        slot_manager.switch_active_pointer(prev_slot_id)
    except Exception as e:
        return False, f"Atomic rollback pointer switch failed: {e}", None

    now_iso = datetime.now(timezone.utc).isoformat()

    # Demote faulted slot to FAILED
    if current_meta and current_active_id != prev_slot_id:
        current_meta.status = SlotState.FAILED
        current_meta.details["failed_reason"] = "Rolled back to previous release"
        slot_manager.update_slot_metadata(current_meta)

    # Promote previous slot to ACTIVE
    prev_meta.status = SlotState.ACTIVE
    prev_meta.activated_at = now_iso
    slot_manager.update_slot_metadata(prev_meta)

    return True, f"Successfully rolled back to release '{prev_meta.release_id}' on {prev_slot_id}.", prev_meta
