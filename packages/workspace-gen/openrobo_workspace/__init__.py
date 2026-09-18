"""OpenRobo Workspace & Deployment Generator.

Milestone 5.1 Hardened package for synthesizing deterministic, reproducible colcon workspaces,
Dockerfiles, Dev Containers, and deployment archives from validated Stack Manifests.
"""

from openrobo_workspace.archive import build_workspace_zip
from openrobo_workspace.filesystem import build_file_tree, sanitize_relative_path, write_workspace_to_disk
from openrobo_workspace.generator import GENERATOR_VERSION, WorkspaceGenerator
from openrobo_workspace.models import (
    ComponentEvidence,
    ComponentGenerationPlan,
    DockerDeploymentProfile,
    ExecutionStatus,
    GeneratedFile,
    GenerationEvidenceLevel,
    MaintainerInfo,
    PackageBuildType,
    SourceStrategy,
    WorkspaceGenerationPlan,
    WorkspacePreviewResponse,
    WorkspaceReadinessReport,
    WorkspaceReadinessState,
    WorkspaceResult,
    WorkspaceValidationResult,
)
from openrobo_workspace.planner import WorkspacePlanner
from openrobo_workspace.validator import WorkspaceValidator

__version__ = GENERATOR_VERSION

__all__ = [
    "GENERATOR_VERSION",
    "ComponentEvidence",
    "ComponentGenerationPlan",
    "DockerDeploymentProfile",
    "ExecutionStatus",
    "GeneratedFile",
    "GenerationEvidenceLevel",
    "MaintainerInfo",
    "PackageBuildType",
    "SourceStrategy",
    "WorkspaceGenerationPlan",
    "WorkspaceGenerator",
    "WorkspacePlanner",
    "WorkspacePreviewResponse",
    "WorkspaceReadinessReport",
    "WorkspaceReadinessState",
    "WorkspaceResult",
    "WorkspaceValidationResult",
    "WorkspaceValidator",
    "build_file_tree",
    "build_workspace_zip",
    "sanitize_relative_path",
    "write_workspace_to_disk",
]
