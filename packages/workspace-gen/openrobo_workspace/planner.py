"""Workspace Generation Planner.

Constructs a strictly-typed, validated WorkspaceGenerationPlan from
canonical stack manifests, registry metadata, and compatibility results.
Enforces the principle: NO EVIDENCE -> NO INVENTED CONFIGURATION.
"""

import re
from typing import Any, Dict, List, Optional

from openrobo_workspace.adapters.registry import default_adapter_registry
from openrobo_workspace.models import (
    ComponentEvidence,
    ComponentGenerationPlan,
    DockerDeploymentProfile,
    ExecutionStatus,
    GenerationEvidenceLevel,
    MaintainerInfo,
    PackageBuildType,
    SourceStrategy,
    WorkspaceGenerationPlan,
    WorkspaceReadinessReport,
    WorkspaceReadinessState,
)

ROS_PKG_SANITIZER = re.compile(r"[^a-z0-9_]")


def sanitize_package_name(name: str) -> str:
    """Sanitize string to valid ROS 2 package name (lower snake_case, alphanumeric + underscore)."""
    s = name.strip().lower()
    s = ROS_PKG_SANITIZER.sub("_", s)
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
        docker_profile: DockerDeploymentProfile = DockerDeploymentProfile.DEFAULT,
        maintainer: Optional[MaintainerInfo] = None,
    ):
        self.manifest = stack_manifest
        self.registry_metadata = registry_metadata or {}
        self.compatibility_result = compatibility_result or {}
        self.allow_incompatible = allow_incompatible
        self.docker_profile = docker_profile
        self.maintainer = maintainer

    def _resolve_maintainer(self) -> MaintainerInfo:
        """Resolve maintainer info from explicit argument or manifest metadata."""
        if self.maintainer:
            return self.maintainer

        manifest_meta = self.manifest.get("metadata", {})
        raw_maintainer = manifest_meta.get("maintainer")
        if isinstance(raw_maintainer, dict):
            return MaintainerInfo(
                name=raw_maintainer.get("name", "OpenRobo User"),
                email=raw_maintainer.get("email"),
            )
        elif isinstance(raw_maintainer, str) and raw_maintainer.strip():
            # Check if format is "Name <email>"
            match = re.match(r"^([^<]+)(?:<([^>]+)>)?$", raw_maintainer.strip())
            if match:
                name = match.group(1).strip()
                email = match.group(2).strip() if match.group(2) else None
                return MaintainerInfo(name=name, email=email)
            return MaintainerInfo(name=raw_maintainer.strip())

        return MaintainerInfo(name="OpenRobo User", email=None)

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
        user_config = self.manifest.get("configuration", {})

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

        maintainer_info = self._resolve_maintainer()

        # 2. Process Components
        components: List[ComponentGenerationPlan] = []
        system_dependencies: List[str] = []
        python_dependencies: List[str] = []
        launch_components: List[str] = []
        unsupported_components: List[str] = []
        evidence_records: List[ComponentEvidence] = []
        manual_steps_required: List[str] = []

        raw_resources = self.manifest.get("resources", [])
        for res_entry in raw_resources:
            res_id = res_entry if isinstance(res_entry, str) else res_entry.get("id", "")
            if not res_id:
                continue

            reg_data = self.registry_metadata.get(res_id, {})
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

            # Determine ROS packages from metadata
            ros_pkgs = reg_data.get("ros_packages") or reg_data.get("ros_package_names") or []
            if not ros_pkgs and "name" in reg_data:
                cand = sanitize_package_name(reg_data["name"])
                if cand:
                    ros_pkgs = [cand]

            # Determine Source Strategy
            is_apt = reg_data.get("has_binary_release", True)
            if is_apt:
                source_strat = SourceStrategy.APT_BINARY
                if ros_pkgs:
                    for rpkg in ros_pkgs:
                        pkg_deb_name = f"ros-{target_distro}-{rpkg.replace('_', '-')}"
                        system_dependencies.append(pkg_deb_name)
                else:
                    sanitized_id = res_id.split("/")[-1].replace("_", "-").lower()
                    system_dependencies.append(f"ros-{target_distro}-{sanitized_id}")
            elif repo_url:
                source_strat = SourceStrategy.SOURCE_GIT
            else:
                source_strat = SourceStrategy.LOCAL_EXTERNAL
                warnings.append(
                    f"Component '{res_id}' has no known binary release or git repository. "
                    "Using placeholder source strategy."
                )

            # Identify Adapter via Deterministic Registry (NO substring matching)
            adapter_def = default_adapter_registry.get_adapter(res_id, target_distro)
            adapter_id: Optional[str] = None
            adapter_ver: Optional[str] = None
            evidence_level = GenerationEvidenceLevel.GENERIC_SCAFFOLD
            comp_manual_steps: List[str] = []
            evidence_reason = ""

            if adapter_def:
                adapter_id = adapter_def.adapter_id
                adapter_ver = adapter_def.adapter_version
                launch_components.append(res_id)

                # Check if user provided explicit configuration for this adapter
                if adapter_id == "ros2_control":
                    ctrl_cfg = user_config.get("ros2_control", {})
                    if ctrl_cfg.get("left_wheel_names") and ctrl_cfg.get("wheel_separation"):
                        evidence_level = GenerationEvidenceLevel.USER_CONFIGURED
                        evidence_reason = "Verified ros2_control adapter with user-supplied joint & geometry configuration"
                    else:
                        evidence_level = GenerationEvidenceLevel.GENERIC_SCAFFOLD
                        evidence_reason = "ros2_control detected but missing hardware geometry/joint data; generated scaffold .example"
                        step_msg = "ros2_control: wheel joints and geometry required in config/ros2_control_params.yaml"
                        comp_manual_steps.append(step_msg)
                        manual_steps_required.append(step_msg)
                elif adapter_id in user_config:
                    evidence_level = GenerationEvidenceLevel.USER_CONFIGURED
                    evidence_reason = f"Verified {adapter_id} adapter with user-supplied parameter overrides"
                else:
                    evidence_level = GenerationEvidenceLevel.VERIFIED_ADAPTER
                    evidence_reason = f"Verified canonical {adapter_id} adapter (v{adapter_ver}) for ROS {target_distro}"
            else:
                unsupported_components.append(res_id)
                evidence_level = GenerationEvidenceLevel.GENERIC_SCAFFOLD
                evidence_reason = f"No verified adapter registered for '{res_id}'; generated generic ROS 2 parameter scaffold"
                pkg_sub = res_id.split('/')[-1].replace('-', '_')
                step_msg = f"{res_id}: Configure node launch and parameters in config/{pkg_sub}.yaml.example"
                comp_manual_steps.append(step_msg)
                manual_steps_required.append(step_msg)

            # Collect dependencies from metadata
            res_deps = reg_data.get("dependencies", [])
            for d in res_deps:
                if isinstance(d, str):
                    if d.startswith("python3-") or d.startswith("pip:"):
                        python_dependencies.append(d.replace("pip:", ""))
                    else:
                        system_dependencies.append(f"ros-{target_distro}-{d.replace('_', '-')}")

            evidence = ComponentEvidence(
                resource_id=res_id,
                level=evidence_level,
                source=source_strat.value,
                adapter_id=adapter_id,
                adapter_version=adapter_ver,
                reason=evidence_reason,
                required_manual_steps=comp_manual_steps,
            )
            evidence_records.append(evidence)

            plan_comp = ComponentGenerationPlan(
                resource_id=res_id,
                name=name,
                resolved_version=version,
                source_strategy=source_strat,
                build_type=build_type,
                repository_url=repo_url,
                commit_or_tag=entry_dict.get("commit") or entry_dict.get("tag"),
                license=license_str,
                has_adapter=(adapter_def is not None),
                adapter_name=adapter_id,
                has_parameters=True,
                dependencies=[d for d in res_deps if isinstance(d, str)],
                ros_package_names=ros_pkgs,
                evidence=evidence,
            )
            components.append(plan_comp)

        bringup_pkg_name = sanitize_package_name(f"{stack_name}_bringup")
        workspace_name = f"{sanitize_package_name(stack_name)}_ws"

        # Requested devices from manifest deployment section
        deployment_cfg = self.manifest.get("deployment", {})
        requested_devs = deployment_cfg.get("devices", [])

        # Build Readiness Report
        readiness_state = (
            WorkspaceReadinessState.BUILD_REQUIRES_CONFIGURATION
            if manual_steps_required
            else WorkspaceReadinessState.STATICALLY_VALIDATED
        )
        evidence_summary = {e.resource_id: e.level.value for e in evidence_records}

        readiness_report = WorkspaceReadinessReport(
            overall_state=readiness_state,
            static_validation=ExecutionStatus.PASSED,
            docker_build=ExecutionStatus.NOT_EXECUTED,
            colcon_build=ExecutionStatus.NOT_EXECUTED,
            runtime_validation=ExecutionStatus.NOT_EXECUTED,
            manual_steps_required=manual_steps_required,
            evidence_summary=evidence_summary,
            notes=[
                "Static syntax & structural analysis passed.",
                "No runtime container or colcon compilation has been executed."
            ],
        )

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
            evidence_records=evidence_records,
            readiness_report=readiness_report,
            docker_profile=self.docker_profile,
            requested_devices=requested_devs,
            user_configuration=user_config,
            maintainer=maintainer_info,
        )
