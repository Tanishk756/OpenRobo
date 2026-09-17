"""Base abstract Simulation Adapter (Milestone 6)."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class SimulationAdapter(ABC):
    """Unified interface for robotics simulator adapters (Gazebo, Webots, MuJoCo)."""

    @abstractmethod
    def detect(self) -> Dict[str, Any]:
        """Detect if simulator binary/toolchain is installed and operational."""
        pass

    @abstractmethod
    def validate(self, workspace_path: str) -> tuple[bool, List[str]]:
        """Validate that workspace contains valid simulation configuration for this engine."""
        pass

    @abstractmethod
    def build_launch_command(
        self,
        workspace_path: str,
        bringup_pkg: str,
        world_name: Optional[str] = None,
        headless: bool = True,
    ) -> List[str]:
        """Construct safe command array for launching the simulation environment."""
        pass
