"""Workspace Generation Planner.

Transforms a validated Stack Manifest, Registry Metadata, and Compatibility Result
into a structured, deterministic WorkspaceGenerationPlan.
"""

import re
from typing import Any, Dict, List, Optional

from openrobo_workspace.adapters.gazebo import has_gazebo_adapter
from openrobo_workspace.adapters.nav2 import has_nav2_adapter
from openrobo_workspace.adapters.ros2_control import has_ros2_control_adapter
from openrobo_workspace.adapters.slam_toolbox import has_slam_toolbox_adapter
from openrobo_workspace.models import (
    ComponentGenerationPlan,
    PackageBuildType,
    SourceStrategy,
    WorkspaceGenerationPlan,
)

ADAPTER_CHECKERS = {
    "nav2": has_nav2_adapter,
    "slam_toolbox": has_slam_toolbox_adapter,
    "ros2_control": has_ros2_control_adapter,
    "gazebo": has_gazebo_adapter,
}


def sanitize_package_name(name: str) -> str:
    """Sanitize string to valid ROS 2 package name (lower snake_case, alphanumeric + underscore)."""
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s or not s[0].isalpha():
        s = "openrobo_" + s
    return s


class WorkspacePlanner:
    """Constructs a WorkspaceGenerationPlan from validated stack inputs."""

    def __init__(
        self,
        stack_manifest: Dict[str, Any],
        registry_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
        compatibility_result: Optional[Dict[str, Any]] = None,
        allow_incompatible: bool = False,
    ):
        self.manifest = stack_manifest
        self.registry_metadata = registry_metadata or {}
        self.compatibility_result = compatibility_result or {}
        self.allow_incompatible = allow_incompatible

    def plan(self) -> WorkspaceGenerationPlan:
        # 1. Check Preconditions
        compat_verdict = self.compatibility_result.get("verdict", "COMPATIBLE")
        if compat_verdict == "INCOMPATIBLE" and not self.allow_incompatible:
            errors = self.compatibility_result.get("errors", [])
            error_msg = "; ".join(errors) if errors else "Stack manifest is marked INCOMPATIBLE"
            raise ValueError(f"Cannot generate workspace for INCOMPATIBLE stack: {error_msg}")

        stack_id = self.manifest.get("id", "openrobo_stack")
        stack_name = self.manifest.get("name", "openrobo_stack")
        description = self.manifest.get("description", "")

        target = self.manifest.get("target", {})
        metadata = self.manifest.get("metadata", {})
        target_distro = (
            target.get("ros_distro")
            or metadata.get("target_distro")
            or metadata.get("ros_distro")
            or "humble"
        )
        target_os = (
            target.get("os")
            or metadata.get("target_os")
            or "ubuntu-22.04"
        )
        target_arch = (
            target.get("architecture")
            or metadata.get("target_arch")
            or "x86_64"
        )

        warnings: List[str] = []
        if compat_verdict == "CONDITIONAL":
            warnings.append("Stack has CONDITIONAL compatibility. Some components may require manual configuration.")
        for warn in self.compatibility_result.get("warnings", []):
            warnings.append(warn)

        # 2. Process Components
        components: List[ComponentGenerationPlan] = []
        system_dependencies: List[str] = []
        python_dependencies: List[str] = []
        launch_components: List[str] = []
        unsupported_components: List[str] = []

        raw_resources = self.manifest.get("resources", [])
        for res_entry in raw_resources:
            res_id = res_entry if isinstance(res_entry, str) else res_entry.get("id", "")
            if not res_id:
                continue

            reg_data = self.registry_metadata.get(res_id, {})
            # Merge entry data with registry data
            entry_dict = res_entry if isinstance(res_entry, dict) else {}
            name = entry_dict.get("name") or reg_data.get("name") or res_id
            version = entry_dict.get("version") or reg_data.get("version") or "main"
            license_str = entry_dict.get("license") or reg_data.get("license") or "Apache-2.0"
            repo_url = (
                entry_dict.get("repository_url")
                or reg_data.get("repository_url")
                or (reg_data.get("repository") if isinstance(reg_data.get("repository"), str) else None)
            )

            # Determine Build Type
            raw_build_type = (
                entry_dict.get("build_type")
                or reg_data.get("build_type")
                or "ament_cmake"
            )
            try:
                build_type = PackageBuildType(raw_build_type.lower())
            except ValueError:
                build_type = PackageBuildType.AMENT_CMAKE

            # Determine Source Strategy
            # If known official binary exists for distro, prefer APT_BINARY
            is_apt = reg_data.get("has_binary_release", True)  # default to apt for official ROS packages
            if is_apt:
                source_strat = SourceStrategy.APT_BINARY
                # Normalize apt package name: ros-<distro>-<pkg-name-with-dashes>
                pkg_deb_name = f"ros-{target_distro}-{res_id.replace('_', '-')}"
                system_dependencies.append(pkg_deb_name)
            elif repo_url:
                source_strat = SourceStrategy.SOURCE_GIT
            else:
                source_strat = SourceStrategy.LOCAL_EXTERNAL
                warnings.append(f"Component '{res_id}' has no known binary release or git repository. Using placeholder source strategy.")

            # Identify Adapter
            has_adapter = False
            for adapter_key, checker in ADAPTER_CHECKERS.items():
                if checker(res_id):
                    has_adapter = True
                    break

            if has_adapter:
                launch_components.append(res_id)
            else:
                unsupported_components.append(res_id)

            # Collect dependencies from metadata
            res_deps = reg_data.get("dependencies", [])
            for d in res_deps:
                if isinstance(d, str):
                    if d.startswith("python3-") or d.startswith("pip:"):
                        python_dependencies.append(d.replace("pip:", ""))
                    else:
                        system_dependencies.append(f"ros-{target_distro}-{d.replace('_', '-')}")

            plan_comp = ComponentGenerationPlan(
                resource_id=res_id,
                name=name,
                resolved_version=version,
                source_strategy=source_strat,
                build_type=build_type,
                repository_url=repo_url,
                commit_or_tag=entry_dict.get("commit") or entry_dict.get("tag"),
                license=license_str,
                has_adapter=has_adapter,
                has_parameters=True,
                dependencies=[d for d in res_deps if isinstance(d, str)],
            )
            components.append(plan_comp)

        bringup_pkg_name = sanitize_package_name(f"{stack_name}_bringup")
        workspace_name = f"{sanitize_package_name(stack_name)}_ws"

        return WorkspaceGenerationPlan(
            stack_id=stack_id,
            stack_name=stack_name,
            workspace_name=workspace_name,
            description=description,
            target_distro=target_distro,
            target_os=target_os,
            target_arch=target_arch,
            compatibility_verdict=compat_verdict,
            bringup_package_name=bringup_pkg_name,
            components=components,
            system_dependencies=sorted(list(set(system_dependencies))),
            python_dependencies=sorted(list(set(python_dependencies))),
            launch_components=sorted(list(set(launch_components))),
            unsupported_components=sorted(list(set(unsupported_components))),
            warnings=warnings,
            enable_docker=True,
            enable_compose=True,
            enable_devcontainer=True,
        )
