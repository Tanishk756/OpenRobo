"""Build Verification Executor (Milestone 6.1)."""

import hashlib
import os
from typing import Optional

from openrobo_runtime.models import (
    BuildStatus,
    BuildVerificationResult,
    ExecutionProviderType,
    ProviderStatus,
)
from openrobo_runtime.providers.detector import ProviderDetector


class BuildRunner:
    """Orchestrates controlled colcon and container build verification on generated workspaces."""

    def __init__(self, detector: Optional[ProviderDetector] = None):
        self.detector = detector or ProviderDetector()

    def verify_workspace_build(
        self,
        workspace_dir: str,
        target_distro: str = "humble",
        requested_provider: Optional[ExecutionProviderType] = None,
        timeout_sec: int = 300,
    ) -> BuildVerificationResult:
        # Path validation
        if not workspace_dir or "\0" in workspace_dir:
            return BuildVerificationResult(
                status=BuildStatus.FAILED,
                errors=["Invalid workspace path: contains null byte or is empty."],
            )

        real_ws_path = os.path.realpath(workspace_dir)
        if not os.path.exists(real_ws_path) or not os.path.isdir(real_ws_path):
            return BuildVerificationResult(
                status=BuildStatus.FAILED,
                errors=[f"Workspace directory does not exist: '{workspace_dir}'"],
            )

        # 1. Pre-flight Static Validation
        # Check for unconfigured .example files that block builds
        src_dir = os.path.join(real_ws_path, "src")
        if os.path.exists(src_dir):
            for root, _, files in os.walk(src_dir):
                for f in files:
                    if f.endswith(".example") and "ros2_control" in f:
                        return BuildVerificationResult(
                            status=BuildStatus.FAILED,
                            errors=[
                                f"Build blocked: Required hardware configuration missing in '{f}'. "
                                "Configure physical joints and geometry before build verification."
                            ],
                        )

        # 2. Select Execution Provider
        ptype, provider, info = self.detector.get_preferred_provider(requested_provider)

        if info.status != ProviderStatus.AVAILABLE:
            return BuildVerificationResult(
                status=BuildStatus.NOT_EXECUTED,
                provider=ptype,
                warnings=[f"Execution provider '{ptype.value}' is unavailable: {info.details}"],
            )

        # 3. Execute Build Verification
        res = provider.build_workspace(
            workspace_dir=real_ws_path,
            target_distro=target_distro,
            timeout_sec=timeout_sec,
        )

        # 4. Generate artifact digest if build passed
        if res.status == BuildStatus.PASSED:
            hasher = hashlib.sha256()
            hasher.update(f"{real_ws_path}:{res.duration_ms}".encode("utf-8"))
            res.artifact_digest = hasher.hexdigest()

        return res
