"""A/B Workspace Slot Manager with atomic pointer activation and crash-consistent state tracking."""

import json
import os
import shutil
from pathlib import Path
from typing import List, Optional

from openrobo_agent.deployment.models import SlotMetadata, SlotState


class ABSlotManager:
    """
    Manages dual A/B workspace partitions ('slot-a', 'slot-b') and atomic 'current' symlink switching.
    """

    SLOT_IDS: List[str] = ["slot-a", "slot-b"]

    def __init__(self, workspaces_dir: Path):
        self.workspaces_dir = Path(workspaces_dir).resolve()
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)

        self.slot_paths = {
            "slot-a": self.workspaces_dir / "slot-a",
            "slot-b": self.workspaces_dir / "slot-b",
        }
        self.meta_paths = {
            "slot-a": self.workspaces_dir / "slot-a.meta.json",
            "slot-b": self.workspaces_dir / "slot-b.meta.json",
        }
        self.current_link = self.workspaces_dir / "current"

        # Initialize slot directories and metadata if missing
        for slot_id in self.SLOT_IDS:
            self.slot_paths[slot_id].mkdir(parents=True, exist_ok=True)
            if not self.meta_paths[slot_id].exists():
                self._save_slot_meta(SlotMetadata(slot_id=slot_id, status=SlotState.EMPTY))

    def _load_slot_meta(self, slot_id: str) -> SlotMetadata:
        meta_path = self.meta_paths[slot_id]
        if not meta_path.exists():
            return SlotMetadata(slot_id=slot_id, status=SlotState.EMPTY)
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            return SlotMetadata(**data)
        except Exception:
            return SlotMetadata(slot_id=slot_id, status=SlotState.FAILED)

    def _save_slot_meta(self, meta: SlotMetadata) -> None:
        meta_path = self.meta_paths[meta.slot_id]
        temp_path = meta_path.with_suffix(".tmp")
        temp_path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")
        os.replace(temp_path, meta_path)

    def get_slot_metadata(self, slot_id: str) -> SlotMetadata:
        """Retrieve current metadata for a specific slot."""
        if slot_id not in self.SLOT_IDS:
            raise ValueError(f"Invalid slot identifier '{slot_id}'. Must be one of {self.SLOT_IDS}")
        return self._load_slot_meta(slot_id)

    def update_slot_metadata(self, meta: SlotMetadata) -> None:
        """Persist updated metadata for a specific slot."""
        self._save_slot_meta(meta)

    def get_active_slot(self) -> Optional[str]:
        """Determine currently active slot from metadata and current pointer."""
        # 1. Inspect metadata for ACTIVE status
        active_candidates = []
        for slot_id in self.SLOT_IDS:
            meta = self._load_slot_meta(slot_id)
            if meta.status == SlotState.ACTIVE:
                active_candidates.append(slot_id)

        if len(active_candidates) == 1:
            return active_candidates[0]

        # 2. Check current link if resolution needed
        if self.current_link.exists() or self.current_link.is_symlink():
            try:
                target = self.current_link.resolve()
                for slot_id, s_path in self.slot_paths.items():
                    if target == s_path.resolve():
                        return slot_id
            except Exception:
                pass

        return active_candidates[0] if active_candidates else None

    def get_inactive_slot(self) -> str:
        """Return the slot that is NOT currently active."""
        active = self.get_active_slot()
        if active == "slot-a":
            return "slot-b"
        return "slot-a"

    def get_previous_slot(self) -> Optional[str]:
        """Return slot currently marked as PREVIOUS (rollback candidate)."""
        for slot_id in self.SLOT_IDS:
            meta = self._load_slot_meta(slot_id)
            if meta.status == SlotState.PREVIOUS:
                return slot_id
        return None

    def prepare_staging_slot(self, slot_id: str) -> Path:
        """Clear inactive slot directory and mark status as STAGING."""
        if slot_id not in self.SLOT_IDS:
            raise ValueError(f"Invalid slot ID '{slot_id}'")

        active = self.get_active_slot()
        if slot_id == active:
            raise RuntimeError(f"Cannot prepare active slot '{slot_id}' for staging. Active slot is protected.")

        slot_dir = self.slot_paths[slot_id]
        if slot_dir.exists():
            shutil.rmtree(slot_dir)
        slot_dir.mkdir(parents=True, exist_ok=True)

        meta = SlotMetadata(slot_id=slot_id, status=SlotState.STAGING)
        self._save_slot_meta(meta)
        return slot_dir

    def switch_active_pointer(self, target_slot_id: str) -> None:
        """
        Atomically point 'current' symlink / junction to the target slot.
        """
        temp_link = self.workspaces_dir / "current.tmp"

        # Remove existing temp link if lingering from previous crash
        if temp_link.exists() or temp_link.is_symlink():
            try:
                if temp_link.is_dir() and not temp_link.is_symlink():
                    shutil.rmtree(temp_link)
                else:
                    temp_link.unlink()
            except Exception:
                pass

        try:
            # Create relative symlink if supported
            os.symlink(target_slot_id, temp_link, target_is_directory=True)
            os.replace(temp_link, self.current_link)
        except (OSError, NotImplementedError, Exception):
            # Fallback for Windows environments without developer mode / symlink privileges:
            # Copy or directory link pointer
            if self.current_link.exists() or self.current_link.is_symlink():
                try:
                    if self.current_link.is_dir() and not self.current_link.is_symlink():
                        shutil.rmtree(self.current_link)
                    else:
                        self.current_link.unlink()
                except Exception:
                    pass
            try:
                os.symlink(target_slot_id, self.current_link, target_is_directory=True)
            except Exception:
                # If symlink creation fails completely on Windows, persist pointer text file
                pointer_file = self.workspaces_dir / "current.ptr"
                temp_ptr = self.workspaces_dir / "current.ptr.tmp"
                temp_ptr.write_text(target_slot_id, encoding="utf-8")
                os.replace(temp_ptr, pointer_file)
