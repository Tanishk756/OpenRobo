"""SLAM Toolbox Adapter for OpenRobo Workspace Generator (Hardened).

Separates safe framework defaults from robot-specific assumptions.
Supports user frame/topic overrides and safe YAML dumping.
"""

from typing import Any, Dict, Optional

import yaml
from openrobo_workspace.models import GeneratedFile


def has_slam_toolbox_adapter(resource_id: str) -> bool:
    canonical_slam_ids = {
        "slam_toolbox",
        "slam-toolbox",
        "stevemacenski/slam_toolbox",
    }
    return resource_id.lower() in canonical_slam_ids


def get_slam_toolbox_launch_snippet() -> str:
    return """
    # --- SLAM Toolbox Mapping Subsystem (Verified) ---
    slam_params_file = os.path.join(bringup_share, 'config', 'slam_toolbox_params.yaml')
    ld.add_action(LogInfo(msg='[OpenRobo] Initializing SLAM Toolbox Subsystem...'))
"""


def get_slam_toolbox_params_file(user_config: Optional[Dict[str, Any]] = None) -> GeneratedFile:
    """Generate SLAM Toolbox parameters using safe framework defaults and user overrides."""
    cfg = user_config or {}
    frames = cfg.get("frames", {}) or {}
    topics = cfg.get("topics", {}) or {}

    odom_frame = frames.get("odom", "odom")
    map_frame = frames.get("map", "map")
    base_frame = frames.get("base", "base_footprint")
    scan_topic = topics.get("scan", "/scan")

    slam_params = {
        "slam_toolbox": {
            "ros__parameters": {
                "use_sim_time": True,
                "solver_plugin": "solver_plugins::CeresSolver",
                "ceres_linear_solver": "SPARSE_NORMAL_CHOLESKY",
                "ceres_preconditioner": "SCHUR_JACOBI",
                "ceres_trust_strategy": "LEVENBERG_MARQUARDT",
                "odom_frame": odom_frame,
                "map_frame": map_frame,
                "base_frame": base_frame,
                "scan_topic": scan_topic,
                "mode": "mapping",
                "resolution": 0.05,
                "max_laser_range": 20.0,
                "minimum_time_interval": 0.5,
                "transform_timeout": 0.2,
                "tf_buffer_duration": 30.0,
            }
        }
    }

    yaml_content = "# ==============================================================================\n"
    yaml_content += "# SLAM Toolbox Parameter Configuration (Hardened)\n"
    yaml_content += f"# Evidence: Safe framework defaults (odom: {odom_frame}, map: {map_frame}, base: {base_frame})\n"
    yaml_content += "# ==============================================================================\n\n"
    yaml_content += yaml.safe_dump(slam_params, sort_keys=False)

    return GeneratedFile(
        path="src/openrobo_bringup/config/slam_toolbox_params.yaml",
        content=yaml_content,
        description="SLAM Toolbox 2D online async mapping parameters",
    )
