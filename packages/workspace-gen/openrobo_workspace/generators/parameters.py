"""Parameter YAML files generator."""

from typing import List

from openrobo_workspace.adapters.gazebo import get_gazebo_params_file
from openrobo_workspace.adapters.nav2 import get_nav2_params_file
from openrobo_workspace.adapters.ros2_control import get_ros2_control_params_file
from openrobo_workspace.adapters.slam_toolbox import get_slam_toolbox_params_file
from openrobo_workspace.models import GeneratedFile, WorkspaceGenerationPlan


def generate_parameter_files(plan: WorkspaceGenerationPlan) -> List[GeneratedFile]:
    files: List[GeneratedFile] = []
    component_ids = {c.resource_id.lower() for c in plan.components}
    pkg_name = plan.bringup_package_name

    if any("nav2" in cid or "navigation2" in cid for cid in component_ids):
        nav2_f = get_nav2_params_file()
        nav2_f.path = f"src/{pkg_name}/config/nav2_params.yaml"
        files.append(nav2_f)

    if any("slam_toolbox" in cid or "slam-toolbox" in cid for cid in component_ids):
        slam_f = get_slam_toolbox_params_file()
        slam_f.path = f"src/{pkg_name}/config/slam_toolbox_params.yaml"
        files.append(slam_f)

    if any("ros2_control" in cid or "joint_state_broadcaster" in cid for cid in component_ids):
        ctrl_f = get_ros2_control_params_file()
        ctrl_f.path = f"src/{pkg_name}/config/ros2_control_params.yaml"
        files.append(ctrl_f)

    if any("gazebo" in cid or "gz_sim" in cid or "ros_gz" in cid for cid in component_ids):
        gz_f = get_gazebo_params_file()
        gz_f.path = f"src/{pkg_name}/config/gazebo_bridge.yaml"
        files.append(gz_f)

    # For generic components without a specialized adapter, generate a clean example template
    for c in plan.components:
        cid = c.resource_id.lower()
        if not ("nav2" in cid or "slam_toolbox" in cid or "ros2_control" in cid or "gazebo" in cid or "gz_sim" in cid or "ros_gz" in cid):
            pkg_token = c.resource_id.split("/")[-1].replace("-", "_")
            example_yaml = f"""# Parameter template for {c.name} ({c.resource_id})
# Add custom node parameters below following standard ROS 2 parameter structure:
{pkg_token}_node:
  ros__parameters:
    use_sim_time: True
    # custom_parameter_example: 1.0
"""
            files.append(
                GeneratedFile(
                    path=f"src/{pkg_name}/config/{pkg_token}.yaml.example",
                    content=example_yaml,
                    description=f"Configuration template example for {c.name}",
                )
            )

    return files
