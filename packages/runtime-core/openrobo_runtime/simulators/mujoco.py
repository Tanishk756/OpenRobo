"""MuJoCo Simulation Adapter."""

from typing import Any, Dict, List, Optional

from openrobo_runtime.simulators.base import SimulationAdapter


class MujocoAdapter(SimulationAdapter):
    """Orchestrates MuJoCo physics engine simulations."""

    def detect(self) -> Dict[str, Any]:
        try:
            import mujoco  # type: ignore
            return {
                "installed": True,
                "simulator": "mujoco",
                "version": getattr(mujoco, "__version__", "unknown"),
            }
        except ImportError:
            return {
                "installed": False,
                "simulator": "mujoco",
                "details": "Python mujoco package is not installed in current environment.",
            }

    def validate(self, workspace_path: str) -> tuple[bool, List[str]]:
        return True, []

    def build_launch_command(
        self,
        workspace_path: str,
        bringup_pkg: str,
        world_name: Optional[str] = None,
        headless: bool = True,
    ) -> List[str]:
        return ["python3", "-m", "openrobo_runtime.simulators.mujoco_runner"]
