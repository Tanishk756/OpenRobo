"""OpenRobo Compatibility Intelligence Engine"""

from openrobo_compat.engine import CompatibilityEngine
from openrobo_compat.explainer import CompatibilityExplainer
from openrobo_compat.graph import GraphEdgeData, OpenRoboGraph
from openrobo_compat.models import (
    CompatibilityMatrixResponse,
    CompatibilityResult,
    CompatibilityStatus,
    ConflictDetail,
    EnvironmentTarget,
    EvaluationRequest,
    EvidenceLevel,
    MatrixRequest,
    ResourceCandidate,
    ResourceCompatibilityProfile,
    RuleEvaluation,
)
from openrobo_compat.rules import (
    BaseRule,
    CpuArchitectureRule,
    DependencyCycleRule,
    ExplicitConflictRule,
    ExplicitTestedWithRule,
    HardwareAndCapabilityRule,
    OperatingSystemRule,
    RosDistributionRule,
    SemVerConstraintRule,
)
from openrobo_compat.semver import matches_version_constraint, parse_semver_constraint

__all__ = [
    "CompatibilityEngine",
    "CompatibilityExplainer",
    "OpenRoboGraph",
    "GraphEdgeData",
    "CompatibilityStatus",
    "EvidenceLevel",
    "EnvironmentTarget",
    "ResourceCandidate",
    "RuleEvaluation",
    "ConflictDetail",
    "CompatibilityResult",
    "CompatibilityMatrixResponse",
    "EvaluationRequest",
    "MatrixRequest",
    "ResourceCompatibilityProfile",
    "BaseRule",
    "RosDistributionRule",
    "OperatingSystemRule",
    "CpuArchitectureRule",
    "SemVerConstraintRule",
    "ExplicitConflictRule",
    "DependencyCycleRule",
    "HardwareAndCapabilityRule",
    "ExplicitTestedWithRule",
    "matches_version_constraint",
    "parse_semver_constraint",
]
