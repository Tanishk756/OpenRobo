from unittest.mock import MagicMock, patch

from openrobo_runtime.models import RosEnvironmentInfo, RosEnvironmentStatus
from openrobo_runtime.ros.collector import LiveRosGraphCollector


def test_collector_unavailable_when_ros_unavailable():
    collector = LiveRosGraphCollector()
    with patch(
        "openrobo_runtime.ros.availability.RosEnvironmentDetector.detect",
        return_value=RosEnvironmentInfo(status=RosEnvironmentStatus.UNAVAILABLE, rclpy_available=False, ros2_cli_available=False),
    ):
        report = collector.collect()
        assert report["status"] == "ROS_RUNTIME_UNAVAILABLE"
        assert report["nodes"] == []
        assert report["topics"] == []


def test_collector_falls_back_to_cli_and_parses_graph():
    collector = LiveRosGraphCollector()

    topic_stdout = "/scan [sensor_msgs/msg/LaserScan]\n/map [nav_msgs/msg/OccupancyGrid]\n"
    mock_topic_proc = MagicMock(return_value=MagicMock(returncode=0, stdout=topic_stdout))
    mock_node_proc = MagicMock(return_value=MagicMock(returncode=0, stdout="/slam_toolbox\n/rplidar_node\n"))

    with patch("shutil.which", return_value="/usr/bin/ros2"):
        with patch(
            "openrobo_runtime.ros.availability.RosEnvironmentDetector.detect",
            return_value=RosEnvironmentInfo(status=RosEnvironmentStatus.AVAILABLE, rclpy_available=False, ros2_cli_available=True),
        ):
            with patch("subprocess.run") as mock_run:

                def side_effect(cmd, **kwargs):
                    if "node" in cmd:
                        return mock_node_proc()
                    if "topic" in cmd:
                        return mock_topic_proc()
                    return MagicMock(returncode=1, stdout="")

                mock_run.side_effect = side_effect
                report = collector.collect()

                assert report["status"] == "COLLECTED_VIA_CLI"
                assert report["method"] == "ros2_cli_fallback"
                node_names = [n["name"] for n in report["nodes"]]
                assert "slam_toolbox" in node_names
                assert "rplidar_node" in node_names
                topic_names = [t["name"] for t in report["topics"]]
                assert "/scan" in topic_names
                assert "/map" in topic_names
