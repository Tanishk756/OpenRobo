"""Local Process Execution Provider for native colcon builds."""

import os
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


class LocalProcessProvider(ExecutionProvider):
    """Executes build verification using local host colcon and rosdep toolchains."""

    def __init__(self, colcon_cmd: str = "colcon", rosdep_cmd: str = "rosdep"):
        self.colcon_cmd = colcon_cmd
        self.rosdep_cmd = rosdep_cmd

    def detect_availability(self) -> ProviderInfo:
        has_colcon = shutil.which(self.colcon_cmd) is not None
        # has_rosdep check

        if has_colcon:
            return ProviderInfo(
                provider_type=ExecutionProviderType.LOCAL_PROCESS,
                status=ProviderStatus.AVAILABLE,
                details="Local colcon build tool is installed on host.",
            )
        else:
            return ProviderInfo(
                provider_type=ExecutionProviderType.LOCAL_PROCESS,
                status=ProviderStatus.UNAVAILABLE,
                details="Local colcon executable not found in PATH.",
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
                provider=ExecutionProviderType.LOCAL_PROCESS,
                errors=[f"Local build verification unavailable: {avail.details}"],
            )

        start_t = time.time()
        # Security: Clean environment allowlist
        clean_env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "USER": os.environ.get("USER", ""),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
        }
        if "ROS_DISTRO" in os.environ:
            clean_env["ROS_DISTRO"] = os.environ["ROS_DISTRO"]
        if env_vars:
            clean_env.update(env_vars)

        cmd = [self.colcon_cmd, "build", "--symlink-install"]
        try:
            proc = subprocess.run(
                cmd,
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                env=clean_env,
            )
            dur_ms = int((time.time() - start_t) * 1000)
            status = BuildStatus.PASSED if proc.returncode == 0 else BuildStatus.FAILED
            return BuildVerificationResult(
                status=status,
                provider=ExecutionProviderType.LOCAL_PROCESS,
                duration_ms=dur_ms,
                colcon_status=status,
                exit_codes={"colcon_build": proc.returncode},
                stdout_summary=proc.stdout.splitlines()[-20:] if proc.stdout else [],
                stderr_summary=proc.stderr.splitlines()[-20:] if proc.stderr else [],
                errors=[proc.stderr.strip()] if proc.returncode != 0 else [],
            )
        except subprocess.TimeoutExpired:
            return BuildVerificationResult(
                status=BuildStatus.FAILED,
                provider=ExecutionProviderType.LOCAL_PROCESS,
                duration_ms=timeout_sec * 1000,
                errors=[f"colcon build timed out after {timeout_sec} seconds."],
            )
        except Exception as e:
            return BuildVerificationResult(
                status=BuildStatus.FAILED,
                provider=ExecutionProviderType.LOCAL_PROCESS,
                errors=[f"colcon execution failed: {str(e)}"],
            )
