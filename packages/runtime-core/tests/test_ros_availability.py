import os
from unittest.mock import patch

from openrobo_runtime.models import RosEnvironmentStatus
from openrobo_runtime.ros.availability import RosEnvironmentDetector


def test_ros_environment_detector_unavailable():
    with patch.dict(os.environ, {}, clear=True):
        with patch("shutil.which", return_value=None):
            detector = RosEnvironmentDetector()
            info = detector.detect()
            assert info.status == RosEnvironmentStatus.UNAVAILABLE
            assert info.distro is None
            assert info.ros2_cli_available is False


def test_ros_environment_detector_with_env_vars():
    env = {
        "ROS_DISTRO": "humble",
        "ROS_VERSION": "2",
        "RMW_IMPLEMENTATION": "rmw_cyclonedds_cpp",
        "ROS_DOMAIN_ID": "42",
        "AMENT_PREFIX_PATH": "/opt/ros/humble",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("shutil.which", return_value="/opt/ros/humble/bin/ros2"):
            detector = RosEnvironmentDetector()
            info = detector.detect()
            assert info.status in [RosEnvironmentStatus.AVAILABLE, RosEnvironmentStatus.MISCONFIGURED]
            assert info.distro == "humble"
            assert info.domain_id == 42
            assert info.rmw_implementation == "rmw_cyclonedds_cpp"
            assert info.ros2_cli_available is True
