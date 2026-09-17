"""Data models for OpenRobo Runtime Verification, Introspection, and Simulation (Milestone 6)."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExecutionProviderType(str, Enum):
    DOCKER = "docker"
    PODMAN = "podman"
    LOCAL_PROCESS = "local_process"
    MOCK = "mock"


class ProviderStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


class BuildStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_EXECUTED = "NOT_EXECUTED"
    RUNNING = "RUNNING"


class RuntimeSessionStatus(str, Enum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class OverallHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class QoSPolicyCompatibility(str, Enum):
    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNKNOWN = "UNKNOWN"


class ConnectionInspectorStatus(str, Enum):
    INSTALLED = "INSTALLED"
    NOT_INSTALLED = "NOT_INSTALLED"
    UNSUPPORTED_DISTRO = "UNSUPPORTED_DISTRO"
    ERROR = "ERROR"


class ProviderInfo(BaseModel):
    provider_type: ExecutionProviderType
    status: ProviderStatus
    version: Optional[str] = None
    details: Optional[str] = None


class BuildVerificationResult(BaseModel):
    status: BuildStatus = BuildStatus.NOT_EXECUTED
    provider: ExecutionProviderType = ExecutionProviderType.LOCAL_PROCESS
    started_at: str = Field(default_factory=utc_now_str)
    duration_ms: int = 0
    workspace_digest: str = ""
    docker_build_status: BuildStatus = BuildStatus.NOT_EXECUTED
    rosdep_status: BuildStatus = BuildStatus.NOT_EXECUTED
    colcon_status: BuildStatus = BuildStatus.NOT_EXECUTED
    exit_codes: Dict[str, int] = Field(default_factory=dict)
    stdout_summary: List[str] = Field(default_factory=list)
    stderr_summary: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    artifact_digest: Optional[str] = None


class NodeHealth(BaseModel):
    name: str
    namespace: str = "/"
    is_present: bool = True
    is_alive: bool = True
    pid: Optional[int] = None
    publisher_topics: List[str] = Field(default_factory=list)
    subscriber_topics: List[str] = Field(default_factory=list)
    services: List[str] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)


class QoSDiagnostic(BaseModel):
    topic: str
    publisher_node: str
    subscriber_node: str
    publisher_qos: Dict[str, str] = Field(default_factory=dict)
    subscriber_qos: Dict[str, str] = Field(default_factory=dict)
    compatibility: QoSPolicyCompatibility = QoSPolicyCompatibility.COMPATIBLE
    reason: Optional[str] = None


class ConnectionDiagnostic(BaseModel):
    topic: str
    topic_type: str = "unknown"
    status: str = "HEALTHY"  # HEALTHY, MISMATCH, ORPHANED, INCOMPATIBLE_QOS
    publishers: List[str] = Field(default_factory=list)
    subscribers: List[str] = Field(default_factory=list)
    rate_hz: Optional[float] = None
    qos_status: QoSPolicyCompatibility = QoSPolicyCompatibility.COMPATIBLE
    qos_reason: Optional[str] = None


class TFDiagnostic(BaseModel):
    frame_id: str
    parent_frame_id: str
    is_connected: bool = True
    is_stale: bool = False
    rate_hz: Optional[float] = None


class ConnectionInspectorReport(BaseModel):
    status: ConnectionInspectorStatus = ConnectionInspectorStatus.NOT_INSTALLED
    version: Optional[str] = None
    detected_prefix: Optional[str] = None
    executables: List[str] = Field(default_factory=list)
    licensing_notice: str = "GPL-3.0-only external third-party tool. OpenRobo provides an unbundled process integration interface."
    diagnostic_summary: Optional[Dict[str, Any]] = None


class RuntimeVerificationResult(BaseModel):
    stack_id: str
    runtime_id: str
    observed_at: str = Field(default_factory=utc_now_str)
    overall_status: OverallHealthStatus = OverallHealthStatus.UNKNOWN
    nodes: List[NodeHealth] = Field(default_factory=list)
    connections: List[ConnectionDiagnostic] = Field(default_factory=list)
    qos_findings: List[QoSDiagnostic] = Field(default_factory=list)
    tf_findings: List[TFDiagnostic] = Field(default_factory=list)
    missing_nodes: List[str] = Field(default_factory=list)
    unexpected_nodes: List[str] = Field(default_factory=list)
    connection_inspector: ConnectionInspectorReport = Field(default_factory=ConnectionInspectorReport)
    summary: str = ""


class RuntimeSession(BaseModel):
    id: str
    stack_id: str
    workspace_path: str
    provider: ExecutionProviderType = ExecutionProviderType.LOCAL_PROCESS
    ros_distro: str = "humble"
    domain_id: int = 0
    status: RuntimeSessionStatus = RuntimeSessionStatus.STARTING
    pids: List[int] = Field(default_factory=list)
    started_at: str = Field(default_factory=utc_now_str)
    stopped_at: Optional[str] = None
