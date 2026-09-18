"""Lockfile generator for OpenRobo workspaces.

Emits structured, cryptographic provenance and evidence metadata for all components.
Avoids ambiguous magic strings (e.g. "UNKNOWN") in favor of structured nulls and statuses.
"""

import hashlib
import json

from openrobo_workspace.models import WorkspaceGenerationPlan


def compute_manifest_digest(manifest_str: str) -> str:
    return hashlib.sha256(manifest_str.encode("utf-8")).hexdigest()


def generate_lockfile(plan: WorkspaceGenerationPlan, manifest_str: str, generator_version: str = "0.5.1") -> str:
    components_lock = []
    for c in sorted(plan.components, key=lambda x: x.resource_id):
        evidence_dict = None
        if c.evidence:
            evidence_dict = {
                "level": c.evidence.level.value,
                "source": c.evidence.source,
                "adapter_id": c.evidence.adapter_id,
                "adapter_version": c.evidence.adapter_version,
                "reason": c.evidence.reason,
                "required_manual_steps": c.evidence.required_manual_steps,
            }

        resolution_status = "resolved" if c.commit_or_tag else "unresolved"
        components_lock.append(
            {
                "resource_id": c.resource_id,
                "original_name": c.name,
                "ros_package_names": c.ros_package_names,
                "version": c.resolved_version,
                "source_strategy": c.source_strategy.value,
                "build_type": c.build_type.value,
                "repository_url": c.repository_url,
                "requested_revision": c.commit_or_tag,
                "resolved_revision": c.commit_or_tag,
                "resolution_status": resolution_status,
                "license": c.license,
                "has_adapter": c.has_adapter,
                "adapter": c.adapter_name,
                "generation_evidence": evidence_dict,
            }
        )

    readiness_dict = None
    if plan.readiness_report:
        readiness_dict = {
            "overall_state": plan.readiness_report.overall_state.value,
            "static_validation": plan.readiness_report.static_validation.value,
            "docker_build": plan.readiness_report.docker_build.value,
            "colcon_build": plan.readiness_report.colcon_build.value,
            "runtime_validation": plan.readiness_report.runtime_validation.value,
            "manual_steps_required": plan.readiness_report.manual_steps_required,
            "evidence_summary": plan.readiness_report.evidence_summary,
        }

    lockfile_dict = {
        "$schema": "https://openrobo.org/schemas/v1/lockfile.schema.json",
        "lockfile_version": "1.1.0",
        "generator": {
            "name": "openrobo-workspace",
            "version": generator_version,
            "hardening_level": "M5.1",
        },
        "stack": {
            "id": plan.stack_id,
            "name": plan.stack_name,
            "generated_package_name": plan.bringup_package_name,
            "manifest_digest": plan.manifest_digest or compute_manifest_digest(manifest_str),
        },
        "target_platform": {
            "ros_distro": plan.target_distro,
            "os": plan.target_os,
            "arch": plan.target_arch,
        },
        "compatibility": {
            "verdict": plan.compatibility_verdict,
        },
        "workspace_readiness": readiness_dict,
        "components": components_lock,
        "dependencies": {
            "system": sorted(list(set(plan.system_dependencies))),
            "python": sorted(list(set(plan.python_dependencies))),
        },
    }

    return json.dumps(lockfile_dict, indent=2, sort_keys=True) + "\n"
