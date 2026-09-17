"""Canonical Adapter Registry for OpenRobo Workspace Generator.

Eliminates substring matching and ensures only explicitly verified, canonical
robotics framework resources receive verified adapter synthesis.
"""

from typing import Dict, List, Optional, Set

from pydantic import BaseModel, Field


class AdapterSpec(BaseModel):
    adapter_id: str
    adapter_version: str = "1.0.0"
    canonical_ids: Set[str] = Field(default_factory=set)
    supported_distros: Set[str] = Field(default_factory=lambda: {"humble", "jazzy", "iron", "rolling"})
    description: str = ""


CANONICAL_ADAPTERS: List[AdapterSpec] = [
    AdapterSpec(
        adapter_id="nav2",
        adapter_version="1.0.0",
        canonical_ids={
            "ros-navigation/navigation2",
            "ros-navigation/nav2",
            "nav2",
            "navigation2",
        },
        supported_distros={"humble", "jazzy", "iron", "rolling"},
        description="Navigation2 Autonomous Mobile Robot Navigation Framework",
    ),
    AdapterSpec(
        adapter_id="slam_toolbox",
        adapter_version="1.0.0",
        canonical_ids={
            "stevemacenski/slam_toolbox",
            "slam_toolbox",
            "slam-toolbox",
        },
        supported_distros={"humble", "jazzy", "iron", "rolling"},
        description="SLAM Toolbox 2D Online Async Lifelong Mapping",
    ),
    AdapterSpec(
        adapter_id="ros2_control",
        adapter_version="1.0.0",
        canonical_ids={
            "ros-controls/ros2_control",
            "ros2_control",
            "controller_manager",
        },
        supported_distros={"humble", "jazzy", "iron", "rolling"},
        description="ros2_control Real-Time Controller Framework & Hardware Abstraction",
    ),
    AdapterSpec(
        adapter_id="gazebo",
        adapter_version="1.0.0",
        canonical_ids={
            "gazebosim/gz-sim",
            "ros-simulation/gazebo",
            "ros_gz_sim",
            "gazebo",
            "gz_sim",
        },
        supported_distros={"humble", "jazzy", "iron", "rolling"},
        description="Gazebo Modern Simulation & ros_gz_bridge Scaffolding",
    ),
]


class AdapterRegistry:
    """Registry maintaining canonical adapter mappings with exact matching."""

    def __init__(self, adapters: Optional[List[AdapterSpec]] = None):
        self._adapters: List[AdapterSpec] = adapters or CANONICAL_ADAPTERS
        self._id_map: Dict[str, AdapterSpec] = {}
        for spec in self._adapters:
            for cid in spec.canonical_ids:
                self._id_map[cid.strip().lower()] = spec

    def get_adapter(self, resource_id: str, ros_distro: str = "humble") -> Optional[AdapterSpec]:
        """Lookup verified adapter using EXACT canonical identifier match.

        Never performs substring matching (e.g. 'my_nav2_pkg' will return None).
        """
        clean_id = resource_id.strip().lower()
        spec = self._id_map.get(clean_id)
        if spec and ros_distro.strip().lower() in spec.supported_distros:
            return spec
        return None

    def is_verified(self, resource_id: str, ros_distro: str = "humble") -> bool:
        return self.get_adapter(resource_id, ros_distro) is not None


default_adapter_registry = AdapterRegistry()
