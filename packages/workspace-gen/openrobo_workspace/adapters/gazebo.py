"""Gazebo Simulator Adapter."""

from openrobo_workspace.models import GeneratedFile


def has_gazebo_adapter(resource_id: str) -> bool:
    rid = resource_id.lower()
    return "gazebo" in rid or "gz_sim" in rid or "ros_gz" in rid or "ignition" in rid


def get_gazebo_launch_snippet() -> str:
    return """    # Gazebo Simulator Environment Scaffolding
    gazebo_sim_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={'gz_args': '-r empty.sdf'}.items()
    )
    # Bridge clock and basic simulation topics
    gz_bridge_node = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
        output='screen'
    )
    ld.add_action(gazebo_sim_launch)
    ld.add_action(gz_bridge_node)
"""


def get_gazebo_params_file() -> GeneratedFile:
    yaml_content = """# OpenRobo Synthesized Gazebo Bridge Configuration
- ros_topic_name: "clock"
  gz_topic_name: "clock"
  ros_type_name: "rosgraph_msgs/msg/Clock"
  gz_type_name: "gz.msgs.Clock"
  direction: GZ_TO_ROS
"""
    return GeneratedFile(
        path="src/openrobo_bringup/config/gazebo_bridge.yaml",
        content=yaml_content,
        description="Gazebo ros_gz_bridge topic mapping configuration",
    )
