"""OpenRobo Workspace & Deployment Generator.

Milestone 5 package for synthesizing deterministic, reproducible colcon workspaces,
Dockerfiles, Dev Containers, and deployment archives from validated Stack Manifests.
"""

from openrobo_workspace.archive import build_workspace_zip
from openrobo_workspace.filesystem import build_file_tree, sanitize_relative_path, write_workspace_to_disk
from openrobo_workspace.generator import GENERATOR_VERSION, WorkspaceGenerator
from openrobo_workspace.models import (
    ComponentGenerationPlan,
    GeneratedFile,
    PackageBuildType,
    SourceStrategy,
    WorkspaceGenerationPlan,
    WorkspacePreviewResponse,
    WorkspaceResult,
)
from openrobo_workspace.planner import WorkspacePlanner

__version__ = GENERATOR_VERSION

__all__ = [
    "GENERATOR_VERSION",
    "ComponentGenerationPlan",
    "GeneratedFile",
    "PackageBuildType",
    "SourceStrategy",
    "WorkspaceGenerationPlan",
    "WorkspaceGenerator",
    "WorkspacePlanner",
    "WorkspacePreviewResponse",
    "WorkspaceResult",
    "build_file_tree",
    "build_workspace_zip",
    "sanitize_relative_path",
    "write_workspace_to_disk",
]
