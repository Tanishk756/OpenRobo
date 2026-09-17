"""Base abstract execution provider for OpenRobo runtime (Milestone 6)."""

from abc import ABC, abstractmethod
from typing import Dict, Optional

from openrobo_runtime.models import BuildVerificationResult, ProviderInfo


class ExecutionProvider(ABC):
    """Abstract base class for containerized and host execution providers."""

    @abstractmethod
    def detect_availability(self) -> ProviderInfo:
        """Probe environment to determine if provider CLI and daemon are operational."""
        pass

    @abstractmethod
    def build_workspace(
        self,
        workspace_dir: str,
        target_distro: str = "humble",
        timeout_sec: int = 300,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> BuildVerificationResult:
        """Execute controlled build verification on a generated colcon workspace."""
        pass
