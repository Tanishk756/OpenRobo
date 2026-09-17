"""Unit tests for BuildRunner and ExecutionProviders."""

from openrobo_runtime import (
    BuildRunner,
    BuildStatus,
    ExecutionProviderType,
    ProviderDetector,
    ProviderStatus,
)


def test_provider_detector_discovery():
    detector = ProviderDetector()
    all_provs = detector.detect_all()

    assert ExecutionProviderType.DOCKER in all_provs
    assert ExecutionProviderType.PODMAN in all_provs
    assert ExecutionProviderType.LOCAL_PROCESS in all_provs

    # Preferred provider returns valid tuple
    ptype, provider, info = detector.get_preferred_provider()
    assert ptype in [ExecutionProviderType.DOCKER, ExecutionProviderType.LOCAL_PROCESS, ExecutionProviderType.PODMAN]
    assert info.status in [ProviderStatus.AVAILABLE, ProviderStatus.UNAVAILABLE, ProviderStatus.ERROR]


def test_build_runner_missing_workspace(tmp_path):
    runner = BuildRunner()
    res = runner.verify_workspace_build(str(tmp_path / "nonexistent_dir"))
    assert res.status == BuildStatus.FAILED
    assert any("does not exist" in err for err in res.errors)


def test_build_runner_blocked_by_unconfigured_example(tmp_path):
    # Workspace containing unconfigured ros2_control_params.yaml.example
    ws_dir = tmp_path / "test_ws"
    config_dir = ws_dir / "src" / "openrobo_bringup" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "ros2_control_params.yaml.example").write_text("wheel_separation: 0.0")

    runner = BuildRunner()
    res = runner.verify_workspace_build(str(ws_dir))
    assert res.status == BuildStatus.FAILED
    assert any("Build blocked" in err for err in res.errors)
