"""Unit tests for Connection Inspector External Integration."""

from openrobo_runtime import ConnectionInspectorAdapter, ConnectionInspectorStatus


def test_connection_inspector_detection_when_missing():
    adapter = ConnectionInspectorAdapter(ros2_cmd="nonexistent_ros2_binary_xyz")
    rep = adapter.detect()
    assert rep.status == ConnectionInspectorStatus.NOT_INSTALLED
    assert "GPL-3.0-only" in rep.licensing_notice


def test_connection_inspector_unsupported_distro():
    adapter = ConnectionInspectorAdapter()
    rep = adapter.detect(target_distro="foxy")
    assert rep.status == ConnectionInspectorStatus.UNSUPPORTED_DISTRO


def test_connection_inspector_safe_command_generation():
    adapter = ConnectionInspectorAdapter()
    cli_cmd = adapter.build_cli_inspect_command(topic_filter="/scan")
    assert cli_cmd == ["ros2", "run", "connection_inspector", "inspect_cli", "--topic", "/scan"]

    gui_cmd = adapter.build_gui_launch_command()
    assert gui_cmd == ["ros2", "run", "connection_inspector", "connection_inspector"]


def test_licensing_boundary_guarantee():
    adapter = ConnectionInspectorAdapter()
    rep = adapter.detect()
    assert "does not vendor or link GPL code" in rep.licensing_notice
