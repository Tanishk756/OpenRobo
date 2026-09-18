"""Local Process Execution Provider for native colcon builds."""

import os
import shutil
import subprocess
import time
from typing import Dict, Optional, Set

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

    ALLOWED_ENV_VARS: Set[str] = {
        "PATH",
        "HOME",
        "USER",
        "LANG",
        "LC_ALL",
        "TMPDIR",
        "TEMP",
        "SYSTEMROOT",
        "WINDIR",
        "ROS_DISTRO",
        "ROS_DOMAIN_ID",
        "ROS_VERSION",
        "RMW_IMPLEMENTATION",
        "AMENT_PREFIX_PATH",
        "COLCON_PREFIX_PATH",
        "CMAKE_PREFIX_PATH",
    }

    DISALLOWED_ENV_SUBSTRINGS: Set[str] = {
        "LD_PRELOAD",
        "PYTHONPATH",
        "BASH_ENV",
        "ENV",
        "PROMPT_COMMAND",
    }

    def __init__(self, colcon_cmd: str = "colcon", rosdep_cmd: str = "rosdep"):
        self.colcon_cmd = colcon_cmd
        self.rosdep_cmd = rosdep_cmd

    def detect_availability(self) -> ProviderInfo:
        has_colcon = shutil.which(self.colcon_cmd) is not None

        if has_colcon:
            return ProviderInfo(
                provider_type=ExecutionProviderType.LOCAL_PROCESS,
                status=ProviderStatus.AVAILABLE,
                details="Local colcon build tool is installed on host.",
                supports_build_verification=True,
            )
        else:
            return ProviderInfo(
                provider_type=ExecutionProviderType.LOCAL_PROCESS,
                status=ProviderStatus.UNAVAILABLE,
                details="Local colcon executable not found in PATH.",
                supports_build_verification=True,
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
        clean_env: Dict[str, str] = {}
        for k in self.ALLOWED_ENV_VARS:
            if k in os.environ:
                clean_env[k] = os.environ[k]

        # Merge user env vars ONLY if in allowlist and not containing injection tokens
        if env_vars:
            for k, v in env_vars.items():
                if k.upper() in self.ALLOWED_ENV_VARS:
                    if not any(bad in k.upper() for bad in self.DISALLOWED_ENV_SUBSTRINGS):
                        clean_env[k] = str(v)

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
                verified_via="host_colcon",
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
