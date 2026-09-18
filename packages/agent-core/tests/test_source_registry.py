# Unit tests for TrustedArtifactSourceRegistry and fail-closed corruption detection.

import json
import tempfile
from pathlib import Path

import pytest
from openrobo_agent.deployment.source_registry import (
    SourceRegistryCorruptedError,
    TrustedArtifactSource,
    TrustedArtifactSourceRegistry,
)


def test_source_registry_registration_and_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        reg_file = Path(tmpdir) / "artifact_sources.json"
        registry = TrustedArtifactSourceRegistry(reg_file)
        assert registry.get("src-prod") is None

        src = TrustedArtifactSource(
            id="src-prod",
            base_url="https://releases.openrobo.org/artifacts",
            allowed_host="releases.openrobo.org",
            allow_private_network=False,
            max_artifact_bytes=50 * 1024 * 1024,
        )
        registry.register(src)

        retrieved = registry.get("src-prod")
        assert retrieved is not None
        assert retrieved.base_url == "https://releases.openrobo.org/artifacts"
        assert retrieved.allowed_host == "releases.openrobo.org"
        assert retrieved.max_artifact_bytes == 50 * 1024 * 1024

        # Reload from disk
        registry2 = TrustedArtifactSourceRegistry.from_file(reg_file)
        retrieved2 = registry2.get("src-prod")
        assert retrieved2 is not None
        assert retrieved2.id == "src-prod"


def test_source_registry_corruption_fails_closed():
    with tempfile.TemporaryDirectory() as tmpdir:
        reg_file = Path(tmpdir) / "artifact_sources.json"

        # 1. Non-JSON corrupted file
        reg_file.write_text("NOT_JSON_DATA", encoding="utf-8")
        with pytest.raises(SourceRegistryCorruptedError):
            TrustedArtifactSourceRegistry(reg_file)

        # 2. Invalid source record (e.g. invalid base_url or missing allowed_host)
        invalid_data = {
            "sources": [
                {
                    "id": "src-bad",
                    "base_url": "ftp://unsupported.com",
                    "allowed_host": "",
                }
            ]
        }
        reg_file.write_text(json.dumps(invalid_data), encoding="utf-8")
        with pytest.raises(SourceRegistryCorruptedError):
            TrustedArtifactSourceRegistry(reg_file)
