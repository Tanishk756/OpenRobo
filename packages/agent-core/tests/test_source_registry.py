import tempfile
from pathlib import Path

from openrobo_agent.deployment.source_registry import (
    TrustedArtifactSource,
    TrustedArtifactSourceRegistry,
)


def test_source_registry_registration_and_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        reg_file = Path(tmpdir) / "sources.json"
        registry = TrustedArtifactSourceRegistry(reg_file)

        src = TrustedArtifactSource(
            id="src-prod-01",
            base_url="https://artifacts.openrobo.internal/v1",
            allowed_host="artifacts.openrobo.internal",
            allow_private_network=False,
            max_artifact_bytes=50 * 1024 * 1024,
        )
        registry.register_source(src)

        # Retrieve
        fetched = registry.get_source("src-prod-01")
        assert fetched is not None
        assert fetched.id == "src-prod-01"
        assert fetched.allowed_host == "artifacts.openrobo.internal"
        assert fetched.allow_private_network is False

        # Verify disk persistence
        registry2 = TrustedArtifactSourceRegistry(reg_file)
        fetched2 = registry2.get_source("src-prod-01")
        assert fetched2 is not None
        assert fetched2.id == "src-prod-01"
        assert fetched2.base_url == "https://artifacts.openrobo.internal/v1"

        # Unknown source fails closed
        assert registry2.get_source("src-unknown") is None
