"""Execution Provider Detector."""

from typing import Dict, Optional

from openrobo_runtime.models import ExecutionProviderType, ProviderInfo, ProviderStatus
from openrobo_runtime.providers.base import ExecutionProvider
from openrobo_runtime.providers.docker import DockerProvider
from openrobo_runtime.providers.local import LocalProcessProvider
from openrobo_runtime.providers.podman import PodmanProvider


class ProviderDetector:
    """Discovers and manages execution providers."""

    def __init__(self):
        self.providers: Dict[ExecutionProviderType, ExecutionProvider] = {
            ExecutionProviderType.DOCKER: DockerProvider(),
            ExecutionProviderType.PODMAN: PodmanProvider(),
            ExecutionProviderType.LOCAL_PROCESS: LocalProcessProvider(),
        }

    def detect_all(self) -> Dict[ExecutionProviderType, ProviderInfo]:
        results = {}
        for ptype, provider in self.providers.items():
            results[ptype] = provider.detect_availability()
        return results

    def get_preferred_provider(
        self, requested: Optional[ExecutionProviderType] = None
    ) -> tuple[ExecutionProviderType, ExecutionProvider, ProviderInfo]:
        if requested and requested in self.providers:
            info = self.providers[requested].detect_availability()
            return requested, self.providers[requested], info

        # Auto-preference: DOCKER -> LOCAL_PROCESS -> PODMAN
        for ptype in [ExecutionProviderType.DOCKER, ExecutionProviderType.LOCAL_PROCESS, ExecutionProviderType.PODMAN]:
            provider = self.providers[ptype]
            info = provider.detect_availability()
            if info.status == ProviderStatus.AVAILABLE:
                return ptype, provider, info

        # Return Docker (unavailable) as default
        docker_p = self.providers[ExecutionProviderType.DOCKER]
        return ExecutionProviderType.DOCKER, docker_p, docker_p.detect_availability()
