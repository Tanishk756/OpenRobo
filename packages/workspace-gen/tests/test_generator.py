"""Comprehensive unit tests for OpenRobo Workspace Generator."""

import ast
import hashlib
import json
import xml.etree.ElementTree as ET

import pytest
import yaml
from openrobo_workspace import (
    WorkspaceGenerator,
    WorkspacePlanner,
)


@pytest.fixture
def standard_stack_manifest():
    return {
        "id": "autonav_amr_stack",
        "name": "AutoNav AMR Stack",
        "description": "Autonomous mobile robot navigation and mapping stack",
        "target": {
            "ros_distro": "humble",
            "os": "ubuntu-22.04",
            "architecture": "x86_64",
        },
        "resources": [
            {"id": "nav2", "name": "Navigation2", "version": "1.1.0"},
            {"id": "slam_toolbox", "name": "SLAM Toolbox", "version": "2.6.4"},
            {"id": "ros2_control", "name": "ROS 2 Control", "version": "2.20.0"},
            {"id": "gazebo", "name": "Gazebo Simulation", "version": "harmonic"},
            {"id": "custom_driver", "name": "Custom LIDAR Driver", "version": "0.1.0"},
        ],
    }


def test_generator_files_synthesis_and_syntax(standard_stack_manifest):
    gen = WorkspaceGenerator(standard_stack_manifest)
    plan, files = gen.generate_files()

    assert len(files) >= 12
    file_paths = {f.path for f in files}

    # Verify key expected files exist
    assert "openrobo.manifest.json" in file_paths
    assert "openrobo.lock.json" in file_paths
    assert "README.md" in file_paths
    assert "setup/install_dependencies.sh" in file_paths
    assert "setup/install_dependencies.ps1" in file_paths
    assert "setup/rosdep-install.sh" in file_paths
    assert "docker/Dockerfile" in file_paths
    assert "docker/docker-compose.yml" in file_paths
    assert ".devcontainer/devcontainer.json" in file_paths
    assert "src/autonav_amr_stack_bringup/package.xml" in file_paths
    assert "src/autonav_amr_stack_bringup/CMakeLists.txt" in file_paths
    assert "src/autonav_amr_stack_bringup/launch/robot_bringup.launch.py" in file_paths
    assert "src/autonav_amr_stack_bringup/config/custom_driver.yaml.example" in file_paths

    # Validate syntax for each file type
    for f in files:
        if f.path.endswith(".py"):
            ast.parse(f.content)
        elif f.path.endswith(".xml"):
            root = ET.fromstring(f.content)
            assert root.tag == "package"
            assert root.find("name").text == "autonav_amr_stack_bringup"
        elif f.path.endswith((".yaml", ".yml")):
            yaml.safe_load(f.content)
        elif f.path.endswith(".json"):
            json.loads(f.content)


def test_generator_determinism(standard_stack_manifest):
    gen1 = WorkspaceGenerator(standard_stack_manifest)
    gen2 = WorkspaceGenerator(standard_stack_manifest)

    _, files1 = gen1.generate_files()
    _, files2 = gen2.generate_files()

    assert len(files1) == len(files2)
    for f1, f2 in zip(files1, files2):
        assert f1.path == f2.path
        assert f1.content == f2.content

    zip1 = gen1.export_archive()
    zip2 = gen2.export_archive()

    hash1 = hashlib.sha256(zip1).hexdigest()
    hash2 = hashlib.sha256(zip2).hexdigest()

    assert hash1 == hash2


def test_lockfile_generation(standard_stack_manifest):
    gen = WorkspaceGenerator(standard_stack_manifest)
    _, files = gen.generate_files()

    lock_file = next(f for f in files if f.path == "openrobo.lock.json")
    lock_data = json.loads(lock_file.content)

    assert lock_data["lockfile_version"] == "1.0.0"
    assert lock_data["generator"]["name"] == "openrobo-workspace"
    assert lock_data["stack"]["name"] == "AutoNav AMR Stack"
    assert lock_data["target_platform"]["ros_distro"] == "humble"
    assert len(lock_data["components"]) == 5

    # Check component entries in lockfile
    nav2_entry = next(c for c in lock_data["components"] if c["resource_id"] == "nav2")
    assert nav2_entry["has_adapter"] is True

    custom_entry = next(c for c in lock_data["components"] if c["resource_id"] == "custom_driver")
    assert custom_entry["has_adapter"] is False


def test_dockerfile_distro_mapping():
    distros = ["humble", "jazzy", "iron", "rolling"]
    for d in distros:
        manifest = {
            "id": f"stack_{d}",
            "name": f"Stack {d}",
            "target": {"ros_distro": d},
            "resources": [{"id": "nav2"}],
        }
        gen = WorkspaceGenerator(manifest)
        _, files = gen.generate_files()
        dockerfile = next(f for f in files if f.path == "docker/Dockerfile")
        assert f"FROM ros:{d}-ros-base AS base" in dockerfile.content


def test_incompatible_stack_handling(standard_stack_manifest):
    # INCOMPATIBLE without override should raise ValueError
    planner = WorkspacePlanner(
        stack_manifest=standard_stack_manifest,
        compatibility_result={"verdict": "INCOMPATIBLE", "errors": ["Conflicting DDS middleware"]},
        allow_incompatible=False,
    )
    with pytest.raises(ValueError, match="Cannot generate workspace for INCOMPATIBLE stack"):
        planner.plan()

    # INCOMPATIBLE with allow_incompatible=True should succeed with warnings
    planner_allowed = WorkspacePlanner(
        stack_manifest=standard_stack_manifest,
        compatibility_result={"verdict": "INCOMPATIBLE", "errors": ["Conflicting DDS middleware"]},
        allow_incompatible=True,
    )
    plan = planner_allowed.plan()
    assert plan.compatibility_verdict == "INCOMPATIBLE"


def test_conditional_stack_warnings(standard_stack_manifest):
    planner = WorkspacePlanner(
        stack_manifest=standard_stack_manifest,
        compatibility_result={"verdict": "CONDITIONAL", "warnings": ["Sensor rate may exceed bandwidth"]},
    )
    plan = planner.plan()
    assert plan.compatibility_verdict == "CONDITIONAL"
    assert any("CONDITIONAL" in w for w in plan.warnings)
    assert any("Sensor rate" in w for w in plan.warnings)
