"""Data models for OpenRobo Workspace and Deployment Generation (Milestone 5.1)."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GenerationEvidenceLevel(str, Enum):
    VERIFIED_ADAPTER = "VERIFIED_ADAPTER"
    METADATA_DRIVEN = "METADATA_DRIVEN"
    USER_CONFIGURED = "USER_CONFIGURED"
    GENERIC_SCAFFOLD = "GENERIC_SCAFFOLD"
    UNSUPPORTED = "UNSUPPORTED"


class WorkspaceReadinessState(str, Enum):
    STATICALLY_VALIDATED = "STATICALLY_VALIDATED"
    BUILD_REQUIRES_CONFIGURATION = "BUILD_REQUIRES_CONFIGURATION"
    BUILD_VERIFIED = "BUILD_VERIFIED"
    RUNTIME_VERIFIED = "RUNTIME_VERIFIED"


class ExecutionStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_EXECUTED = "NOT_EXECUTED"


class DockerDeploymentProfile(str, Enum):
    DEFAULT = "default"
    HARDWARE = "hardware"
    SIMULATION = "simulation"


class MaintainerInfo(BaseModel):
    name: str = "OpenRobo User"
    email: Optional[str] = None


class ComponentEvidence(BaseModel):
    level: GenerationEvidenceLevel = GenerationEvidenceLevel.GENERIC_SCAFFOLD
    source: str = "openrobo_generator"
    resource_id: str
    adapter_id: Optional[str] = None
    adapter_version: Optional[str] = None
    reason: str = ""
    required_manual_steps: List[str] = Field(default_factory=list)


class WorkspaceReadinessReport(BaseModel):
    overall_state: WorkspaceReadinessState = WorkspaceReadinessState.STATICALLY_VALIDATED
    static_validation: ExecutionStatus = ExecutionStatus.PASSED
    docker_build: ExecutionStatus = ExecutionStatus.NOT_EXECUTED
    colcon_build: ExecutionStatus = ExecutionStatus.NOT_EXECUTED
    runtime_validation: ExecutionStatus = ExecutionStatus.NOT_EXECUTED
    manual_steps_required: List[str] = Field(default_factory=list)
    evidence_summary: Dict[str, str] = Field(default_factory=dict)
    notes: List[str] = Field(default_factory=list)


class WorkspaceValidationResult(BaseModel):
    is_valid: bool = True
    status: ExecutionStatus = ExecutionStatus.PASSED
    checks_count: int = 0
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class SourceStrategy(str, Enum):
    APT_BINARY = "apt"
    ROSDEP = "rosdep"
    SOURCE_GIT = "git_source"
    PIP = "pip"
    LOCAL_EXTERNAL = "local"


class PackageBuildType(str, Enum):
    AMENT_CMAKE = "ament_cmake"
    AMENT_PYTHON = "ament_python"
    CMAKE = "cmake"


class ComponentGenerationPlan(BaseModel):
    resource_id: str
    name: str
    resolved_version: str = "1.0.0"
    source_strategy: SourceStrategy = SourceStrategy.ROSDEP
    build_type: PackageBuildType = PackageBuildType.AMENT_CMAKE
    repository_url: Optional[str] = None
    commit_or_tag: Optional[str] = None
    license: str = "Apache-2.0"
    has_adapter: bool = False
    adapter_name: Optional[str] = None
    has_parameters: bool = True
    ros_package_names: List[str] = Field(default_factory=list)
    evidence: Optional[ComponentEvidence] = None
    dependencies: List[str] = Field(default_factory=list)
    system_dependencies: List[str] = Field(default_factory=list)
    python_dependencies: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class WorkspaceGenerationPlan(BaseModel):
    stack_id: str = "openrobo_stack"
    stack_name: str = "openrobo_stack"
    workspace_name: str = "openrobo_ws"
    description: Optional[str] = None
    target_distro: str = "humble"
    target_os: str = "ubuntu-22.04"
    target_arch: str = "x86_64"
    compatibility_verdict: str = "COMPATIBLE"
    bringup_package_name: str = "openrobo_bringup"
    maintainer: MaintainerInfo = Field(default_factory=MaintainerInfo)
    components: List[ComponentGenerationPlan] = Field(default_factory=list)
    system_dependencies: List[str] = Field(default_factory=list)
    python_dependencies: List[str] = Field(default_factory=list)
    launch_components: List[str] = Field(default_factory=list)
    unsupported_components: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    evidence_records: List[ComponentEvidence] = Field(default_factory=list)
    readiness_report: WorkspaceReadinessReport = Field(default_factory=WorkspaceReadinessReport)
    enable_docker: bool = True
    enable_compose: bool = True
    enable_devcontainer: bool = True
    docker_profile: DockerDeploymentProfile = DockerDeploymentProfile.DEFAULT
    requested_devices: List[str] = Field(default_factory=list)
    user_configuration: Dict[str, Any] = Field(default_factory=dict)
    manifest_digest: str = ""
    planned_at: str = Field(default_factory=utc_now_str)


class GeneratedFile(BaseModel):
    path: str  # Relative POSIX path e.g. "src/openrobo_bringup/package.xml"
    content: str
    is_executable: bool = False
    description: Optional[str] = None


class WorkspacePreviewResponse(BaseModel):
    status: str = "success"
    stack_id: str
    stack_name: str
    workspace_name: str
    target_distro: str
    target_os: str
    target_arch: str
    compatibility_verdict: str
    file_count: int
    total_bytes: int
    file_tree: Dict[str, Any]
    files: Dict[str, str] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    unsupported_components: List[str] = Field(default_factory=list)
    selected_adapters: List[str] = Field(default_factory=list)
    generator_version: str = "0.5.1"
    readiness_report: Optional[WorkspaceReadinessReport] = None
    validation_result: Optional[WorkspaceValidationResult] = None
    generated_at: str = Field(default_factory=utc_now_str)


class WorkspaceResult(BaseModel):
    status: str = "success"
    stack_id: str
    workspace_name: str
    output_path: Optional[str] = None
    file_count: int
    total_bytes: int
    file_tree: Dict[str, Any]
    warnings: List[str] = Field(default_factory=list)
    unsupported_components: List[str] = Field(default_factory=list)
    generator_version: str = "0.5.1"
    readiness_report: Optional[WorkspaceReadinessReport] = None
    validation_result: Optional[WorkspaceValidationResult] = None
    archive_bytes: Optional[bytes] = None
    generated_at: str = Field(default_factory=utc_now_str)
