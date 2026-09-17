from openrobo_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def test_fleet_help():
    result = runner.invoke(app, ["fleet", "--help"])
    assert result.exit_code == 0
    assert "devices" in result.stdout
    assert "tokens-create" in result.stdout
    assert "revoke" in result.stdout


def test_agent_help():
    result = runner.invoke(app, ["agent", "--help"])
    assert result.exit_code == 0
    assert "init" in result.stdout
    assert "enroll" in result.stdout
    assert "status" in result.stdout
    assert "doctor" in result.stdout
    assert "service" in result.stdout


def test_agent_init_status_doctor(tmp_path):
    state_dir = str(tmp_path / "agent_state")

    # 1. Init
    res_init = runner.invoke(app, ["agent", "init", "--state-dir", state_dir, "--name", "test-bot"])
    assert res_init.exit_code == 0
    assert "Initialized Device Identity" in res_init.stdout
    assert "test-bot" in res_init.stdout

    # 2. Status
    res_status = runner.invoke(app, ["agent", "status", "--state-dir", state_dir])
    assert res_status.exit_code == 0
    assert "test-bot" in res_status.stdout
    assert "NOT ENROLLED" in res_status.stdout

    # 3. Doctor
    res_doc = runner.invoke(app, ["agent", "doctor", "--state-dir", state_dir])
    assert res_doc.exit_code == 0
    assert "Private Key" in res_doc.stdout

    # 4. Service generation
    res_svc = runner.invoke(app, ["agent", "service", "--state-dir", state_dir, "--user", "openrobo-agent"])
    assert res_svc.exit_code == 0
    assert "User=openrobo-agent" in res_svc.stdout
    assert "ProtectSystem=strict" in res_svc.stdout
