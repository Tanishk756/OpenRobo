"""Agent-side trusted release key store for signature verification."""

import json
from pathlib import Path

from openrobo_release.models import KeyStatus, TrustedReleaseKey


class TrustedReleaseKeyStore:
    """Manages trusted public release signing keys on the agent."""

    def __init__(self, trust_dir: Path | str | None = None, initial_keys: list[TrustedReleaseKey] | None = None) -> None:
        self.trust_dir = Path(trust_dir) if trust_dir else None
        self._keys: dict[str, TrustedReleaseKey] = {}

        if initial_keys:
            for k in initial_keys:
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
                self._keys[key.key_id] = key
            except Exception:
                continue

    def add_key(self, key: TrustedReleaseKey, persist: bool = True) -> None:
        """Adds a trusted release key to the store."""
        self._keys[key.key_id] = key
        if persist and self.trust_dir:
            self.trust_dir.mkdir(parents=True, exist_ok=True)
            key_file = self.trust_dir / f"{key.key_id}.json"
            with open(key_file, "w", encoding="utf-8") as f:
                f.write(key.model_dump_json(indent=2))

    def revoke_key(self, key_id: str, revoked_at: str | None = None, persist: bool = True) -> bool:
        """Marks a trusted release key as REVOKED."""
        if key_id not in self._keys:
            return False
        key = self._keys[key_id]
        updated = key.model_copy(update={"status": KeyStatus.REVOKED, "revoked_at": revoked_at or "2026-09-18T00:00:00Z"})
        self._keys[key_id] = updated
        if persist and self.trust_dir:
            key_file = self.trust_dir / f"{key_id}.json"
            with open(key_file, "w", encoding="utf-8") as f:
                f.write(updated.model_dump_json(indent=2))
        return True

    def get_trusted_key(self, key_id: str) -> TrustedReleaseKey | None:
        """Retrieves a trusted release key by its ID."""
        return self._keys.get(key_id)

    def list_keys(self) -> list[TrustedReleaseKey]:
        """Lists all trusted release keys in the store."""
        return list(self._keys.values())
