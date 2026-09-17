"""Workspace Generator Core.

Orchestrates planning, artifact synthesis, validation, filesystem output,
and reproducible archive packaging.
"""

import json
import os
from typing import Any, Dict, List, Optional

from openrobo_workspace.archive import build_workspace_zip
from openrobo_workspace.filesystem import build_file_tree, write_workspace_to_disk
from openrobo_workspace.generators.cmake import generate_cmake
from openrobo_workspace.generators.compose import generate_docker_compose
from openrobo_workspace.generators.devcontainer import generate_devcontainer_json
from openrobo_workspace.generators.docker import generate_dockerfile
from openrobo_workspace.generators.launch import generate_bringup_launch
from openrobo_workspace.generators.package_xml import generate_package_xml
from openrobo_workspace.generators.parameters import generate_parameter_files
from openrobo_workspace.generators.readme import generate_workspace_readme
from openrobo_workspace.generators.rosdep import (
    generate_install_dependencies_ps1,
    generate_install_dependencies_sh,
    generate_rosdep_install_sh,
)
from openrobo_workspace.lockfile import generate_lockfile
from openrobo_workspace.models import (
    DockerDeploymentProfile,
    GeneratedFile,
    MaintainerInfo,
    WorkspaceGenerationPlan,
    WorkspacePreviewResponse,
    WorkspaceResult,
    WorkspaceValidationResult,
)
from openrobo_workspace.planner import WorkspacePlanner
from openrobo_workspace.validator import WorkspaceValidator

GENERATOR_VERSION = "0.5.1"


class WorkspaceGenerator:
    """End-to-end deterministic workspace generator for OpenRobo stacks."""

    def __init__(
        self,
        stack_manifest: Dict[str, Any],
        registry_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
        compatibility_result: Optional[Dict[str, Any]] = None,
        allow_incompatible: bool = False,
        docker_profile: DockerDeploymentProfile = DockerDeploymentProfile.DEFAULT,
        maintainer: Optional[MaintainerInfo] = None,
    ):
        self.raw_manifest = stack_manifest
        self.planner = WorkspacePlanner(
            stack_manifest=stack_manifest,
            registry_metadata=registry_metadata,
            compatibility_result=compatibility_result,
            allow_incompatible=allow_incompatible,
            docker_profile=docker_profile,
            maintainer=maintainer,
        )

    def generate_files(self) -> tuple[WorkspaceGenerationPlan, List[GeneratedFile]]:
        """Synthesize all workspace files in memory."""
        plan = self.planner.plan()
        files: List[GeneratedFile] = []

        # 1. Canonical Manifest
        manifest_json_str = json.dumps(self.raw_manifest, indent=2, sort_keys=True) + "\n"
        files.append(GeneratedFile(path="openrobo.manifest.json", content=manifest_json_str))

        # 2. Lockfile
        lockfile_str = generate_lockfile(plan, manifest_json_str, GENERATOR_VERSION)
        files.append(GeneratedFile(path="openrobo.lock.json", content=lockfile_str))

        # 3. Workspace README
        files.append(generate_workspace_readme(plan))

        # 4. Dependency Setup Scripts
        files.append(generate_install_dependencies_sh(plan))
        files.append(generate_install_dependencies_ps1(plan))
        files.append(generate_rosdep_install_sh(plan))

        # 5. Bringup Meta-Package (REP-149)
        files.append(generate_package_xml(plan))
        files.append(generate_cmake(plan))
        files.append(generate_bringup_launch(plan))
        files.extend(generate_parameter_files(plan))

        # 6. Container & Dev Environment
        if plan.enable_docker:
            files.append(generate_dockerfile(plan))
        if plan.enable_compose:
            files.append(generate_docker_compose(plan))
        if plan.enable_devcontainer:
            files.append(generate_devcontainer_json(plan))

        # Sort files by path for strict determinism
        files = sorted(files, key=lambda f: f.path)

        # 7. Run Static Analysis Validation
        validation = WorkspaceValidator.validate_files(files, plan)
        if plan.readiness_report:
            plan.readiness_report.static_validation = validation.status

        return plan, files

    def validate(self) -> WorkspaceValidationResult:
        """Run static validation against synthesized workspace files."""
        plan, files = self.generate_files()
        return WorkspaceValidator.validate_files(files, plan)

    def preview(self) -> WorkspacePreviewResponse:
        """Produce an in-memory preview of the workspace files and file tree."""
        plan, files = self.generate_files()
        validation = WorkspaceValidator.validate_files(files, plan)
        file_tree = build_file_tree(files)
        total_bytes = sum(len(f.content.encode("utf-8")) for f in files)

        files_content_map = {f.path: f.content for f in files}

        return WorkspacePreviewResponse(
            status="success",
            stack_id=plan.stack_id,
            stack_name=plan.stack_name,
            workspace_name=plan.workspace_name,
            target_distro=plan.target_distro,
            target_os=plan.target_os,
            target_arch=plan.target_arch,
            compatibility_verdict=plan.compatibility_verdict,
            file_count=len(files),
            total_bytes=total_bytes,
            file_tree=file_tree,
            files=files_content_map,
            warnings=plan.warnings + validation.warnings,
            unsupported_components=plan.unsupported_components,
            selected_adapters=plan.launch_components,
            generator_version=GENERATOR_VERSION,
            readiness_report=plan.readiness_report,
            validation_result=validation,
        )

    def export_directory(self, target_dir: str) -> WorkspaceResult:
        """Write all generated files to disk safely."""
        plan, files = self.generate_files()
        validation = WorkspaceValidator.validate_files(files, plan)
        written_paths = write_workspace_to_disk(target_dir, files)
        file_tree = build_file_tree(files)
        total_bytes = sum(len(f.content.encode("utf-8")) for f in files)

        return WorkspaceResult(
            status="success",
            stack_id=plan.stack_id,
            workspace_name=plan.workspace_name,
            output_path=os.path.abspath(target_dir),
            file_count=len(written_paths),
            total_bytes=total_bytes,
            file_tree=file_tree,
            warnings=plan.warnings + validation.warnings,
            unsupported_components=plan.unsupported_components,
            generator_version=GENERATOR_VERSION,
            readiness_report=plan.readiness_report,
            validation_result=validation,
        )

    def export_archive(self) -> bytes:
        """Generate deterministic, reproducible in-memory ZIP archive bytes."""
        plan, files = self.generate_files()
        return build_workspace_zip(files, root_dir_name=plan.workspace_name)
