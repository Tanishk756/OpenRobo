from openrobo_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "OpenRobo CLI" in result.stdout


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "openrobo" in result.stdout.lower()


def test_cli_info():
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "OpenRobo Infrastructure Platform" in result.stdout


def test_cli_ingest_help():
    result = runner.invoke(app, ["ingest", "--help"])
    assert result.exit_code == 0
    assert "github" in result.stdout.lower()


def test_cli_ingest_github_help():
    result = runner.invoke(app, ["ingest", "github", "--help"])
    assert result.exit_code == 0
    assert "repository_url" in result.stdout.lower()


def test_cli_search_help():
    result = runner.invoke(app, ["search", "--help"])
    assert result.exit_code == 0
    assert "search" in result.stdout.lower()


def test_cli_search_query():
    result = runner.invoke(app, ["search", "slam"])
    assert result.exit_code == 0
    assert "SLAM" in result.stdout or "Resource ID" in result.stdout


def test_cli_runtime_help():
    result = runner.invoke(app, ["runtime", "--help"])
    assert result.exit_code == 0
    assert "providers" in result.stdout
    assert "build-verify" in result.stdout
    assert "connection-inspector" in result.stdout
    assert "simulators" in result.stdout
    assert "rosbag" in result.stdout


def test_cli_runtime_providers():
    result = runner.invoke(app, ["runtime", "providers"])
    assert result.exit_code == 0
    assert "Execution Providers" in result.stdout
    assert "local_process" in result.stdout or "docker" in result.stdout


def test_cli_runtime_connection_inspector():
    result = runner.invoke(app, ["runtime", "connection-inspector"])
    assert result.exit_code == 0
    assert "Connection Inspector Status" in result.stdout
    assert "Licensing Notice" in result.stdout
    assert "GPL-3.0-only" in result.stdout


def test_cli_runtime_simulators():
    result = runner.invoke(app, ["runtime", "simulators"])
    assert result.exit_code == 0
    assert "Simulation Adapters" in result.stdout
    assert "gazebo" in result.stdout
    assert "webots" in result.stdout
    assert "mujoco" in result.stdout
