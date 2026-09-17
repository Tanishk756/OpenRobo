"""Nav2 Navigation Framework Adapter."""

from openrobo_workspace.models import GeneratedFile


def has_nav2_adapter(resource_id: str) -> bool:
    rid = resource_id.lower()
    return "nav2" in rid or "navigation2" in rid


def get_nav2_launch_snippet() -> str:
    return """    # Nav2 Navigation Framework Launch Integration
    nav2_params_file = os.path.join(bringup_share, 'config', 'nav2_params.yaml')
    nav2_bringup_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('nav2_bringup'), 'launch', 'navigation_launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'params_file': nav2_params_file,
            'autostart': 'true',
        }.items()
    )
    ld.add_action(nav2_bringup_launch)
"""


def get_nav2_params_file() -> GeneratedFile:
    yaml_content = """# OpenRobo Synthesized Nav2 Parameters
amcl:
  ros__parameters:
    use_sim_time: True
    alpha1: 0.2
    alpha2: 0.2
    alpha3: 0.2
    alpha4: 0.2
    alpha5: 0.2
    base_frame_id: "base_footprint"
    global_frame_id: "map"
    odom_frame_id: "odom"
    scan_topic: scan

controller_server:
  ros__parameters:
    use_sim_time: True
    controller_frequency: 20.0
    min_x_velocity_threshold: 0.001
    min_y_velocity_threshold: 0.5
    min_theta_velocity_threshold: 0.001
    failure_tolerance: 0.3
    progress_checker_plugin: "progress_checker"
    goal_checker_plugins: ["general_goal_checker"]
    controller_plugins: ["FollowPath"]

planner_server:
  ros__parameters:
    expected_planner_frequency: 20.0
    use_sim_time: True
    planner_plugins: ["GridBased"]
    GridBased:
      plugin: "nav2_navfn_planner/NavfnPlanner"
      tolerance: 0.5
      use_astar: false
      allow_unknown: true

bt_navigator:
  ros__parameters:
    use_sim_time: True
    global_frame: map
    robot_base_frame: base_link
    odom_topic: /odom
"""
    return GeneratedFile(
        path="src/openrobo_bringup/config/nav2_params.yaml",
        content=yaml_content,
        description="Standard Nav2 parameters for autonomous navigation",
    )
