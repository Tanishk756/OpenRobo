# Authoritative local trusted artifact source registry for OpenRobo Agent.

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Union


@dataclass
class TrustedArtifactSource:
    id: str
    base_url: str
    allowed_host: str
    allow_private_network: bool = False
    max_artifact_bytes: int = 104857600  # 100 MB default
    ca_cert_path: Optional[str] = None

    @property
    def source_id(self) -> str:
        return self.id


class TrustedArtifactSourceRegistry:
    """Authoritative local store of trusted artifact sources for an agent."""

    def __init__(self, sources_or_path: Optional[Union[Dict[str, TrustedArtifactSource], Path, str]] = None):
        self._sources: Dict[str, TrustedArtifactSource] = {}
        self._file_path: Optional[Path] = None

        if isinstance(sources_or_path, (Path, str)):
            self._file_path = Path(sources_or_path)
            self._load()
        elif isinstance(sources_or_path, dict):
            self._sources = dict(sources_or_path)

    def _load(self) -> None:
        if self._file_path and self._file_path.exists():
            try:
                with open(self._file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("sources", []):
                    src_id = item.get("id") or item.get("source_id")
                    src = TrustedArtifactSource(
                        id=src_id,
                        base_url=item["base_url"],
                        allowed_host=item["allowed_host"],
                        allow_private_network=item.get("allow_private_network", False),
                        max_artifact_bytes=item.get("max_artifact_bytes", 104857600),
                        ca_cert_path=item.get("ca_cert_path"),
                    )
                    self._sources[src.id] = src
            except Exception:
                pass

    def _save(self) -> None:
        if self._file_path:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "sources": [
                    {
                        "id": s.id,
                        "base_url": s.base_url,
                        "allowed_host": s.allowed_host,
                        "allow_private_network": s.allow_private_network,
                        "max_artifact_bytes": s.max_artifact_bytes,
                        "ca_cert_path": s.ca_cert_path,
                    }
                    for s in self._sources.values()
                ]
            }
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    def register(self, source: TrustedArtifactSource) -> None:
        self._sources[source.id] = source
        self._save()

    def register_source(self, source: TrustedArtifactSource) -> None:
        self.register(source)

    def get(self, source_id: str) -> Optional[TrustedArtifactSource]:
        return self._sources.get(source_id)

    def get_source(self, source_id: str) -> Optional[TrustedArtifactSource]:
        return self.get(source_id)

    def require(self, source_id: str) -> TrustedArtifactSource:
        source = self.get(source_id)
        if not source:
            raise ValueError(f"Artifact source '{source_id}' is not in the agent's trusted source registry")
        return source

    @classmethod
    def from_file(cls, registry_file: Path) -> "TrustedArtifactSourceRegistry":
        return cls(registry_file)
