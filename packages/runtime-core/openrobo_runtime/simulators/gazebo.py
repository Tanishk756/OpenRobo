"""Gazebo Simulation Adapter (Harmonic & Fortress)."""

import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from openrobo_runtime.simulators.base import SimulationAdapter


class GazeboAdapter(SimulationAdapter):
    """Orchestrates Gazebo Harmonic/Fortress simulation workflows and topic bridges."""

    KNOWN_GZ_CMDS = ["gz", "ign"]

    def __init__(self, gz_cmd: Optional[str] = None):
        self.gz_cmd = gz_cmd or self._find_gz_cmd()

    def _find_gz_cmd(self) -> str:
        for cmd in self.KNOWN_GZ_CMDS:
            if shutil.which(cmd):
                return cmd
        return "gz"

    def detect(self) -> Dict[str, Any]:
        if not shutil.which(self.gz_cmd):
            return {
                "installed": False,
                "simulator": "gazebo",
                "details": "Gazebo (gz/ign) CLI executable not found in PATH.",
            }

        try:
            res = subprocess.run([self.gz_cmd, "sim", "--version"], capture_output=True, text=True, timeout=5)
            version_str = res.stdout.strip() if res.returncode == 0 else "unknown"
            variant = "Harmonic" if "8." in version_str or "Harmonic" in version_str else "Fortress" if "6." in version_str else "Gazebo"
            return {
                "installed": True,
                "simulator": "gazebo",
                "variant": variant,
                "version": version_str,
                "executable": shutil.which(self.gz_cmd),
            }
        except Exception as e:
            return {
                "installed": False,
                "simulator": "gazebo",
                "details": f"Gazebo probing failed: {str(e)}",
            }

    def validate(self, workspace_path: str) -> tuple[bool, List[str]]:
        errors = []
        # Check for bringup package and gazebo_bridge.yaml or launch file
        src_dir = os.path.join(workspace_path, "src")
        if not os.path.exists(src_dir):
            errors.append("Workspace missing 'src/' directory.")

        return len(errors) == 0, errors

    def build_launch_command(
        self,
        workspace_path: str,
        bringup_pkg: str,
        world_name: Optional[str] = None,
        headless: bool = True,
    ) -> List[str]:
        cmd = ["ros2", "launch", bringup_pkg, "robot_bringup.launch.py", "use_sim_time:=true"]
        if headless:
            cmd.append("headless:=true")
        return cmd
