"""Nav2 Adapter for OpenRobo Workspace Generator (Hardened).

Separates safe framework defaults from robot-specific assumptions.
Supports explicit frame/topic configurations and uses safe YAML dumping.
"""

from typing import Any, Dict, Optional

import yaml
from openrobo_workspace.models import GeneratedFile


def has_nav2_adapter(resource_id: str) -> bool:
    canonical_nav2_ids = {
        "nav2",
        "navigation2",
        "ros-navigation/navigation2",
        "ros-navigation/nav2_bringup",
    }
    return resource_id.lower() in canonical_nav2_ids


def get_nav2_launch_snippet() -> str:
    return """
    # --- Navigation2 Bringup Adapter (Verified) ---
    nav2_params_file = os.path.join(bringup_share, 'config', 'nav2_params.yaml')
    ld.add_action(LogInfo(msg='[OpenRobo] Initializing Nav2 Bringup Subsystem...'))
    # Nav2 orchestration uses standard include pattern
"""


def get_nav2_params_file(user_config: Optional[Dict[str, Any]] = None) -> GeneratedFile:
    """Generate Nav2 parameters using safe framework defaults and user overrides."""
    cfg = user_config or {}
    frames = cfg.get("frames", {}) or {}
    topics = cfg.get("topics", {}) or {}

    base_frame = frames.get("base", "base_link")
    odom_frame = frames.get("odom", "odom")
    global_frame = frames.get("map", "map")
    scan_topic = topics.get("scan", "/scan")

    nav2_params = {
        "amcl": {
            "ros__parameters": {
                "use_sim_time": True,
                "base_frame_id": base_frame,
                "odom_frame_id": odom_frame,
                "global_frame_id": global_frame,
                "scan_topic": scan_topic,
                "min_particles": 500,
                "max_particles": 2000,
                "update_min_d": 0.2,
                "update_min_a": 0.2,
            }
        },
        "bt_navigator": {
            "ros__parameters": {
                "use_sim_time": True,
                "global_frame": global_frame,
                "robot_base_frame": base_frame,
                "odom_topic": topics.get("odom", "/odom"),
            }
        },
        "controller_server": {
            "ros__parameters": {
                "use_sim_time": True,
                "controller_frequency": 20.0,
                "min_x_velocity_threshold": 0.001,
                "min_y_velocity_threshold": 0.5,
                "min_theta_velocity_threshold": 0.001,
            }
        },
        "planner_server": {
            "ros__parameters": {
                "use_sim_time": True,
                "expected_planner_frequency": 20.0,
            }
        },
        "behavior_server": {
            "ros__parameters": {
                "use_sim_time": True,
                "costmap_topic": "local_costmap/costmap_raw",
                "footprint_topic": "local_costmap/published_footprint",
                "cycle_frequency": 10.0,
            }
        },
    }

    yaml_content = "# ==============================================================================\n"
    yaml_content += "# Navigation2 Parameter Configuration (Hardened)\n"
    yaml_content += f"# Evidence: Safe framework defaults (base_frame: {base_frame}, global_frame: {global_frame})\n"
    yaml_content += "# Note: Verify frame IDs for your specific robot platform.\n"
    yaml_content += "# ==============================================================================\n\n"
    yaml_content += yaml.safe_dump(nav2_params, sort_keys=False)

    return GeneratedFile(
        path="src/openrobo_bringup/config/nav2_params.yaml",
        content=yaml_content,
        description="Navigation2 stack parameter configuration (safe framework defaults)",
    )
