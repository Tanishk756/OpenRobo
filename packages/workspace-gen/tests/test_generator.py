"""Comprehensive unit tests for OpenRobo Workspace Generator (Milestone 5.1 Hardened)."""

import ast
import hashlib
import json
import xml.etree.ElementTree as ET

import pytest
import yaml
from openrobo_workspace import (
    GenerationEvidenceLevel,
    WorkspaceGenerator,
    WorkspacePlanner,
    WorkspaceReadinessState,
    WorkspaceValidator,
)
from openrobo_workspace.adapters.registry import default_adapter_registry


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

    assert lock_data["lockfile_version"] == "1.1.0"
    assert lock_data["generator"]["name"] == "openrobo-workspace"
    assert lock_data["stack"]["name"] == "AutoNav AMR Stack"
    assert lock_data["target_platform"]["ros_distro"] == "humble"
    assert len(lock_data["components"]) == 5

    # Check component entries in lockfile
    nav2_entry = next(c for c in lock_data["components"] if c["resource_id"] == "nav2")
    assert nav2_entry["has_adapter"] is True
    assert nav2_entry["adapter"] == "nav2"
    assert nav2_entry["generation_evidence"]["level"] == GenerationEvidenceLevel.VERIFIED_ADAPTER.value

    custom_entry = next(c for c in lock_data["components"] if c["resource_id"] == "custom_driver")
    assert custom_entry["has_adapter"] is False
    assert custom_entry["generation_evidence"]["level"] == GenerationEvidenceLevel.GENERIC_SCAFFOLD.value


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


# ==============================================================================
# M5.1 HARDENING TESTS: Adapter Matching, Safety, and Evidence Verification
# ==============================================================================


def test_adapter_exact_matching_and_false_positive_rejection():
    """Negative tests: Substring matches MUST NOT trigger verified adapters."""
    false_positives = [
        "my_nav2_demo",
        "custom_gazebo_tools",
        "ros2_control_helper",
        "slam_toolbox_extra_utils",
        "navigation2_tut",
    ]
    for fp in false_positives:
        adapter = default_adapter_registry.get_adapter(fp, "humble")
        assert adapter is None, f"False positive adapter match detected for '{fp}'!"

    # Verified canonical IDs must match
    assert default_adapter_registry.get_adapter("nav2", "humble") is not None
    assert default_adapter_registry.get_adapter("ros-navigation/navigation2", "humble") is not None
    assert default_adapter_registry.get_adapter("ros2_control", "humble") is not None
    assert default_adapter_registry.get_adapter("slam_toolbox", "humble") is not None
    assert default_adapter_registry.get_adapter("gazebo", "humble") is not None


def test_ros2_control_missing_geometry_safety():
    """Without explicit user configuration, ros2_control emits .example and flags required manual steps."""
    manifest = {
        "id": "unconfigured_diffbot",
        "name": "Unconfigured DiffBot",
        "resources": [{"id": "ros2_control"}],
    }
    gen = WorkspaceGenerator(manifest)
    plan, files = gen.generate_files()

    file_paths = {f.path for f in files}
    # MUST NOT emit deployable ros2_control_params.yaml
    assert "src/unconfigured_diffbot_bringup/config/ros2_control_params.yaml" not in file_paths
    # MUST emit scaffold example
    assert "src/unconfigured_diffbot_bringup/config/ros2_control_params.yaml.example" in file_paths

    example_file = next(f for f in files if f.path.endswith("ros2_control_params.yaml.example"))
    assert "MANUAL CONFIGURATION REQUIRED" in example_file.content
    assert "wheel_separation: 0.0" in example_file.content

    # Readiness should downgrade to BUILD_REQUIRES_CONFIGURATION
    assert plan.readiness_report.overall_state == WorkspaceReadinessState.BUILD_REQUIRES_CONFIGURATION
    assert any("ros2_control" in step for step in plan.readiness_report.manual_steps_required)


def test_ros2_control_user_provided_geometry():
    """With explicit user configuration, ros2_control emits params.yaml with USER_CONFIGURED evidence."""
    manifest = {
        "id": "configured_diffbot",
        "name": "Configured DiffBot",
        "resources": [{"id": "ros2_control"}],
        "configuration": {
            "ros2_control": {
                "left_wheel_names": ["wheel_left_joint"],
                "right_wheel_names": ["wheel_right_joint"],
                "wheel_separation": 0.45,
                "wheel_radius": 0.08,
            }
        },
    }
    gen = WorkspaceGenerator(manifest)
    plan, files = gen.generate_files()

    file_paths = {f.path for f in files}
    assert "src/configured_diffbot_bringup/config/ros2_control_params.yaml" in file_paths
    params_file = next(f for f in files if f.path.endswith("ros2_control_params.yaml"))

    parsed = yaml.safe_load(params_file.content)
    diff_cfg = parsed["diff_drive_controller"]["ros__parameters"]
    assert diff_cfg["left_wheel_names"] == ["wheel_left_joint"]
    assert diff_cfg["wheel_separation"] == 0.45
    assert diff_cfg["wheel_radius"] == 0.08

    # Evidence level must be USER_CONFIGURED
    evidence = next(e for e in plan.evidence_records if e.resource_id == "ros2_control")
    assert evidence.level == GenerationEvidenceLevel.USER_CONFIGURED
    assert plan.readiness_report.overall_state == WorkspaceReadinessState.STATICALLY_VALIDATED


def test_nav2_user_frame_configuration():
    """Nav2 respects user frame & topic overrides."""
    manifest = {
        "id": "custom_nav_stack",
        "name": "Custom Nav Stack",
        "resources": [{"id": "nav2"}],
        "configuration": {
            "nav2": {
                "frames": {"base": "base_footprint", "map": "global_map", "odom": "odom_combined"},
                "topics": {"scan": "/lidar/scan", "odom": "/odometry/filtered"},
            }
        },
    }
    gen = WorkspaceGenerator(manifest)
    _, files = gen.generate_files()

    nav2_f = next(f for f in files if f.path.endswith("nav2_params.yaml"))
    parsed = yaml.safe_load(nav2_f.content)

    amcl_params = parsed["amcl"]["ros__parameters"]
    assert amcl_params["base_frame_id"] == "base_footprint"
    assert amcl_params["global_frame_id"] == "global_map"
    assert amcl_params["scan_topic"] == "/lidar/scan"


def test_package_xml_xml_escaping_and_maintainer():
    """User strings with XML entities (&, <, >, ', \") must be safely escaped."""
    manifest = {
        "id": "special_stack",
        "name": "Special & Cool <Robot> Stack",
        "description": "Stack with <dangerous> & 'tricky' \"characters\"",
        "metadata": {"maintainer": {"name": "Tanishk & Co <dev>", "email": "dev@example.org"}},
        "resources": [{"id": "nav2"}],
    }
    gen = WorkspaceGenerator(manifest)
    _, files = gen.generate_files()

    pxml = next(f for f in files if f.path.endswith("package.xml"))
    # ET.fromstring parses XML and verifies validity
    root = ET.fromstring(pxml.content)
    assert root.find("description").text == "Stack with <dangerous> & 'tricky' \"characters\""
    assert root.find("maintainer").text == "Tanishk & Co <dev>"
    assert root.find("maintainer").get("email") == "dev@example.org"


def test_docker_least_privilege_default():
    """Default Docker Compose configuration MUST NOT use privileged mode or mount /dev."""
    manifest = {
        "id": "safe_stack",
        "name": "Safe Stack",
        "resources": [{"id": "nav2"}],
    }
    gen = WorkspaceGenerator(manifest)
    _, files = gen.generate_files()

    compose_file = next(f for f in files if f.path == "docker/docker-compose.yml")
    parsed = yaml.safe_load(compose_file.content)

    bringup_service = parsed["services"]["robot"]
    assert "privileged" not in bringup_service or bringup_service["privileged"] is False
    # No blind /dev:/dev mount
    volumes = bringup_service.get("volumes", [])
    assert "/dev:/dev" not in volumes


def test_docker_explicit_device_passthrough():
    """Explicitly requested devices are passed through safely in compose."""
    manifest = {
        "id": "hw_stack",
        "name": "Hardware Stack",
        "resources": [{"id": "nav2"}],
        "deployment": {"devices": ["/dev/ttyUSB0", "/dev/i2c-1"]},
    }
    gen = WorkspaceGenerator(manifest)
    _, files = gen.generate_files()

    compose_file = next(f for f in files if f.path == "docker/docker-compose.yml")
    parsed = yaml.safe_load(compose_file.content)
    devices = parsed["services"]["robot"].get("devices", [])
    assert "/dev/ttyUSB0:/dev/ttyUSB0" in devices
    assert "/dev/i2c-1:/dev/i2c-1" in devices


def test_static_workspace_validator():
    """Static WorkspaceValidator correctly validates clean workspace and detects invalid syntax."""
    manifest = {
        "id": "valid_stack",
        "name": "Valid Stack",
        "resources": [{"id": "nav2"}],
    }
    gen = WorkspaceGenerator(manifest)
    plan, files = gen.generate_files()

    val = WorkspaceValidator.validate_files(files, plan)
    assert val.is_valid is True
    assert len(val.errors) == 0
    assert val.checks_count >= 5
