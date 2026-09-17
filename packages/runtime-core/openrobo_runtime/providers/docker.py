"""Docker Execution Provider for containerized colcon verification."""

import shutil
import subprocess
import time
from typing import Dict, Optional

from openrobo_runtime.models import (
    BuildStatus,
    BuildVerificationResult,
    ExecutionProviderType,
    ProviderInfo,
    ProviderStatus,
)
from openrobo_runtime.providers.base import ExecutionProvider


class DockerProvider(ExecutionProvider):
    """Executes build verification in controlled Docker containers."""

    def __init__(self, docker_cmd: str = "docker"):
        self.docker_cmd = docker_cmd

    def detect_availability(self) -> ProviderInfo:
        if not shutil.which(self.docker_cmd):
            return ProviderInfo(
                provider_type=ExecutionProviderType.DOCKER,
                status=ProviderStatus.UNAVAILABLE,
                details="Docker CLI executable not found in PATH.",
            )

        try:
            res = subprocess.run(
                [self.docker_cmd, "info"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                v_res = subprocess.run(
                    [self.docker_cmd, "version", "--format", "{{.Client.Version}}"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                v_str = v_res.stdout.strip() if v_res.returncode == 0 else "unknown"
                return ProviderInfo(
                    provider_type=ExecutionProviderType.DOCKER,
                    status=ProviderStatus.AVAILABLE,
                    version=v_str,
                    details="Docker daemon is active and accessible.",
                )
            else:
                return ProviderInfo(
                    provider_type=ExecutionProviderType.DOCKER,
                    status=ProviderStatus.UNAVAILABLE,
                    details=f"Docker daemon is not running: {res.stderr.strip() or res.stdout.strip()}",
                )
        except Exception as e:
            return ProviderInfo(
                provider_type=ExecutionProviderType.DOCKER,
                status=ProviderStatus.ERROR,
                details=f"Docker probing failed: {str(e)}",
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
                provider=ExecutionProviderType.DOCKER,
                errors=[f"Cannot run Docker build verification: {avail.details}"],
            )

        start_t = time.time()
        dockerfile_path = f"{workspace_dir}/docker/Dockerfile"
        tag_name = f"openrobo_verify_{target_distro}"
        cmd = [
            self.docker_cmd,
            "build",
            "-t",
            tag_name,
            "-f",
            dockerfile_path,
            workspace_dir,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
            dur_ms = int((time.time() - start_t) * 1000)
            status = BuildStatus.PASSED if proc.returncode == 0 else BuildStatus.FAILED
            return BuildVerificationResult(
                status=status,
                provider=ExecutionProviderType.DOCKER,
                duration_ms=dur_ms,
                docker_build_status=status,
                exit_codes={"docker_build": proc.returncode},
                stdout_summary=proc.stdout.splitlines()[-20:] if proc.stdout else [],
                stderr_summary=proc.stderr.splitlines()[-20:] if proc.stderr else [],
                errors=[proc.stderr.strip()] if proc.returncode != 0 else [],
            )
        except subprocess.TimeoutExpired:
            return BuildVerificationResult(
                status=BuildStatus.FAILED,
                provider=ExecutionProviderType.DOCKER,
                duration_ms=timeout_sec * 1000,
                errors=[f"Docker build timed out after {timeout_sec} seconds."],
            )
        except Exception as e:
            return BuildVerificationResult(
                status=BuildStatus.FAILED,
                provider=ExecutionProviderType.DOCKER,
                errors=[f"Docker execution failed: {str(e)}"],
            )
