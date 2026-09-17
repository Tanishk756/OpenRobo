from unittest.mock import MagicMock, patch

from openrobo_runtime.integrations.connection_inspector import ConnectionInspectorAdapter
from openrobo_runtime.models import ConnectionInspectorStatus, DistroReleaseSupport


def test_connection_inspector_missing():
    with patch("shutil.which", return_value=None):
        adapter = ConnectionInspectorAdapter()
        report = adapter.detect()
        assert report.status == ConnectionInspectorStatus.NOT_INSTALLED
        assert "GPL-3.0-only" in report.licensing_notice
        assert report.executables == []
        assert report.version is None


def test_connection_inspector_unsupported_distro():
    adapter = ConnectionInspectorAdapter()
    report = adapter.detect(target_distro="foxy")
    assert report.status == ConnectionInspectorStatus.UNSUPPORTED_DISTRO
    assert report.distro_support == DistroReleaseSupport.UNSUPPORTED


def test_connection_inspector_installed_with_dynamic_discovery():
    with patch("shutil.which", return_value="/usr/bin/ros2"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="/opt/ros/humble\n", stderr="")
            with patch("os.path.isdir", return_value=True):
                with patch("os.path.isfile", return_value=True):
                    adapter = ConnectionInspectorAdapter()
                    report = adapter.detect(target_distro="humble")
                    assert report.status == ConnectionInspectorStatus.INSTALLED
                    assert report.distro_support == DistroReleaseSupport.VERIFIED_RELEASE
                    assert "inspect_cli" in report.executables
                    assert "GPL-3.0-only" in report.licensing_notice


def test_connection_inspector_command_builders():
    adapter = ConnectionInspectorAdapter()
    cli_cmd = adapter.build_cli_inspect_command()
    gui_cmd = adapter.build_gui_launch_command()

    assert cli_cmd == ["ros2", "run", "connection_inspector", "inspect_cli"]
    assert gui_cmd == ["ros2", "run", "connection_inspector", "connection_inspector"]
