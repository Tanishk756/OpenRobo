from unittest.mock import MagicMock, patch

from openrobo_runtime.models import ProviderStatus
from openrobo_runtime.providers.local import LocalProcessProvider
from openrobo_runtime.providers.podman import PodmanProvider


def test_local_process_provider_filters_disallowed_env_vars():
    provider = LocalProcessProvider()
    with patch("shutil.which", return_value="/usr/bin/colcon"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="build success", stderr="")

            malicious_env = {
                "LD_PRELOAD": "/evil/lib.so",
                "PYTHONPATH": "/injected/scripts",
                "ROS_DISTRO": "jazzy",
                "ROS_DOMAIN_ID": "10",
                "CUSTOM_UNKNOWN": "some_value",
            }

            res = provider.build_workspace(
                workspace_dir=".",
                env_vars=malicious_env,
            )

            assert res.status.value == "PASSED"
            assert mock_run.called
            passed_env = mock_run.call_args[1]["env"]

            # Safe vars kept
            assert passed_env.get("ROS_DISTRO") == "jazzy"
            assert passed_env.get("ROS_DOMAIN_ID") == "10"
            # Unsafe or unknown vars strictly excluded
            assert "LD_PRELOAD" not in passed_env
            assert "PYTHONPATH" not in passed_env
            assert "CUSTOM_UNKNOWN" not in passed_env


def test_podman_provider_reports_not_implemented():
    provider = PodmanProvider()
    with patch("shutil.which", return_value="/usr/bin/podman"):
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="podman version 4.9")):
            info = provider.detect_availability()
            assert info.status == ProviderStatus.DETECTED_NOT_IMPLEMENTED
            assert info.supports_build_verification is False

            res = provider.build_workspace(workspace_dir=".")
            assert res.status.value == "NOT_EXECUTED"
