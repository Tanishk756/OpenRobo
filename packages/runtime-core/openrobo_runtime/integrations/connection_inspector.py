"""Connection Inspector Integration Adapter (Milestone 6).

External tool integration for the Dyno Robotics connection_inspector package (v1.0.1).

LICENSING & INTEGRATION POLICY:
Upstream Connection Inspector is licensed under GPL-3.0-only.
OpenRobo is licensed under Apache-2.0.
To preserve license integrity, OpenRobo NEVER vendors, embeds, or statically/dynamically
links Connection Inspector code. This adapter acts strictly as an external process-level
bridge for detection, launch orchestration, and diagnostic telemetry consumption.
"""

import os
import shutil
import subprocess
from typing import List, Optional

from openrobo_runtime.models import ConnectionInspectorReport, ConnectionInspectorStatus


class ConnectionInspectorAdapter:
    """Detects and interacts with the external ROS 2 connection_inspector package."""

    PACKAGE_NAME = "connection_inspector"
    SUPPORTED_ROS_DISTROS = {"humble", "iron", "jazzy", "rolling"}
    KNOWN_EXECUTABLES = ["inspect_cli", "connection_inspector"]

    def __init__(self, ros2_cmd: str = "ros2"):
        self.ros2_cmd = ros2_cmd

    def detect(self, target_distro: Optional[str] = None) -> ConnectionInspectorReport:
        """Safely probe whether connection_inspector is installed in the active ROS environment."""
        if target_distro and target_distro.lower() not in self.SUPPORTED_ROS_DISTROS:
            return ConnectionInspectorReport(
                status=ConnectionInspectorStatus.UNSUPPORTED_DISTRO,
                licensing_notice=self._get_licensing_notice(),
                diagnostic_summary={"supported_distros": sorted(list(self.SUPPORTED_ROS_DISTROS))},
            )

        if not shutil.which(self.ros2_cmd):
            return ConnectionInspectorReport(
                status=ConnectionInspectorStatus.NOT_INSTALLED,
                licensing_notice=self._get_licensing_notice(),
                diagnostic_summary={"note": "ROS 2 CLI ('ros2') not found in PATH."},
            )

        try:
            # Query ROS package prefix safely
            res = subprocess.run(
                [self.ros2_cmd, "pkg", "prefix", self.PACKAGE_NAME],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip():
                prefix = res.stdout.strip()
                # Check for known executables in package libexec / bin
                detected_execs = []
                for exe in self.KNOWN_EXECUTABLES:
                    exe_path = os.path.join(prefix, "lib", self.PACKAGE_NAME, exe)
                    if os.path.exists(exe_path) or shutil.which(exe):
                        detected_execs.append(exe)

                return ConnectionInspectorReport(
                    status=ConnectionInspectorStatus.INSTALLED,
                    version="1.0.1",
                    detected_prefix=prefix,
                    executables=detected_execs or self.KNOWN_EXECUTABLES,
                    licensing_notice=self._get_licensing_notice(),
                    diagnostic_summary={"installed_path": prefix},
                )
            else:
                return ConnectionInspectorReport(
                    status=ConnectionInspectorStatus.NOT_INSTALLED,
                    licensing_notice=self._get_licensing_notice(),
                    diagnostic_summary={
                        "installation_guidance": (
                            "To install Connection Inspector: sudo apt-get install ros-<distro>-connection-inspector "
                            "or build from https://github.com/DynoRobotics/connection_inspector-release"
                        )
                    },
                )
        except Exception as e:
            return ConnectionInspectorReport(
                status=ConnectionInspectorStatus.ERROR,
                licensing_notice=self._get_licensing_notice(),
                diagnostic_summary={"error": str(e)},
            )

    def build_cli_inspect_command(self, topic_filter: Optional[str] = None) -> List[str]:
        """Build controlled command array to run CLI diagnostic without shell interpolation."""
        cmd = [self.ros2_cmd, "run", self.PACKAGE_NAME, "inspect_cli"]
        if topic_filter:
            cmd.extend(["--topic", topic_filter])
        return cmd

    def build_gui_launch_command(self) -> List[str]:
        """Build controlled command array to open the Connection Inspector GUI."""
        return [self.ros2_cmd, "run", self.PACKAGE_NAME, "connection_inspector"]

    def _get_licensing_notice(self) -> str:
        return (
            "Connection Inspector is an external third-party tool licensed under GPL-3.0-only by Dyno Robotics. "
            "OpenRobo communicates with Connection Inspector via safe external process execution and does not vendor or link GPL code."
        )
