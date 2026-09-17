"""ros2_control Adapter."""

from openrobo_workspace.models import GeneratedFile


def has_ros2_control_adapter(resource_id: str) -> bool:
    rid = resource_id.lower()
    return "ros2_control" in rid or "controller_manager" in rid or "diff_drive_controller" in rid


def get_ros2_control_launch_snippet() -> str:
    return """    # ros2_control Hardware Controller Manager
    control_params_file = os.path.join(bringup_share, 'config', 'ros2_control_params.yaml')
    controller_manager_node = Node(
        package='controller_manager',
        executable='ros2_control_node',
        parameters=[control_params_file],
        output='screen',
    )
    jsb_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster', '--controller-manager', '/controller_manager'],
        output='screen',
    )
    ld.add_action(controller_manager_node)
    ld.add_action(jsb_spawner)
"""


def get_ros2_control_params_file() -> GeneratedFile:
    yaml_content = """# OpenRobo Synthesized ros2_control Parameters
controller_manager:
  ros__parameters:
    update_rate: 100  # Hz

    joint_state_broadcaster:
      type: joint_state_broadcaster/JointStateBroadcaster

    diff_drive_controller:
      type: diff_drive_controller/DiffDriveController

diff_drive_controller:
  ros__parameters:
    left_wheel_names: ["left_wheel_joint"]
    right_wheel_names: ["right_wheel_joint"]
    wheel_separation: 0.287
    wheel_radius: 0.033
    use_stamped_vel: false
"""
    return GeneratedFile(
        path="src/openrobo_bringup/config/ros2_control_params.yaml",
        content=yaml_content,
        description="ros2_control hardware and controller manager parameters",
    )
