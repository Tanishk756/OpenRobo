"""Podman Execution Provider for rootless containerized verification."""

import shutil
import subprocess
from typing import Dict, Optional

from openrobo_runtime.models import (
    BuildStatus,
    BuildVerificationResult,
    ExecutionProviderType,
    ProviderInfo,
    ProviderStatus,
)
from openrobo_runtime.providers.base import ExecutionProvider


class PodmanProvider(ExecutionProvider):
    """Executes build verification in Podman containers."""

    def __init__(self, podman_cmd: str = "podman"):
        self.podman_cmd = podman_cmd

    def detect_availability(self) -> ProviderInfo:
        if not shutil.which(self.podman_cmd):
            return ProviderInfo(
                provider_type=ExecutionProviderType.PODMAN,
                status=ProviderStatus.UNAVAILABLE,
                details="Podman CLI executable not found in PATH.",
                supports_build_verification=False,
            )
        try:
            res = subprocess.run([self.podman_cmd, "--version"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                return ProviderInfo(
                    provider_type=ExecutionProviderType.PODMAN,
                    status=ProviderStatus.DETECTED_NOT_IMPLEMENTED,
                    version=res.stdout.strip(),
                    details="Podman CLI detected; container build runner integration is in development.",
                    supports_build_verification=False,
                )
            return ProviderInfo(
                provider_type=ExecutionProviderType.PODMAN,
                status=ProviderStatus.UNAVAILABLE,
                details=res.stderr.strip(),
                supports_build_verification=False,
            )
        except Exception as e:
            return ProviderInfo(
                provider_type=ExecutionProviderType.PODMAN,
                status=ProviderStatus.ERROR,
                details=str(e),
                supports_build_verification=False,
            )

    def build_workspace(
        self,
        workspace_dir: str,
        target_distro: str = "humble",
        timeout_sec: int = 300,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> BuildVerificationResult:
        return BuildVerificationResult(
            status=BuildStatus.NOT_EXECUTED,
            provider=ExecutionProviderType.PODMAN,
            warnings=["Podman build verification runner is pending implementation. Use Docker or Local provider."],
        )
