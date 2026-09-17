"""OpenRobo Agent Configuration & Path Resolution."""

import os
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

    def ensure_directories(self) -> None:
        """Create state and config directories with appropriate permissions."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
