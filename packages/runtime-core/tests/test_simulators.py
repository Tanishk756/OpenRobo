"""Unit tests for Simulator Adapters (Gazebo, Webots, MuJoCo)."""

from openrobo_runtime import GazeboAdapter, MujocoAdapter, WebotsAdapter


def test_gazebo_adapter_detection_and_command():
    gz = GazeboAdapter()
    det = gz.detect()
    assert "installed" in det
    assert det["simulator"] == "gazebo"

    cmd = gz.build_launch_command(
        workspace_path="/tmp/ws",
        bringup_pkg="openrobo_bringup",
        headless=True,
    )
    assert "ros2" in cmd
    assert "launch" in cmd
    assert "openrobo_bringup" in cmd
    assert "use_sim_time:=true" in cmd
    assert "headless:=true" in cmd


def test_webots_adapter_command():
    webots = WebotsAdapter()
    cmd = webots.build_launch_command(
        workspace_path="/tmp/ws",
        bringup_pkg="openrobo_bringup",
        headless=True,
    )
    assert "--batch" in cmd


def test_mujoco_adapter_detection():
    mujoco_adapter = MujocoAdapter()
    det = mujoco_adapter.detect()
    assert "simulator" in det
    assert det["simulator"] == "mujoco"
