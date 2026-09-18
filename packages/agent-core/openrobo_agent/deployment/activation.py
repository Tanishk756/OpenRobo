"""Atomic activation of verified staged workspace slots."""

from datetime import datetime, timezone
from typing import Optional, Tuple

from openrobo_agent.deployment.models import SlotMetadata, SlotState
from openrobo_agent.deployment.slots import ABSlotManager


def activate_staged_slot(
    slot_manager: ABSlotManager,
    target_slot_id: Optional[str] = None,
) -> Tuple[bool, str, Optional[SlotMetadata]]:
    """
    Atomically switch active workspace pointer to the staged slot, transitioning the prior active
    slot to PREVIOUS (preserved as a verified rollback candidate).
    """
    # 1. Identify Target Staged Slot
    if target_slot_id is None:
        # Auto-detect slot with STAGED or VERIFIED status
        candidates = []
        for sid in slot_manager.SLOT_IDS:
            meta = slot_manager.get_slot_metadata(sid)
            if meta.status in (SlotState.STAGED, SlotState.VERIFIED):
                candidates.append(sid)

        if not candidates:
            return False, "No staged or verified workspace slot found for activation.", None
        if len(candidates) > 1:
            return False, f"Ambiguous staging state: multiple slots staged ({candidates}).", None
        target_slot_id = candidates[0]

    target_meta = slot_manager.get_slot_metadata(target_slot_id)
    if target_meta.status not in (SlotState.STAGED, SlotState.VERIFIED):
        return False, f"Slot '{target_slot_id}' is in state '{target_meta.status}'; must be STAGED or VERIFIED.", None

    # 2. Identify Current Active Slot (if any)
    prior_active_id = slot_manager.get_active_slot()
    prior_meta = slot_manager.get_slot_metadata(prior_active_id) if prior_active_id else None

    # 3. Perform Atomic Pointer Switch
    try:
        slot_manager.switch_active_pointer(target_slot_id)
    except Exception as e:
        return False, f"Atomic activation switch failed: {e}", None

    now_iso = datetime.now(timezone.utc).isoformat()

    # 4. Demote Prior Active Slot to PREVIOUS (Do NOT delete files)
    if prior_meta is not None and prior_active_id != target_slot_id:
        prior_meta.status = SlotState.PREVIOUS
        slot_manager.update_slot_metadata(prior_meta)

    # 5. Promote Target Slot to ACTIVE
    target_meta.status = SlotState.ACTIVE
    target_meta.activated_at = now_iso
    target_meta.previous_release_id = prior_meta.release_id if prior_meta else None
    slot_manager.update_slot_metadata(target_meta)

    return True, f"Workspace slot '{target_slot_id}' successfully activated.", target_meta
