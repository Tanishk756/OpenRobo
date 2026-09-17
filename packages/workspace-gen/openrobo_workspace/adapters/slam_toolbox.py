"""SLAM Toolbox Adapter."""

from openrobo_workspace.models import GeneratedFile


def has_slam_toolbox_adapter(resource_id: str) -> bool:
    rid = resource_id.lower()
    return "slam_toolbox" in rid or "slam-toolbox" in rid


def get_slam_toolbox_launch_snippet() -> str:
    return """    # SLAM Toolbox 2D Mapping Integration
    slam_params_file = os.path.join(bringup_share, 'config', 'slam_toolbox_params.yaml')
    slam_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('slam_toolbox'), 'launch', 'online_async_launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'params_file': slam_params_file,
        }.items()
    )
    ld.add_action(slam_launch)
"""


def get_slam_toolbox_params_file() -> GeneratedFile:
    yaml_content = """# OpenRobo Synthesized SLAM Toolbox Parameters
slam_toolbox:
  ros__parameters:
    use_sim_time: True
    solver_plugin: solver_plugins::CeresSolver
    ceres_linear_solver: SPARSE_NORMAL_CHOLESKY
    ceres_preconditioner: SCHUR_JACOBI
    ceres_trust_strategy: LEVENBERG_MARQUARDT

    odom_frame: odom
    map_frame: map
    base_frame: base_footprint
    scan_topic: /scan
    mode: mapping

    # Spatial resolution
    resolution: 0.05
    max_laser_range: 20.0
    minimum_time_interval: 0.5
    transform_timeout: 0.2
    tf_buffer_duration: 30.0
"""
    return GeneratedFile(
        path="src/openrobo_bringup/config/slam_toolbox_params.yaml",
        content=yaml_content,
        description="SLAM Toolbox 2D online async mapping parameters",
    )
