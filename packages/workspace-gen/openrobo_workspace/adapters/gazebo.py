"""Gazebo Simulator Adapter for OpenRobo Workspace Generator (Hardened).

Provides generic simulation clock bridging and launch scaffolding.
Does not invent robot SDF, sensor topics, or world models unless supplied in configuration.
"""

from typing import Any, Dict, Optional

import yaml
from openrobo_workspace.models import GeneratedFile


def has_gazebo_adapter(resource_id: str) -> bool:
    canonical_gazebo_ids = {
        "gazebo",
        "gz_sim",
        "ros_gz",
        "ros_gz_sim",
        "ros_gz_bridge",
    }
    return resource_id.lower() in canonical_gazebo_ids


def get_gazebo_launch_snippet() -> str:
    return """
    # --- Gazebo Simulation & Clock Bridge (Verified Generic Scaffolding) ---
    ld.add_action(LogInfo(msg='[OpenRobo] Initializing Gazebo Simulation Clock Bridge...'))
    gz_bridge_node = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
        output='screen'
    )
    ld.add_action(gz_bridge_node)
"""


def get_gazebo_params_file(user_config: Optional[Dict[str, Any]] = None) -> GeneratedFile:
    """Generate Gazebo ros_gz_bridge topic mapping configuration safely."""
    bridges = (user_config or {}).get(
        "bridges",
        [
            {
                "ros_topic_name": "clock",
                "gz_topic_name": "clock",
                "ros_type_name": "rosgraph_msgs/msg/Clock",
                "gz_type_name": "gz.msgs.Clock",
                "direction": "GZ_TO_ROS",
            }
        ],
    )

    yaml_content = "# ==============================================================================\n"
    yaml_content += "# Gazebo ros_gz_bridge Parameter Configuration (Generic Clock Bridge)\n"
    yaml_content += "# Note: Add explicit sensor and actuator topic bridges below for custom robots.\n"
    yaml_content += "# ==============================================================================\n\n"
    yaml_content += yaml.safe_dump(bridges, sort_keys=False)

    return GeneratedFile(
        path="src/openrobo_bringup/config/gazebo_bridge.yaml",
        content=yaml_content,
        description="Gazebo ros_gz_bridge topic mapping configuration",
    )
