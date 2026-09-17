#!/usr/bin/env python3
"""
OpenRobo Schema Validation Utility
Validates canonical JSON schema files and sample resource manifests.
"""

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT_DIR = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = ROOT_DIR / "schemas"


def validate_schema_file(schema_path: Path) -> bool:
    print(f"Validating schema definition: {schema_path.name}...")
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_data = json.load(f)
        Draft202012Validator.check_schema(schema_data)
        print(f"  [OK] {schema_path.name} is a valid Draft 2020-12 JSON Schema.")
        return True
    except Exception as e:
        print(f"  [ERROR] {schema_path.name} failed validation: {e}")
        return False


def validate_sample_instance():
    print("Validating sample resource manifest against resource.schema.json...")
    resource_schema_path = SCHEMAS_DIR / "resource.schema.json"
    with open(resource_schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    sample_manifest = {
        "id": "ros-navigation/nav2",
        "name": "Nav2 Autonomous Navigation Framework",
        "version": "1.3.0",
        "type": "ros_package",
        "summary": "ROS 2 Navigation Framework for Autonomous Mobile Robots",
        "source": {"repo_url": "https://github.com/ros-navigation/navigation2", "vcs_type": "git"},
        "license": {"spdx_id": "Apache-2.0"},
        "robotics_domains": ["ground", "amr", "rover"],
        "capabilities": ["navigation", "path-planning", "obstacle-avoidance"],
        "platforms": {"operating_systems": ["Ubuntu 24.04"], "cpu_architectures": ["x86_64", "arm64"], "ros_versions": ["Jazzy"]},
        "evidence": {"level": "ci_verified"},
    }

    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(sample_manifest))
    if errors:
        print(f"  [ERROR] Sample instance validation failed with {len(errors)} errors:")
        for err in errors:
            print(f"    - {err.message}")
        return False
    else:
        print("  [OK] Sample resource manifest successfully validated.")
        return True


def validate_sample_stack_instance():
    print("Validating sample stack manifest against stack.schema.json...")
    stack_schema_path = SCHEMAS_DIR / "stack.schema.json"
    sample_stack_path = ROOT_DIR / "samples" / "mobile_robot_nav.stack.json"
    with open(stack_schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    with open(sample_stack_path, "r", encoding="utf-8") as f:
        sample_stack = json.load(f)

    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(sample_stack))
    if errors:
        print(f"  [ERROR] Sample stack validation failed with {len(errors)} errors:")
        for err in errors:
            print(f"    - {err.message}")
        return False
    else:
        print("  [OK] Sample stack manifest successfully validated.")
        return True


def main():
    all_valid = True
    for schema_file in SCHEMAS_DIR.glob("*.schema.json"):
        if not validate_schema_file(schema_file):
            all_valid = False

    if not validate_sample_instance():
        all_valid = False
    if not validate_sample_stack_instance():
        all_valid = False

    if not all_valid:
        print("\nSchema validation completed with ERRORS.")
        sys.exit(1)
    else:
        print("\nAll OpenRobo schemas and sample instances are VALID.")
        sys.exit(0)


if __name__ == "__main__":
    main()
