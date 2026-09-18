"""Unit tests for release and agent deployment CLI commands."""

from openrobo_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def test_cli_release_build_and_verify(tmp_path):
    """Test 'openrobo release build' and 'openrobo release verify' through CLI runner."""
    ws_dir = tmp_path / "cli_ws"
    ws_dir.mkdir()
    (ws_dir / "main.py").write_text("print('cli build')", encoding="utf-8")
    dist_dir = tmp_path / "dist"

    res_build = runner.invoke(app, [
        "release", "build", str(ws_dir),
        "--output-dir", str(dist_dir),
        "--release-id", "rel-cli-test",
        "--version", "1.0.0",
        "--key-id", "cli-test-key",
    ])
    assert res_build.exit_code == 0
    assert "Release Package Built Successfully" in res_build.stdout

    manifest_file = dist_dir / "rel-cli-test.manifest.json"
    sig_file = dist_dir / "rel-cli-test.sig"
    pub_file = dist_dir / "cli-test-key.pub.pem"
    art_file = dist_dir / "rel-cli-test.tar.gz"

    assert manifest_file.exists()
    assert sig_file.exists()
    assert pub_file.exists()
    assert art_file.exists()

    res_verify = runner.invoke(app, [
        "release", "verify",
        str(manifest_file),
        str(sig_file),
        "--public-key", str(pub_file),
        "--artifact", str(art_file),
    ])
    assert res_verify.exit_code == 0
    assert "VERIFICATION SUCCESSFUL" in res_verify.stdout


def test_cli_agent_deployment_slots(tmp_path):
    """Test 'openrobo agent deployment slots' command."""
    state_dir = tmp_path / "agent_state"
    res = runner.invoke(app, [
        "agent", "deployment", "slots",
        "--state-dir", str(state_dir),
    ])
    assert res.exit_code == 0
    assert "OpenRobo A/B Workspace Deployment Slots" in res.stdout
    assert "slot-a" in res.stdout
    assert "slot-b" in res.stdout
