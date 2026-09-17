from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class CompatibilityStatus(str, Enum):
    COMPATIBLE = "compatible"
    CONDITIONAL = "conditional"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


class EvidenceLevel(str, Enum):
    CI_VERIFIED = "ci_verified"
    VENDOR_TESTED = "vendor_tested"
    COMMUNITY_REPORTED = "community_reported"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class EnvironmentTarget(BaseModel):
    ros_version: Optional[str] = Field(None, description="Target ROS distribution (e.g. 'Jazzy', 'Humble', 'Iron')")
    os: Optional[str] = Field(None, description="Target Operating System (e.g. 'Ubuntu', 'Windows', 'macOS')")
    os_version: Optional[str] = Field(None, description="Target OS version (e.g. '24.04', '22.04', '11')")
    cpu_architecture: Optional[str] = Field(None, description="Target CPU architecture (e.g. 'x86_64', 'aarch64', 'armv7l')")
    capabilities: List[str] = Field(default_factory=list, description="Available platform or hardware capabilities")
    hardware: List[str] = Field(default_factory=list, description="Available hardware devices/sensors/actuators")


class ResourceCandidate(BaseModel):
    id: str
    name: str
    version: Optional[str] = None
    type: str = "ros_package"
    robotics_domains: List[str] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    platforms: Optional[Dict[str, List[str]]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    evidence_level: Optional[str] = "inferred"


class RuleEvaluation(BaseModel):
    rule_name: str
    status: CompatibilityStatus
    message: str
    evidence_level: EvidenceLevel = EvidenceLevel.INFERRED
    remediation: Optional[str] = None


class ConflictDetail(BaseModel):
    source_id: str
    target_id: Optional[str] = None
    conflict_type: str
    message: str
    dependency_path: List[str] = Field(default_factory=list)
    remediation: Optional[str] = None


class CompatibilityResult(BaseModel):
    status: CompatibilityStatus
    resource_ids: List[str]
    environment: Optional[EnvironmentTarget] = None
    rule_evaluations: List[RuleEvaluation] = Field(default_factory=list)
    conflicts: List[ConflictDetail] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    missing_requirements: List[str] = Field(default_factory=list)
    dependency_paths: List[List[str]] = Field(default_factory=list)
    evidence_level: EvidenceLevel = EvidenceLevel.UNKNOWN
    remediation: Optional[str] = None
    evaluated_at: str = Field(default_factory=utc_now_str)


class CompatibilityMatrixResponse(BaseModel):
    candidate_ids: List[str]
    matrix: Dict[str, Dict[str, CompatibilityResult]]
    summary: Dict[str, int] = Field(default_factory=dict)
    evaluated_at: str = Field(default_factory=utc_now_str)


class EvaluationRequest(BaseModel):
    resource_ids: List[str] = Field(..., min_length=1, description="List of candidate resource IDs to evaluate")
    environment: Optional[EnvironmentTarget] = Field(None, description="Optional target environment constraints")


class MatrixRequest(BaseModel):
    resource_ids: List[str] = Field(..., min_length=2, description="Candidate resource IDs to compute pairwise matrix")
    environment: Optional[EnvironmentTarget] = Field(None, description="Optional target environment constraints")


class ResourceCompatibilityProfile(BaseModel):
    resource_id: str
    name: str
    version: Optional[str] = None
    type: str
    evidence_level: str = "inferred"
    direct_dependencies: List[str] = Field(default_factory=list)
    provides: List[str] = Field(default_factory=list)
    requires: List[str] = Field(default_factory=list)
    tested_with: List[str] = Field(default_factory=list)
    compatible_with: List[str] = Field(default_factory=list)
    conflicts_with: List[str] = Field(default_factory=list)
    platform_matrix: Dict[str, List[str]] = Field(default_factory=dict)
