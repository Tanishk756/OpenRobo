"""Unit tests for agent security, secret redaction, and permission validation."""

import tempfile
from pathlib import Path

from openrobo_agent.security import (
    redact_sensitive_text,
    sanitize_telemetry_payload,
    set_secure_file_permissions,
    validate_file_permissions,
)


def test_secret_redaction_in_text():
    sample_log = """
    Connecting with token: abcd1234efgh5678ijkl9012 and Authorization: Bearer secret_bearer_token_xyz_12345
    -----BEGIN PRIVATE KEY-----
    MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg...
    -----END PRIVATE KEY-----
    Done with transaction.
    """
    redacted = redact_sensitive_text(sample_log)
    assert "secret_bearer_token" not in redacted
    assert "MIGHAgE" not in redacted
    assert "[REDACTED_PRIVATE_KEY]" in redacted


def test_telemetry_payload_sanitization():
    payload = {
        "robot_name": "turtlebot4",
        "cpu_percent": 12.5,
        "wifi_ssid": "SecretCorpNetwork",
        "user_password": "supersecretpassword",
        "env_vars": {"AWS_SECRET_KEY": "12345"},
        "nested": {
            "status": "HEALTHY",
            "token": "sensitive_session_token_1234",
        },
    }
    sanitized = sanitize_telemetry_payload(payload)

    assert sanitized["robot_name"] == "turtlebot4"
    assert sanitized["cpu_percent"] == 12.5
    assert sanitized["wifi_ssid"] == "[REDACTED]"
    assert sanitized["user_password"] == "[REDACTED]"
    assert sanitized["env_vars"] == "[REDACTED]"
    assert sanitized["nested"]["token"] == "[REDACTED]"
    assert sanitized["nested"]["status"] == "HEALTHY"


def test_filesystem_permissions():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = Path(f.name)
    try:
        set_secure_file_permissions(path, 0o600)
        assert validate_file_permissions(path, 0o600) is True
    finally:
        if path.exists():
            path.unlink()
