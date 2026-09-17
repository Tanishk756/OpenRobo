"""OpenRobo Agent & Fleet Data Models (Milestone 7.1)."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


def utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class DeviceStatus(str, Enum):
    """Device lifecycle and operational status."""

    PENDING_ENROLLMENT = "PENDING_ENROLLMENT"
    ENROLLED = "ENROLLED"
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    REVOKED = "REVOKED"
    UNKNOWN = "UNKNOWN"


class AgentCapability(BaseModel):
    """Discovered hardware and runtime capabilities on the robot edge."""

    ros_runtime: bool = False
    docker: bool = False
    podman: bool = False
    gazebo: bool = False
    connection_inspector: bool = False
    gpu: bool = False
    hardware_telemetry: bool = True
    distro: Optional[str] = None
    rmw: Optional[str] = None


class DeviceIdentity(BaseModel):
    """Cryptographic and platform identity of a registered OpenRobo robot device."""

    device_id: str = Field(..., description="Unique Device UUID")
    display_name: str = Field(..., description="Human readable device name")
    public_key_fingerprint: str = Field(..., description="SHA-256 fingerprint of device public key")
    certificate_fingerprint: Optional[str] = Field(None, description="SHA-256 fingerprint of active device certificate")
    certificate_serial: Optional[str] = Field(None, description="Hex serial number of active device certificate")
    platform: str = Field(..., description="OS Platform e.g. linux, darwin, win32")
    architecture: str = Field(..., description="CPU Architecture e.g. x86_64, aarch64")
    os_name: str = Field(..., description="Operating system distribution name e.g. Ubuntu 22.04")
    agent_version: str = Field(default="0.7.0", description="OpenRobo agent software version")
    created_at: str = Field(default_factory=utc_now_str)


class EnrollmentTokenPayload(BaseModel):
    """Enrollment token metadata provided to an edge robot."""

    token: str = Field(..., description="Single-use random token string")
    control_plane_url: str = Field(..., description="Control plane base URL")
    device_id: Optional[str] = Field(None, description="Optional pre-assigned device UUID")
    expires_at: str = Field(..., description="ISO timestamp of token expiry")


class EnrollmentRequest(BaseModel):
    """CSR and identity payload sent by agent to enroll with control plane."""

    token: Optional[str] = Field(None, description="Single-use enrollment token")
    enrollment_token: Optional[str] = Field(None, description="Alias for token")
    device_id: str = Field(..., description="Client-generated device UUID")
    csr_pem: str = Field(..., description="PEM-encoded X.509 Certificate Signing Request")
    device_name: Optional[str] = Field(None, description="Device name")
    display_name: Optional[str] = Field(None, description="Display name")
    domain: str = Field(default="general_robotics")
    robot_type: str = Field(default="custom")
    platform: str = Field(default="linux")
    architecture: str = Field(default="x86_64")
    os_name: str = Field(default="Ubuntu 22.04")
    agent_version: str = Field(default="0.7.0")
    capabilities: Optional[Any] = None

    def get_token(self) -> str:
        tok = self.enrollment_token or self.token
        if not tok:
            raise ValueError("Enrollment token must be provided")
        return tok


class EnrollmentResponse(BaseModel):
    """Signed certificate response from control plane."""

    device_id: str
    certificate_pem: str
    ca_certificate_pem: str
    certificate_fingerprint: str
    certificate_serial: str
    expires_at: str
    status: DeviceStatus = DeviceStatus.ONLINE


class AgentOperationType(str, Enum):
    """Strictly typed, read-oriented fleet operations allowed in Milestone 7.1."""

    PING = "PING"
    GET_AGENT_INFO = "GET_AGENT_INFO"
    GET_RUNTIME_STATUS = "GET_RUNTIME_STATUS"
    GET_ROS_ENVIRONMENT = "GET_ROS_ENVIRONMENT"
    GET_ROS_GRAPH = "GET_ROS_GRAPH"
    GET_RUNTIME_DIAGNOSTICS = "GET_RUNTIME_DIAGNOSTICS"
    GET_CONNECTION_INSPECTOR_STATUS = "GET_CONNECTION_INSPECTOR_STATUS"
    GET_SIMULATOR_STATUS = "GET_SIMULATOR_STATUS"


class HeartbeatPayload(BaseModel):
    """Periodic edge health and runtime status packet."""

    device_id: str
    agent_version: str = "0.7.0"
    timestamp: str = Field(default_factory=utc_now_str)
    status: DeviceStatus = DeviceStatus.ONLINE
    uptime_seconds: float = 0.0
    ros_distro: Optional[str] = None
    runtime_status: Optional[str] = None
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    disk_percent: Optional[float] = None
    capabilities: Optional[AgentCapability] = None


class TelemetryEventType(str, Enum):
    """Categories of edge telemetry events."""

    HEARTBEAT = "HEARTBEAT"
    NODE_STATE_CHANGE = "NODE_STATE_CHANGE"
    TOPIC_STATE_CHANGE = "TOPIC_STATE_CHANGE"
    QOS_WARNING = "QOS_WARNING"
    RUNTIME_VERIFICATION_EVIDENCE = "RUNTIME_VERIFICATION_EVIDENCE"
    DIAGNOSTIC_EVENT = "DIAGNOSTIC_EVENT"


class TelemetryMessage(BaseModel):
    """Structured telemetry data packet."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: TelemetryEventType
    device_id: str
    timestamp: str = Field(default_factory=utc_now_str)
    payload: Dict[str, Any] = Field(default_factory=dict)


class MessageEnvelope(BaseModel):
    """Standardized versioned message envelope for transport over WebSocket or HTTP."""

    protocol_version: str = Field(default="1.0", description="OpenRobo agent protocol version")
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str = Field(..., description="Device UUID")
    timestamp: str = Field(default_factory=utc_now_str)
    message_type: str = Field(..., description="Type identifier e.g. HEARTBEAT, TELEMETRY, OPERATION_REQ, OPERATION_RESP")
    payload: Dict[str, Any] = Field(default_factory=dict)
    signature: Optional[str] = None
