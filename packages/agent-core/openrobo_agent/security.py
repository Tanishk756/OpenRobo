"""OpenRobo Agent Security, Permission Validation, and Secret Redaction."""

import os
import re
from pathlib import Path
from typing import Any, Dict

# Regex patterns for sensitive secret data
TOKEN_REGEX = re.compile(r"(?i)(bearer\s+[a-zA-Z0-9_\-\.]{16,})|(token[\"']?\s*[:=]\s*[\"']?[a-zA-Z0-9_\-\.]{16,}[\"']?)")
KEY_BLOCK_REGEX = re.compile(r"-----BEGIN (EC |RSA |OPENSSH )?PRIVATE KEY-----[\s\S]+?-----END (EC |RSA |OPENSSH )?PRIVATE KEY-----")
AUTH_HEADER_REGEX = re.compile(r"(?i)(authorization[\"']?\s*[:=]\s*[\"']?)[^\s\"']+", re.IGNORECASE)


def redact_sensitive_text(text: str) -> str:
    """Redact private keys, tokens, and authorization credentials from log text."""
    if not text or not isinstance(text, str):
        return text
    redacted = KEY_BLOCK_REGEX.sub("[REDACTED_PRIVATE_KEY]", text)
    redacted = TOKEN_REGEX.sub("[REDACTED_TOKEN]", redacted)
    redacted = AUTH_HEADER_REGEX.sub(r"\1[REDACTED_HEADER]", redacted)
    return redacted


def sanitize_telemetry_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure telemetry dictionaries do not leak environment variables, passwords, or PII."""
    sanitized: Dict[str, Any] = {}
    blocked_keys = {
        "env", "environment", "environ", "password", "secret", "token", "key",
        "auth", "credential", "ssid", "wifi", "username", "home", "user",
    }

    for k, v in payload.items():
        k_lower = str(k).lower()
        if any(b in k_lower for b in blocked_keys):
            sanitized[k] = "[REDACTED]"
            continue

        if isinstance(v, dict):
            sanitized[k] = sanitize_telemetry_payload(v)
        elif isinstance(v, str):
            sanitized[k] = redact_sensitive_text(v)
        elif isinstance(v, (int, float, bool, list)):
            sanitized[k] = v
        else:
            sanitized[k] = str(v)

    return sanitized


def validate_file_permissions(path: Path, expected_mode: int = 0o600) -> bool:
    """Validate that private key or credential file permissions are strict on POSIX."""
    if not path.exists():
        return True
    if os.name == "nt":
        # Windows ACLs differ from POSIX file mode bits
        return True
    try:
        stat_res = path.stat()
        mode = stat_res.st_mode & 0o777
        return mode == expected_mode
    except Exception:
        return False


def set_secure_file_permissions(path: Path, mode: int = 0o600) -> None:
    """Set restrictive file permissions (0600) on POSIX systems."""
    if not path.exists():
        return
    if os.name != "nt":
        try:
            os.chmod(path, mode)
        except Exception:
            pass

check_file_permissions = validate_file_permissions
