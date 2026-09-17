"""Connection Inspector Integration Adapter (Milestone 6.1).

External tool integration for the Dyno Robotics connection_inspector package.

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
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from openrobo_runtime.models import (
    ConnectionInspectorReport,
    ConnectionInspectorStatus,
    DistroReleaseSupport,
)


class ConnectionInspectorAdapter:
    """Detects and interacts with the external ROS 2 connection_inspector package."""

    PACKAGE_NAME = "connection_inspector"
    VERIFIED_DISTROS = {"humble", "jazzy"}
    COMMUNITY_DISTROS = {"iron", "rolling"}
    KNOWN_EXECUTABLE_NAMES = ["inspect_cli", "connection_inspector"]

    def __init__(self, ros2_cmd: str = "ros2"):
        self.ros2_cmd = ros2_cmd

    def detect(self, target_distro: Optional[str] = None) -> ConnectionInspectorReport:
        """Safely probe whether connection_inspector is installed in the active ROS environment."""
        # Distro support classification
        distro_support = DistroReleaseSupport.UNKNOWN
        if target_distro:
            ldistro = target_distro.lower().strip()
            if ldistro in self.VERIFIED_DISTROS:
                distro_support = DistroReleaseSupport.VERIFIED_RELEASE
            elif ldistro in self.COMMUNITY_DISTROS:
                distro_support = DistroReleaseSupport.UNKNOWN
            else:
                distro_support = DistroReleaseSupport.UNSUPPORTED
                return ConnectionInspectorReport(
                    status=ConnectionInspectorStatus.UNSUPPORTED_DISTRO,
                    distro_support=distro_support,
                    licensing_notice=self._get_licensing_notice(),
                    diagnostic_summary={
                        "verified_distros": sorted(list(self.VERIFIED_DISTROS)),
                        "requested_distro": target_distro,
                    },
                )

        if not shutil.which(self.ros2_cmd):
            return ConnectionInspectorReport(
                status=ConnectionInspectorStatus.NOT_INSTALLED,
                distro_support=distro_support,
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

                # Dynamic version discovery from package.xml
                version = self._extract_version_from_prefix(prefix)

                # Dynamic executable discovery
                detected_execs = self._discover_executables(prefix)

                return ConnectionInspectorReport(
                    status=ConnectionInspectorStatus.INSTALLED,
                    version=version,
                    detected_prefix=prefix,
                    executables=detected_execs,
                    distro_support=distro_support,
                    licensing_notice=self._get_licensing_notice(),
                    diagnostic_summary={"installed_path": prefix},
                )
            else:
                return ConnectionInspectorReport(
                    status=ConnectionInspectorStatus.NOT_INSTALLED,
                    distro_support=distro_support,
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
                distro_support=distro_support,
                licensing_notice=self._get_licensing_notice(),
                diagnostic_summary={"error": str(e)},
            )

    def _extract_version_from_prefix(self, prefix: str) -> Optional[str]:
        """Extract actual installed version from package.xml in package share dir."""
        pkg_xml_path = os.path.join(prefix, "share", self.PACKAGE_NAME, "package.xml")
        if os.path.isfile(pkg_xml_path):
            try:
                tree = ET.parse(pkg_xml_path)
                root = tree.getroot()
                version_elem = root.find("version")
                if version_elem is not None and version_elem.text:
                    return version_elem.text.strip()
            except Exception:
                pass
        return None

    def _discover_executables(self, prefix: str) -> List[str]:
        """Discover actual installed executables in package lib or bin."""
        found = []
        # Check libexec directory: <prefix>/lib/<package_name>/
        lib_dir = os.path.join(prefix, "lib", self.PACKAGE_NAME)
        if os.path.isdir(lib_dir):
            for exe in self.KNOWN_EXECUTABLE_NAMES:
                if os.path.isfile(os.path.join(lib_dir, exe)):
                    found.append(exe)

        # Check bin directory
        bin_dir = os.path.join(prefix, "bin")
        if os.path.isdir(bin_dir):
            for exe in self.KNOWN_EXECUTABLE_NAMES:
                if os.path.isfile(os.path.join(bin_dir, exe)) and exe not in found:
                    found.append(exe)

        return found

    def build_cli_inspect_command(self) -> List[str]:
        """Build controlled command array to run CLI diagnostic without shell interpolation."""
        return [self.ros2_cmd, "run", self.PACKAGE_NAME, "inspect_cli"]

    def build_gui_launch_command(self) -> List[str]:
        """Build controlled command array to open the Connection Inspector GUI."""
        return [self.ros2_cmd, "run", self.PACKAGE_NAME, "connection_inspector"]

    def run_cli_inspection(self, timeout_sec: int = 10) -> Dict[str, Any]:
        """Execute inspect_cli external process safely."""
        detection = self.detect()
        if detection.status != ConnectionInspectorStatus.INSTALLED:
            return {
                "status": "NOT_EXECUTED",
                "error": "connection_inspector package is not installed in the ROS environment.",
            }

        cmd = self.build_cli_inspect_command()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
            return {
                "status": "COMPLETED" if proc.returncode == 0 else "FAILED",
                "exit_code": proc.returncode,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
            }
        except subprocess.TimeoutExpired:
            return {"status": "TIMEOUT", "error": f"CLI inspection timed out after {timeout_sec}s"}
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}

    def _get_licensing_notice(self) -> str:
        return (
            "Connection Inspector is an external third-party tool licensed under GPL-3.0-only by Dyno Robotics. "
            "OpenRobo communicates with Connection Inspector via safe external process execution and does not vendor or link GPL code."
        )
