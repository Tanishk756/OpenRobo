"""Data models for OpenRobo Runtime Verification, Introspection, and Simulation (Milestone 6.1)."""

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
    DETECTED_NOT_IMPLEMENTED = "DETECTED_NOT_IMPLEMENTED"


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


class ReadinessState(str, Enum):
    STATICALLY_VALIDATED = "STATICALLY_VALIDATED"
    BUILD_REQUIRES_CONFIGURATION = "BUILD_REQUIRES_CONFIGURATION"
    BUILD_NOT_EXECUTED = "BUILD_NOT_EXECUTED"
    BUILD_VERIFIED = "BUILD_VERIFIED"
    RUNTIME_NOT_EXECUTED = "RUNTIME_NOT_EXECUTED"
    RUNTIME_VERIFYING = "RUNTIME_VERIFYING"
    RUNTIME_VERIFIED = "RUNTIME_VERIFIED"
    RUNTIME_FAILED = "RUNTIME_FAILED"


class QoSPolicyCompatibility(str, Enum):
    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNKNOWN = "UNKNOWN"


class ConnectionInspectorStatus(str, Enum):
    INSTALLED = "INSTALLED"
    NOT_INSTALLED = "NOT_INSTALLED"
    UNSUPPORTED_DISTRO = "UNSUPPORTED_DISTRO"
    ERROR = "ERROR"


class DistroReleaseSupport(str, Enum):
    VERIFIED_RELEASE = "VERIFIED_RELEASE"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"


class RosEnvironmentStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    MISCONFIGURED = "MISCONFIGURED"


class RosEnvironmentInfo(BaseModel):
    status: RosEnvironmentStatus = RosEnvironmentStatus.UNAVAILABLE
    distro: Optional[str] = None
    ros_version: Optional[str] = None
    rmw_implementation: Optional[str] = None
    domain_id: Optional[int] = None
    rclpy_available: bool = False
    ros2_cli_available: bool = False
    installation_prefix: Optional[str] = None
    details: Optional[str] = None


class ProviderInfo(BaseModel):
    provider_type: ExecutionProviderType
    status: ProviderStatus
    version: Optional[str] = None
    details: Optional[str] = None
    supports_build_verification: bool = True


class BuildVerificationResult(BaseModel):
    status: BuildStatus = BuildStatus.NOT_EXECUTED
    provider: ExecutionProviderType = ExecutionProviderType.LOCAL_PROCESS
    started_at: str = Field(default_factory=utc_now_str)
    duration_ms: int = 0
    workspace_digest: str = ""
    docker_build_status: BuildStatus = BuildStatus.NOT_EXECUTED
    rosdep_status: BuildStatus = BuildStatus.NOT_EXECUTED
    colcon_status: BuildStatus = BuildStatus.NOT_EXECUTED
    verified_via: Optional[str] = None  # e.g. "docker_build_stage", "host_colcon"
    exit_codes: Dict[str, int] = Field(default_factory=dict)
    stdout_summary: List[str] = Field(default_factory=list)
    stderr_summary: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    artifact_digest: Optional[str] = None


class ExpectedTopicContract(BaseModel):
    name: str
    msg_type: str
    direction: str = "pubsub"  # "publisher", "subscriber", "pubsub"
    required: bool = True


class ExpectedTransformContract(BaseModel):
    parent: str
    child: str
    required: bool = True


class RuntimeContract(BaseModel):
    expected_nodes: List[str] = Field(default_factory=list)
    expected_topics: List[ExpectedTopicContract] = Field(default_factory=list)
    expected_transforms: List[ExpectedTransformContract] = Field(default_factory=list)
    expected_services: List[str] = Field(default_factory=list)


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
    status: str = "HEALTHY"  # HEALTHY, TYPE_MISMATCH, ORPHANED_PUBLISHER, ORPHANED_SUBSCRIBER, INCOMPATIBLE_QOS
    publishers: List[str] = Field(default_factory=list)
    subscribers: List[str] = Field(default_factory=list)
    rate_hz: Optional[float] = None
    qos_status: QoSPolicyCompatibility = QoSPolicyCompatibility.COMPATIBLE
    qos_reason: Optional[str] = None
    type_mismatch_detail: Optional[str] = None


class TopicRateMetrics(BaseModel):
    topic: str
    rate_hz: Optional[float] = None
    message_count: int = 0
    sampling_duration_sec: float = 0.0
    last_message_age_sec: Optional[float] = None
    status: str = "AVAILABLE"  # "AVAILABLE", "RATE_UNAVAILABLE", "TIMEOUT"


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
    distro_support: DistroReleaseSupport = DistroReleaseSupport.UNKNOWN
    licensing_notice: str = (
        "GPL-3.0-only external tool: OpenRobo communicates with Connection Inspector "
        "via safe external process execution and does not vendor or link GPL code."
    )
    diagnostic_summary: Optional[Dict[str, Any]] = None


class VerificationType(str, Enum):
    STATIC = "STATIC"
    BUILD = "BUILD"
    RUNTIME = "RUNTIME"


class VerificationEvidence(BaseModel):
    id: str
    stack_id: str
    workspace_digest: str
    runtime_id: Optional[str] = None
    verification_type: VerificationType
    status: str
    timestamp: str = Field(default_factory=utc_now_str)
    environment: Dict[str, Any] = Field(default_factory=dict)
    tool_versions: Dict[str, Optional[str]] = Field(default_factory=dict)
    duration_ms: int = 0
    summary: str = ""
    artifact_digest: Optional[str] = None


class RuntimeVerificationResult(BaseModel):
    stack_id: str
    runtime_id: str
    observed_at: str = Field(default_factory=utc_now_str)
    overall_status: OverallHealthStatus = OverallHealthStatus.UNKNOWN
    readiness_state: ReadinessState = ReadinessState.RUNTIME_NOT_EXECUTED
    nodes: List[NodeHealth] = Field(default_factory=list)
    connections: List[ConnectionDiagnostic] = Field(default_factory=list)
    qos_findings: List[QoSDiagnostic] = Field(default_factory=list)
    tf_findings: List[TFDiagnostic] = Field(default_factory=list)
    missing_nodes: List[str] = Field(default_factory=list)
    unexpected_nodes: List[str] = Field(default_factory=list)
    contract_evaluated: bool = False
    connection_inspector: ConnectionInspectorReport = Field(default_factory=ConnectionInspectorReport)
    summary: str = ""


class RuntimeSession(BaseModel):
    id: str
    stack_id: str
    workspace_path: str
    workspace_digest: str = ""
    provider: ExecutionProviderType = ExecutionProviderType.LOCAL_PROCESS
    ros_distro: str = "humble"
    domain_id: int = 0
    status: RuntimeSessionStatus = RuntimeSessionStatus.STARTING
    pids: List[int] = Field(default_factory=list)
    started_at: str = Field(default_factory=utc_now_str)
    stopped_at: Optional[str] = None
    build_verification_id: Optional[str] = None
    evidence: Optional[VerificationEvidence] = None
