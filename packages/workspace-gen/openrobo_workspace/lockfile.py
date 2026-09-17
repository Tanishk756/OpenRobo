"""Lockfile generator for OpenRobo workspaces."""

import hashlib
import json

from openrobo_workspace.models import WorkspaceGenerationPlan


def compute_manifest_digest(manifest_str: str) -> str:
    return hashlib.sha256(manifest_str.encode("utf-8")).hexdigest()


def generate_lockfile(
    plan: WorkspaceGenerationPlan,
    manifest_str: str,
    generator_version: str = "0.5.0"
) -> str:
    components_lock = []
    for c in sorted(plan.components, key=lambda x: x.resource_id):
        components_lock.append(
            {
                "resource_id": c.resource_id,
                "name": c.name,
                "version": c.resolved_version,
                "source_strategy": c.source_strategy.value,
                "build_type": c.build_type.value,
                "repository_url": c.repository_url or "UNKNOWN",
                "revision": c.commit_or_tag or "UNKNOWN",
                "license": c.license,
                "has_adapter": c.has_adapter,
                "adapter_name": c.adapter_name or ("custom" if c.has_adapter else None),
            }
        )

    lockfile_dict = {
        "$schema": "https://openrobo.org/schemas/v1/lockfile.schema.json",
        "lockfile_version": "1.0.0",
        "generator": {
            "name": "openrobo-workspace",
            "version": generator_version,
        },
        "stack": {
            "id": plan.stack_id,
            "name": plan.stack_name,
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
        "components": components_lock,
        "dependencies": {
            "system": sorted(list(set(plan.system_dependencies))),
            "python": sorted(list(set(plan.python_dependencies))),
        },
    }

    return json.dumps(lockfile_dict, indent=2, sort_keys=True) + "\n"
