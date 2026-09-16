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
