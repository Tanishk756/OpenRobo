"""Agent-side trusted release key store for signature verification."""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from openrobo_release.models import KeyStatus, TrustedReleaseKey

KEY_ID_REGEX = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def validate_key_id(key_id: str) -> None:
    """Validates that a key_id contains only safe path-invariant characters."""
    if not key_id or not isinstance(key_id, str) or not KEY_ID_REGEX.match(key_id):
        raise ValueError(f"Invalid or unsafe key_id '{key_id}'. Key IDs must match ^[A-Za-z0-9._-]{{1,64}}$")
    if ".." in key_id or "/" in key_id or "\\" in key_id:
        raise ValueError(f"Unsafe path characters in key_id: '{key_id}'")


class TrustedReleaseKeyStore:
    """Manages trusted public release signing keys on the agent."""

    def __init__(self, trust_dir: Path | str | None = None, initial_keys: list[TrustedReleaseKey] | None = None) -> None:
        self.trust_dir = Path(trust_dir) if trust_dir else None
        self._keys: dict[str, TrustedReleaseKey] = {}

        if initial_keys:
            for k in initial_keys:
                validate_key_id(k.key_id)
                self._keys[k.key_id] = k

        if self.trust_dir and self.trust_dir.exists():
            self.load_keys()

    def load_keys(self) -> None:
        """Loads all trusted keys from the trust directory."""
        if not self.trust_dir or not self.trust_dir.exists():
            return

        for key_file in self.trust_dir.glob("*.json"):
            try:
                with open(key_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                key = TrustedReleaseKey.model_validate(data)
                validate_key_id(key.key_id)
                self._keys[key.key_id] = key
            except Exception:
                continue

    def add_key(self, key: TrustedReleaseKey, persist: bool = True) -> None:
        """Adds a trusted release key to the store."""
        validate_key_id(key.key_id)
        self._keys[key.key_id] = key
        if persist and self.trust_dir:
            self.trust_dir.mkdir(parents=True, exist_ok=True)
            key_file = self.trust_dir / f"{key.key_id}.json"
            tmp_file = self.trust_dir / f"{key.key_id}.tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(key.model_dump_json(indent=2))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, key_file)

    def revoke_key(self, key_id: str, revoked_at: str | None = None, persist: bool = True) -> bool:
        """Marks a trusted release key as REVOKED."""
        validate_key_id(key_id)
        if key_id not in self._keys:
            return False
        key = self._keys[key_id]
        revocation_time = revoked_at or datetime.now(timezone.utc).isoformat()
        updated = key.model_copy(update={"status": KeyStatus.REVOKED, "revoked_at": revocation_time})
        self._keys[key_id] = updated
        if persist and self.trust_dir:
            key_file = self.trust_dir / f"{key_id}.json"
            tmp_file = self.trust_dir / f"{key_id}.tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(updated.model_dump_json(indent=2))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, key_file)
        return True

    def get_trusted_key(self, key_id: str) -> TrustedReleaseKey | None:
        """Retrieves a trusted release key by its ID."""
        try:
            validate_key_id(key_id)
        except ValueError:
            return None
        return self._keys.get(key_id)

    def list_keys(self) -> list[TrustedReleaseKey]:
        """Lists all trusted release keys in the store."""
        return list(self._keys.values())
