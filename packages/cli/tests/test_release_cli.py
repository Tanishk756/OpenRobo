"""CLI integration tests for openrobo release and openrobo agent deployment."""

from openrobo_agent.cli import agent_app
from openrobo_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def test_release_build_and_verify_cli(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROBO_DEV_RELEASE_SIGNING", "true")

    # Generate development key via CLI
    keys_dir = tmp_path / "keys"
    res_gen = runner.invoke(app, ["release", "key", "generate", "--dev", "--output-dir", str(keys_dir), "--key-id", "my-key"])
    assert res_gen.exit_code == 0
    assert (keys_dir / "my-key.key").exists()

    # Workspace
    ws = tmp_path / "my_ws"
    ws.mkdir()
    (ws / "package.xml").write_text("<package><name>cli_pkg</name></package>", encoding="utf-8")

    dist = tmp_path / "dist"

    # Build release with explicit private key
    res_build = runner.invoke(
        app,
        [
            "release",
            "build",
            str(ws),
            "--output-dir",
            str(dist),
            "--private-key",
            str(keys_dir / "my-key.key"),
            "--key-id",
            "my-key",
            "--release-id",
            "rel-cli-01",
            "--os",
            "any",
            "--arch",
            "any",
        ],
    )
    assert res_build.exit_code == 0
    assert (dist / "openrobo-rel-cli-01.tar.gz").exists()
    assert (dist / "openrobo-rel-cli-01.manifest.json").exists()
    assert (dist / "openrobo-rel-cli-01.sig").exists()

    # Verify release with trust directory
    res_ver = runner.invoke(
        app,
        [
            "release",
            "verify",
            str(dist / "openrobo-rel-cli-01.manifest.json"),
            str(dist / "openrobo-rel-cli-01.sig"),
            "--trust-dir",
            str(keys_dir),
        ],
    )
    assert res_ver.exit_code == 0
    assert "VALID" in res_ver.output


def test_agent_deployment_slots_cli(tmp_path):
    dep_root = tmp_path / "agent_deploy"
    res = runner.invoke(agent_app, ["deployment", "slots", "--root", str(dep_root)])
    assert res.exit_code == 0
    assert "slot-a" in res.output
    assert "slot-b" in res.output
