"""ros2_control Adapter for OpenRobo Workspace Generator (Hardened).

STRICT SAFETY POLICY:
Never emit guessed robot-specific values (wheel joints, separation, radius).
If hardware configuration is missing, emit a .example scaffold with clear placeholders.
"""

from typing import Any, Dict, Optional

import yaml
from openrobo_workspace.models import GeneratedFile


def has_ros2_control_adapter(resource_id: str) -> bool:
    canonical_control_ids = {
        "ros2_control",
        "ros2_controllers",
        "ros-controls/ros2_control",
        "ros-controls/ros2_controllers",
    }
    return resource_id.lower() in canonical_control_ids


def get_ros2_control_launch_snippet() -> str:
    return """
    # --- ros2_control Subsystem Launch (Verified) ---
    ros2_control_params = os.path.join(bringup_share, 'config', 'ros2_control_params.yaml')
    if os.path.exists(ros2_control_params):
        controller_manager_node = Node(
            package='controller_manager',
            executable='ros2_control_node',
            parameters=[ros2_control_params, {'use_sim_time': use_sim_time}],
            output='screen',
        )
        ld.add_action(controller_manager_node)
    else:
        ld.add_action(LogInfo(
            msg='[OpenRobo] ros2_control_params.yaml not found. Configure joint hardware before enabling ros2_control_node.'
        ))
"""


def get_ros2_control_params_file(user_config: Optional[Dict[str, Any]] = None) -> GeneratedFile:
    """Generate ros2_control parameters ONLY if explicitly configured by user."""
    ctrl_cfg = user_config or {}

    controller_type = ctrl_cfg.get("controller_type", "diff_drive_controller/DiffDriveController")
    left_wheel_names = ctrl_cfg.get("left_wheel_names")
    right_wheel_names = ctrl_cfg.get("right_wheel_names")
    wheel_separation = ctrl_cfg.get("wheel_separation")
    wheel_radius = ctrl_cfg.get("wheel_radius")

    if left_wheel_names and right_wheel_names and wheel_separation is not None and wheel_radius is not None:
        params_dict = {
            "controller_manager": {
                "ros__parameters": {
                    "update_rate": ctrl_cfg.get("update_rate", 50),
                    "diff_drive_controller": {"type": controller_type},
                    "joint_state_broadcaster": {"type": "joint_state_broadcaster/JointStateBroadcaster"},
                }
            },
            "diff_drive_controller": {
                "ros__parameters": {
                    "left_wheel_names": left_wheel_names,
                    "right_wheel_names": right_wheel_names,
                    "wheel_separation": float(wheel_separation),
                    "wheel_radius": float(wheel_radius),
                    "use_stamped_vel": False,
                    "publish_rate": 50.0,
                    "odom_frame_id": ctrl_cfg.get("odom_frame_id", "odom"),
                    "base_frame_id": ctrl_cfg.get("base_frame_id", "base_link"),
                }
            },
        }

        yaml_content = "# ==============================================================================\n"
        yaml_content += "# ros2_control Parameter Configuration (USER CONFIGURED)\n"
        yaml_content += "# Evidence Level: USER_CONFIGURED (Explicit hardware joints and geometry provided)\n"
        yaml_content += "# ==============================================================================\n\n"
        yaml_content += yaml.safe_dump(params_dict, sort_keys=False)

        return GeneratedFile(
            path="src/openrobo_bringup/config/ros2_control_params.yaml",
            content=yaml_content,
            description="ros2_control controller parameters with user-provided hardware geometry",
        )
    else:
        example_content = """# ==============================================================================
# ros2_control Parameter Configuration TEMPLATE (MANUAL CONFIGURATION REQUIRED)
# Evidence Level: GENERIC_SCAFFOLD
#
# IMPORTANT: OpenRobo will NOT guess robot wheel joint names or dimensions.
# To activate ros2_control:
#   1. Copy or rename this file to 'ros2_control_params.yaml'
#   2. Replace the joint names and physical dimensions below with your robot's exact URDF joints.
# ==============================================================================
controller_manager:
  ros__parameters:
    update_rate: 50
    diff_drive_controller:
      type: diff_drive_controller/DiffDriveController
    joint_state_broadcaster:
      type: joint_state_broadcaster/JointStateBroadcaster

diff_drive_controller:
  ros__parameters:
    # REQUIRED: Replace with exact joint names defined in your robot URDF / ros2_control tag:
    left_wheel_names:
      - left_wheel_joint  # TODO: Set your left wheel joint name(s)
    right_wheel_names:
      - right_wheel_joint # TODO: Set your right wheel joint name(s)

    # REQUIRED: Replace with exact physical dimensions (meters):
    wheel_separation: 0.0 # TODO: Distance between left and right wheels in meters
    wheel_radius: 0.0     # TODO: Wheel radius in meters

    use_stamped_vel: false
    publish_rate: 50.0
    odom_frame_id: odom
    base_frame_id: base_link
"""
        return GeneratedFile(
            path="src/openrobo_bringup/config/ros2_control_params.yaml.example",
            content=example_content,
            description="ros2_control configuration template (manual hardware parameters required)",
        )
