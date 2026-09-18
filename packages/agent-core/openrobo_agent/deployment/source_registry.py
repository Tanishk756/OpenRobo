# Authoritative local trusted artifact source registry for OpenRobo Agent.

import json
import logging
import os
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Union

logger = logging.getLogger("openrobo.agent.source_registry")


class SourceRegistryError(Exception):
    pass


class SourceRegistryCorruptedError(SourceRegistryError):
    """Raised when persisted artifact sources file exists but cannot be safely parsed or contains invalid entries."""

    pass


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
            for k, v in sources_or_path.items():
                self._validate_source(v)
                self._sources[k] = v

    def _validate_source(self, source: TrustedArtifactSource) -> None:
        if not source.id or not isinstance(source.id, str) or not source.id.strip():
            raise SourceRegistryCorruptedError(f"Invalid source ID: {source.id}")
        if not source.base_url or not isinstance(source.base_url, str):
            raise SourceRegistryCorruptedError(f"Invalid base_url for source {source.id}")
        try:
            parsed = urllib.parse.urlparse(source.base_url)
            if parsed.scheme.lower() not in ("https", "http") or not parsed.netloc:
                raise ValueError("Scheme must be http or https with valid host")
        except Exception as e:
            raise SourceRegistryCorruptedError(f"Invalid URL '{source.base_url}' in source {source.id}: {e}") from e

        if not source.allowed_host or not isinstance(source.allowed_host, str) or not source.allowed_host.strip():
            raise SourceRegistryCorruptedError(f"Invalid allowed_host for source {source.id}")
        if not isinstance(source.max_artifact_bytes, int) or source.max_artifact_bytes <= 0:
            raise SourceRegistryCorruptedError(f"Invalid max_artifact_bytes for source {source.id}")

    def _load(self) -> None:
        if self._file_path and self._file_path.exists():
            try:
                with open(self._file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict) or "sources" not in data or not isinstance(data["sources"], list):
                    raise ValueError("Source registry JSON must be a dictionary with a 'sources' list")
                for item in data.get("sources", []):
                    if not isinstance(item, dict):
                        raise ValueError(f"Malformed source item: {item}")
                    src_id = item.get("id") or item.get("source_id")
                    src = TrustedArtifactSource(
                        id=str(src_id) if src_id is not None else "",
                        base_url=str(item.get("base_url", "")),
                        allowed_host=str(item.get("allowed_host", "")),
                        allow_private_network=bool(item.get("allow_private_network", False)),
                        max_artifact_bytes=int(item.get("max_artifact_bytes", 104857600)),
                        ca_cert_path=str(item["ca_cert_path"]) if item.get("ca_cert_path") else None,
                    )
                    self._validate_source(src)
                    self._sources[src.id] = src
            except Exception as e:
                logger.error("Failed to load source registry from %s: %s", self._file_path, e)
                raise SourceRegistryCorruptedError(f"Corrupted source registry in {self._file_path}: {e}") from e

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
            temp_file = self._file_path.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            temp_file.replace(self._file_path)

    def register(self, source: TrustedArtifactSource) -> None:
        self._validate_source(source)
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
