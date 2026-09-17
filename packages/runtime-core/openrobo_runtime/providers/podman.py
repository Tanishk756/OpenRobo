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
            )
        try:
            res = subprocess.run([self.podman_cmd, "--version"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                return ProviderInfo(
                    provider_type=ExecutionProviderType.PODMAN,
                    status=ProviderStatus.AVAILABLE,
                    version=res.stdout.strip(),
                    details="Podman CLI is ready.",
                )
            return ProviderInfo(
                provider_type=ExecutionProviderType.PODMAN,
                status=ProviderStatus.UNAVAILABLE,
                details=res.stderr.strip(),
            )
        except Exception as e:
            return ProviderInfo(
                provider_type=ExecutionProviderType.PODMAN,
                status=ProviderStatus.ERROR,
                details=str(e),
            )

    def build_workspace(
        self,
        workspace_dir: str,
        target_distro: str = "humble",
        timeout_sec: int = 300,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> BuildVerificationResult:
        avail = self.detect_availability()
        if avail.status != ProviderStatus.AVAILABLE:
            return BuildVerificationResult(
                status=BuildStatus.FAILED,
                provider=ExecutionProviderType.PODMAN,
                errors=[f"Cannot run Podman build: {avail.details}"],
            )
        return BuildVerificationResult(
            status=BuildStatus.NOT_EXECUTED,
            provider=ExecutionProviderType.PODMAN,
            warnings=["Podman build runner integration pending."],
        )
