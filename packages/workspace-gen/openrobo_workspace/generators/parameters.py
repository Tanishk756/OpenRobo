"""Parameter YAML files generator."""

from typing import List

from openrobo_workspace.adapters.gazebo import get_gazebo_params_file
from openrobo_workspace.adapters.nav2 import get_nav2_params_file
from openrobo_workspace.adapters.ros2_control import get_ros2_control_params_file
from openrobo_workspace.adapters.slam_toolbox import get_slam_toolbox_params_file
from openrobo_workspace.models import GeneratedFile, WorkspaceGenerationPlan


def generate_parameter_files(plan: WorkspaceGenerationPlan) -> List[GeneratedFile]:
    files: List[GeneratedFile] = []
    pkg_name = plan.bringup_package_name
    user_cfg = plan.user_configuration or {}
    active_adapter_ids = {c.adapter_name for c in plan.components if c.has_adapter and c.adapter_name}

    if "nav2" in active_adapter_ids:
        nav2_user = user_cfg.get("nav2") or {
            "frames": user_cfg.get("frames"),
            "topics": user_cfg.get("topics"),
        }
        nav2_f = get_nav2_params_file(user_config=nav2_user)
        nav2_f.path = f"src/{pkg_name}/config/nav2_params.yaml"
        files.append(nav2_f)

    if "slam_toolbox" in active_adapter_ids:
        slam_user = user_cfg.get("slam_toolbox") or {
            "frames": user_cfg.get("frames"),
            "topics": user_cfg.get("topics"),
        }
        slam_f = get_slam_toolbox_params_file(user_config=slam_user)
        slam_f.path = f"src/{pkg_name}/config/slam_toolbox_params.yaml"
        files.append(slam_f)

    if "ros2_control" in active_adapter_ids:
        ctrl_user = user_cfg.get("ros2_control")
        ctrl_f = get_ros2_control_params_file(user_config=ctrl_user)
        # If user config is absent, path becomes .yaml.example
        if ctrl_user:
            ctrl_f.path = f"src/{pkg_name}/config/ros2_control_params.yaml"
        else:
            ctrl_f.path = f"src/{pkg_name}/config/ros2_control_params.yaml.example"
        files.append(ctrl_f)

    if "gazebo" in active_adapter_ids:
        gz_user = user_cfg.get("gazebo")
        gz_f = get_gazebo_params_file(user_config=gz_user)
        gz_f.path = f"src/{pkg_name}/config/gazebo_bridge.yaml"
        files.append(gz_f)

    # For generic components without a specialized adapter, generate clean scaffold example template
    for c in plan.components:
        if not c.has_adapter or not c.adapter_name:
            pkg_token = c.resource_id.split("/")[-1].replace("-", "_").lower()
            example_yaml = f"""# ==============================================================================
# Generic Configuration Scaffold Example for {c.name} ({c.resource_id})
# Evidence Level: GENERIC_SCAFFOLD (Manual configuration required)
# ==============================================================================
{pkg_token}_node:
  ros__parameters:
    use_sim_time: True
    # TODO: Add robot-specific node parameters here
"""
            files.append(
                GeneratedFile(
                    path=f"src/{pkg_name}/config/{pkg_token}.yaml.example",
                    content=example_yaml,
                    description=f"Configuration scaffold example for {c.name}",
                )
            )

    return files
