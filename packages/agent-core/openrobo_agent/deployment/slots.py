"""A/B Workspace Slot Manager with startup crash reconciliation and pointer verification."""

import json
import os
import shutil
from pathlib import Path
from typing import Literal

from openrobo_agent.deployment.models import ActivationIntent, SlotMetadata, SlotsState, SlotState


class ABSlotManager:
    """Manages slot partitions, active pointers, release evidence, and crash-consistent state transitions."""

    def __init__(self, deployment_root: Path | str) -> None:
        self.deployment_root = Path(deployment_root).resolve()
        self.deployment_root.mkdir(parents=True, exist_ok=True)

        self.slot_a_dir = self.deployment_root / "slot-a"
        self.slot_b_dir = self.deployment_root / "slot-b"
        self.slot_a_dir.mkdir(parents=True, exist_ok=True)
        self.slot_b_dir.mkdir(parents=True, exist_ok=True)

        self.evidence_a_dir = self.deployment_root / "slot-a.release"
        self.evidence_b_dir = self.deployment_root / "slot-b.release"
        self.evidence_a_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_b_dir.mkdir(parents=True, exist_ok=True)

        self.current_link = self.deployment_root / "current"
        self.current_ptr_file = self.deployment_root / "current.ptr"
        self.metadata_file = self.deployment_root / "slots.json"
        self.intent_journal_file = self.deployment_root / "activation.intent.json"

        self.is_windows = os.name == "nt"

        self.state = self._load_or_initialize_state()
        self._reconcile_startup_state()

    def _load_or_initialize_state(self) -> SlotsState:
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return SlotsState.model_validate(data)
            except Exception:
                pass

        return SlotsState(
            active_slot=None,
            slots={
                "slot-a": SlotMetadata(slot_id="slot-a", state=SlotState.EMPTY),
                "slot-b": SlotMetadata(slot_id="slot-b", state=SlotState.EMPTY),
            },
        )

    def _save_state(self) -> None:
        temp_file = self.deployment_root / f"slots.json.tmp.{os.getpid()}"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(self.state.model_dump_json(indent=2))
        os.replace(temp_file, self.metadata_file)

    def _read_filesystem_pointer(self) -> str | None:
        """Reads the active slot referenced by the filesystem pointer (authoritative)."""
        if self.current_link.exists() or self.current_link.is_symlink():
            try:
                target = os.readlink(self.current_link)
                target_name = Path(target).name
                if target_name in ("slot-a", "slot-b"):
                    return target_name
            except Exception:
                pass

        if self.current_ptr_file.exists():
            try:
                with open(self.current_ptr_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content in ("slot-a", "slot-b"):
                    return content
            except Exception:
                pass

        return None

    def _reconcile_startup_state(self) -> None:
        """Reconciles interrupted activation transactions and ensures metadata matches the authoritative pointer."""
        # 1. Check activation transaction journal
        if self.intent_journal_file.exists():
            try:
                with open(self.intent_journal_file, "r", encoding="utf-8") as f:
                    intent_data = json.load(f)
                intent = ActivationIntent.model_validate(intent_data)

                # Check pointer position
                ptr_slot = self._read_filesystem_pointer()
                if ptr_slot == intent.to_slot:
                    # Switch happened on disk; complete the metadata transition
                    self.state.active_slot = intent.to_slot
                    if intent.from_slot and intent.from_slot in self.state.slots:
                        self.state.slots[intent.from_slot].state = SlotState.PREVIOUS
                    if intent.to_slot in self.state.slots:
                        self.state.slots[intent.to_slot].state = SlotState.ACTIVE
                    self._save_state()
                elif intent.from_slot and ptr_slot == intent.from_slot:
                    # Switch did not happen; restore from_slot as ACTIVE, to_slot as VERIFIED/FAILED
                    self.state.active_slot = intent.from_slot
                    if intent.from_slot in self.state.slots:
                        self.state.slots[intent.from_slot].state = SlotState.ACTIVE
                    if intent.to_slot in self.state.slots and self.state.slots[intent.to_slot].state == SlotState.ACTIVE:
                        self.state.slots[intent.to_slot].state = SlotState.VERIFIED
                    self._save_state()

                # Clean up resolved journal
                self.intent_journal_file.unlink(missing_ok=True)
            except Exception:
                pass

        # 2. Reconcile metadata with authoritative filesystem pointer
        fs_active = self._read_filesystem_pointer()
        if fs_active:
            self.state.active_slot = fs_active
            for sid, meta in self.state.slots.items():
                if sid == fs_active and meta.state != SlotState.ACTIVE:
                    meta.state = SlotState.ACTIVE
                elif sid != fs_active and meta.state == SlotState.ACTIVE:
                    meta.state = SlotState.PREVIOUS
            self._save_state()

    def get_slot_dir(self, slot_id: Literal["slot-a", "slot-b"]) -> Path:
        if slot_id == "slot-a":
            return self.slot_a_dir
        elif slot_id == "slot-b":
            return self.slot_b_dir
        raise ValueError(f"Invalid slot ID: {slot_id}")

    def get_evidence_dir(self, slot_id: Literal["slot-a", "slot-b"]) -> Path:
        if slot_id == "slot-a":
            return self.evidence_a_dir
        elif slot_id == "slot-b":
            return self.evidence_b_dir
        raise ValueError(f"Invalid slot ID: {slot_id}")

    def get_active_slot_id(self) -> str | None:
        return self._read_filesystem_pointer() or self.state.active_slot

    def get_inactive_slot_id(self) -> Literal["slot-a", "slot-b"]:
        active = self.get_active_slot_id()
        if active == "slot-a":
            return "slot-b"
        return "slot-a"

    def get_slot_metadata(self, slot_id: str) -> SlotMetadata | None:
        return self.state.slots.get(slot_id)

    def update_slot_metadata(self, slot_id: str, **kwargs) -> SlotMetadata:
        if slot_id not in self.state.slots:
            self.state.slots[slot_id] = SlotMetadata(slot_id=slot_id)
        current = self.state.slots[slot_id]
        updated = current.model_copy(update=kwargs)
        self.state.slots[slot_id] = updated
        self._save_state()
        return updated

    def clear_slot(self, slot_id: Literal["slot-a", "slot-b"]) -> None:
        active = self.get_active_slot_id()
        if active == slot_id:
            raise PermissionError(f"Cannot clear currently ACTIVE slot '{slot_id}'.")

        sdir = self.get_slot_dir(slot_id)
        if sdir.exists():
            shutil.rmtree(sdir)
        sdir.mkdir(parents=True, exist_ok=True)

        edir = self.get_evidence_dir(slot_id)
        if edir.exists():
            shutil.rmtree(edir)
        edir.mkdir(parents=True, exist_ok=True)

        self.update_slot_metadata(
            slot_id,
            state=SlotState.EMPTY,
            release_id=None,
            release_version=None,
            artifact_digest=None,
            manifest_digest=None,
            workspace_digest=None,
            key_id=None,
            installed_at=None,
            verified_at=None,
            activated_at=None,
        )
