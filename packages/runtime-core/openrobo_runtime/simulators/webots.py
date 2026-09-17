"""Webots Simulation Adapter."""

import shutil
import subprocess
from typing import Any, Dict, List, Optional

from openrobo_runtime.simulators.base import SimulationAdapter


class WebotsAdapter(SimulationAdapter):
    """Orchestrates Webots robot simulation."""

    def __init__(self, webots_cmd: str = "webots"):
        self.webots_cmd = webots_cmd

    def detect(self) -> Dict[str, Any]:
        if not shutil.which(self.webots_cmd):
            return {
                "installed": False,
                "simulator": "webots",
                "details": "Webots executable not found in PATH.",
            }
        try:
            res = subprocess.run([self.webots_cmd, "--version"], capture_output=True, text=True, timeout=5)
            return {
                "installed": True,
                "simulator": "webots",
                "version": res.stdout.strip() if res.returncode == 0 else "unknown",
            }
        except Exception as e:
            return {"installed": False, "simulator": "webots", "details": str(e)}

    def validate(self, workspace_path: str) -> tuple[bool, List[str]]:
        return True, []

    def build_launch_command(
        self,
        workspace_path: str,
        bringup_pkg: str,
        world_name: Optional[str] = None,
        headless: bool = True,
    ) -> List[str]:
        cmd = [self.webots_cmd, "--mode=realtime"]
        if headless:
            cmd.append("--batch")
        return cmd
