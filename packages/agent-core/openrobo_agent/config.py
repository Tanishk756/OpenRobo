"""OpenRobo Agent Configuration & Path Resolution."""

import os
import urllib.parse
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


def get_default_state_dir() -> Path:
    """Get standard state directory with user fallback."""
    if os.name != "nt" and os.path.exists("/var/lib") and os.access("/var/lib", os.W_OK):
        return Path("/var/lib/openrobo-agent")
    user_home = Path.home()
    return user_home / ".openrobo" / "agent" / "data"


def get_default_config_dir() -> Path:
    """Get standard config directory with user fallback."""
    if os.name != "nt" and os.path.exists("/etc") and os.access("/etc", os.W_OK):
        return Path("/etc/openrobo-agent")
    user_home = Path.home()
    return user_home / ".openrobo" / "agent" / "config"


class AgentConfig(BaseModel):
    """Configuration settings for OpenRobo remote agent."""

    control_plane_url: str = Field(default="http://localhost:8000", description="Base URL of OpenRobo fleet API")
    deployment_ws_url: Optional[str] = Field(default=None, description="Explicit WebSocket URL for deployment session")
    state_dir: Path = Field(default_factory=get_default_state_dir, description="Directory for keys, certs, and spool")
    config_dir: Path = Field(default_factory=get_default_config_dir, description="Directory for agent configuration")
    device_id: Optional[str] = Field(None, description="Assigned or generated device UUID")
    display_name: str = Field(default="robot-node", description="Human-readable node label")
    heartbeat_interval_sec: float = Field(default=10.0, description="Heartbeat frequency in seconds")
    telemetry_interval_sec: float = Field(default=5.0, description="Telemetry sampler frequency in seconds")
    spool_max_events: int = Field(default=5000, description="Maximum offline spool queue size")
    spool_max_bytes: int = Field(default=50 * 1024 * 1024, description="Maximum offline spool disk limit (50 MB)")
    spool_max_age_days: int = Field(default=7, description="Maximum telemetry event age before expiration")
    allow_dev_ca: bool = Field(default=False, description="Explicit development CA usage flag")

    @property
    def key_path(self) -> Path:
        return self.state_dir / "device.key"

    @property
    def cert_path(self) -> Path:
        return self.state_dir / "device.crt"

    @property
    def ca_cert_path(self) -> Path:
        return self.state_dir / "ca.crt"

    @property
    def identity_path(self) -> Path:
        return self.state_dir / "identity.json"

    @property
    def spool_path(self) -> Path:
        return self.state_dir / "spool.db"

    @property
    def status_outbox_path(self) -> Path:
        return self.state_dir / "deployment_status_outbox.json"

    @property
    def trusted_keys_dir(self) -> Path:
        cfg_path_rel = self.config_dir / "trusted-release-keys"
        if cfg_path_rel.exists():
            return cfg_path_rel
        cfg_path_keys = self.config_dir / "trusted_keys"
        if cfg_path_keys.exists():
            return cfg_path_keys
        state_path_rel = self.state_dir / "trusted-release-keys"
        if state_path_rel.exists():
            return state_path_rel
        return self.state_dir / "trusted_keys"

    @property
    def artifact_sources_path(self) -> Path:
        cfg_path = self.config_dir / "artifact_sources.json"
        if cfg_path.exists():
            return cfg_path
        return self.state_dir / "artifact_sources.json"

    def get_deployment_ws_url(self) -> str:
        """Derives and validates deployment WebSocket URL."""
        if self.deployment_ws_url:
            raw_url = self.deployment_ws_url
        else:
            base = self.control_plane_url.rstrip("/")
            if base.startswith("https://"):
                raw_url = f"wss://{base[8:]}/api/v1/fleet/agent/ws"
            elif base.startswith("http://"):
                env_mode = os.environ.get("ENVIRONMENT", "").lower()
                allow_dev_ws = os.environ.get("OPENROBO_ALLOW_DEV_AGENT_WS", "").lower() in ("true", "1", "yes")
                if not (self.allow_dev_ca or env_mode in ("development", "test") or allow_dev_ws):
                    raise ValueError(
                        f"Insecure ws:// deployment transport '{base}' is prohibited in production. "
                        "wss:// is required unless ENVIRONMENT=development and OPENROBO_ALLOW_DEV_AGENT_WS=true."
                    )
                raw_url = f"ws://{base[7:]}/api/v1/fleet/agent/ws"
            else:
                raw_url = f"{base}/api/v1/fleet/agent/ws"

        parsed = urllib.parse.urlparse(raw_url)
        if parsed.scheme not in ("wss", "ws"):
            raise ValueError(f"Invalid WebSocket scheme '{parsed.scheme}'. Must be wss:// or ws://")
        return raw_url

    def ensure_directories(self) -> None:
        """Create state and config directories with appropriate permissions."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
