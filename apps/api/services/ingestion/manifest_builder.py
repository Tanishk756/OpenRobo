import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from apps.api.services.ingestion.models import RepoInspectionEvidence

SPDX_NORMALIZATION_MAP = {
    "apache-2.0": "Apache-2.0",
    "apache 2.0": "Apache-2.0",
    "apache2.0": "Apache-2.0",
    "apache-2": "Apache-2.0",
    "bsd": "BSD-3-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "3-clause bsd": "BSD-3-Clause",
    "bsd-2-clause": "BSD-2-Clause",
    "2-clause bsd": "BSD-2-Clause",
    "mit": "MIT",
    "gpl-3.0": "GPL-3.0-only",
    "gpl-3.0-only": "GPL-3.0-only",
    "gplv3": "GPL-3.0-only",
    "lgpl-3.0": "LGPL-3.0-only",
    "lgplv3": "LGPL-3.0-only",
    "mpl-2.0": "MPL-2.0",
    "boost": "BSL-1.0",
}

DOMAIN_KEYWORDS = {
    "navigation": ["navigation", "nav2", "path_planning", "costmap", "waypoint", "amcl", "planner", "controller_server"],
    "localization": ["localization", "slam", "odometry", "cartographer", "rtabmap", "ekf", "robot_localization", "lidar_slam"],
    "perception": ["perception", "camera", "vision", "realsense", "oak-d", "opencv", "pointcloud", "yolo", "detection", "depth"],
    "manipulation": ["manipulation", "moveit", "arm", "gripper", "kinematics", "motion_planning", "trajectory", "ik"],
    "control": ["control", "ros2_control", "controller", "hardware_interface", "pid", "motor", "actuator", "diff_drive"],
    "simulation": ["simulation", "gazebo", "webots", "ignition", "gz", "sim", "mujoco", "isaac", "urdf", "xacro"],
    "middleware": ["middleware", "dds", "rmw", "cyclonedds", "fastdds", "zenoh", "micro-ros", "transport", "comm"],
    "visualization": ["visualization", "rviz", "plotjuggler", "foxglove", "display", "gui", "ui", "dashboard"],
}

CAPABILITY_KEYWORDS = {
    "path_planning": ["nav2", "planner", "path_planning", "nav_core", "global_planner"],
    "obstacle_avoidance": ["obstacle", "collision", "costmap", "avoidance"],
    "slam": ["slam", "mapping", "cartographer", "slam_toolbox"],
    "motion_planning": ["moveit", "ompl", "motion_plan", "trajectory"],
    "kinematics": ["kinematics", "kdl", "trac_ik", "ikfast", "forward_kinematics"],
    "sensor_streaming": ["camera", "sensor", "realsense", "lidar", "pointcloud_to_laserscan"],
    "simulation_rendering": ["gazebo", "webots", "rendering", "physics_engine"],
    "hardware_abstraction": ["ros2_control", "hardware_interface", "actuator", "driver"],
}


def normalize_spdx_license(raw_license: str | None) -> str:
    if not raw_license:
        return "NOASSERTION"
    clean = raw_license.strip().lower()
    return SPDX_NORMALIZATION_MAP.get(clean, raw_license.strip() if len(raw_license) <= 50 else "NOASSERTION")


def normalize_semver(raw_version: str | None) -> str:
    if not raw_version or not raw_version.strip():
        return "0.1.0"
    v = raw_version.strip()
    match = re.match(r"^([0-9]+(?:\.[0-9]+)*)(.*)$", v)
    if not match:
        return "0.1.0"
    digits = match.group(1).split(".")
    suffix = match.group(2)
    while len(digits) < 3:
        digits.append("0")
    return ".".join(digits[:3]) + suffix


def sanitize_slug(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]", "-", name).lower().strip(".-")
    return slug or "unnamed-resource"


def infer_domains_and_capabilities(
    name: str, description: str | None, topics: List[str], robotics_markers: List[str]
) -> Tuple[List[str], List[str]]:
    corpus = f"{name} {description or ''} {' '.join(topics)} {' '.join(robotics_markers)}".lower()
    domains = set()
    capabilities = set()

    for domain, kw_list in DOMAIN_KEYWORDS.items():
        if any(kw in corpus for kw in kw_list):
            domains.add(domain)

    for cap, kw_list in CAPABILITY_KEYWORDS.items():
        if any(kw in corpus for kw in kw_list):
            capabilities.add(cap)

    return sorted(list(domains)), sorted(list(capabilities))


def build_candidate_manifests(evidence: RepoInspectionEvidence) -> List[Dict[str, Any]]:
    candidates = []
    utc_timestamp = datetime.now(timezone.utc).isoformat()
    repo_url = f"https://github.com/{evidence.owner}/{evidence.repo}"

    base_provenance = {
        "source_provider": "github",
        "source_url": repo_url,
        "source_identifier": f"{evidence.owner}/{evidence.repo}",
        "upstream_revision": evidence.commit_sha or evidence.default_branch,
        "ingestion_timestamp": utc_timestamp,
        "provenance_classification": "UPSTREAM_DATA",
        "inspected_files": evidence.inspected_files,
    }

    # Case A: Monorepo (Multiple packages discovered)
    if len(evidence.packages) > 1:
        repo_slug = sanitize_slug(evidence.repo)
        repo_domains, repo_caps = infer_domains_and_capabilities(
            evidence.repo, evidence.description, evidence.topics, evidence.robotics_markers
        )
        repo_license = normalize_spdx_license(evidence.spdx_license_id)

        top_candidate = {
            "id": f"{sanitize_slug(evidence.owner)}/{repo_slug}",
            "name": evidence.repo.replace("-", " ").replace("_", " ").title(),
            "version": "1.0.0",
            "type": "software",
            "summary": (evidence.description or f"{evidence.repo} robotics software framework")[:280],
            "description": evidence.description or f"Monorepo containing {len(evidence.packages)} packages.",
            "source": {
                "repo_url": repo_url,
                "vcs_type": "git",
                "branch": evidence.default_branch,
                "commit": evidence.commit_sha or evidence.default_branch,
            },
            "license": {"spdx_id": repo_license, "license_url": f"{repo_url}/blob/{evidence.default_branch}/LICENSE"},
            "robotics_domains": repo_domains,
            "capabilities": repo_caps,
            "platforms": {
                "operating_systems": ["Linux", "Ubuntu 22.04", "Ubuntu 24.04"],
                "cpu_architectures": ["x86_64", "arm64"],
                "ros_versions": ["ROS 2 Humble", "ROS 2 Jazzy"] if "ros_package" in evidence.robotics_markers else [],
            },
            "evidence": {
                "level": "automatically_detected",
                "notes": f"Ingested from GitHub monorepo with {len(evidence.packages)} ROS packages.",
            },
            "provenance": base_provenance,
            "sub_packages": [pkg.name for pkg in evidence.packages],
        }
        candidates.append(top_candidate)

        for pkg in evidence.packages:
            pkg_slug = sanitize_slug(pkg.name)
            pkg_domains, pkg_caps = infer_domains_and_capabilities(pkg.name, pkg.description, evidence.topics, evidence.robotics_markers)
            pkg_license = normalize_spdx_license(pkg.license or evidence.spdx_license_id)

            pkg_candidate = {
                "id": f"{sanitize_slug(evidence.owner)}/{pkg_slug}",
                "name": pkg.name,
                "version": normalize_semver(pkg.version),
                "type": "ros_package",
                "summary": (pkg.description or f"ROS package {pkg.name} from {evidence.repo}")[:280],
                "description": pkg.description or f"ROS package manifest at '{pkg.rel_path}' in {repo_url}.",
                "source": {
                    "repo_url": repo_url,
                    "vcs_type": "git",
                    "branch": evidence.default_branch,
                    "commit": evidence.commit_sha or evidence.default_branch,
                },
                "license": {"spdx_id": pkg_license, "license_url": f"{repo_url}/blob/{evidence.default_branch}/LICENSE"},
                "robotics_domains": pkg_domains or repo_domains,
                "capabilities": pkg_caps or repo_caps,
                "platforms": {
                    "operating_systems": ["Linux", "Ubuntu 22.04", "Ubuntu 24.04"],
                    "cpu_architectures": ["x86_64", "arm64"],
                    "ros_versions": ["ROS 2 Humble", "ROS 2 Jazzy"],
                },
                "evidence": {
                    "level": "upstream_declared" if pkg.license else "automatically_detected",
                    "notes": f"Extracted from manifest '{pkg.rel_path}'.",
                },
                "dependencies": {
                    "build": pkg.build_depends,
                    "exec": pkg.exec_depends,
                    "test": pkg.test_depends,
                    "buildtool": pkg.buildtool_depends,
                },
                "provenance": {**base_provenance, "source_manifest_path": pkg.rel_path, "maintainers": pkg.maintainers},
            }
            candidates.append(pkg_candidate)

    # Case B: Single Package Repository
    elif len(evidence.packages) == 1:
        pkg = evidence.packages[0]
        pkg_slug = sanitize_slug(evidence.repo)
        pkg_domains, pkg_caps = infer_domains_and_capabilities(
            f"{evidence.repo} {pkg.name}", pkg.description or evidence.description, evidence.topics, evidence.robotics_markers
        )
        pkg_license = normalize_spdx_license(pkg.license or evidence.spdx_license_id)

        single_candidate = {
            "id": f"{sanitize_slug(evidence.owner)}/{pkg_slug}",
            "name": pkg.name,
            "version": normalize_semver(pkg.version),
            "type": "ros_package",
            "summary": (pkg.description or evidence.description or f"{evidence.repo} package")[:280],
            "description": pkg.description or evidence.description or f"ROS package {pkg.name}",
            "source": {
                "repo_url": repo_url,
                "vcs_type": "git",
                "branch": evidence.default_branch,
                "commit": evidence.commit_sha or evidence.default_branch,
            },
            "license": {"spdx_id": pkg_license, "license_url": f"{repo_url}/blob/{evidence.default_branch}/LICENSE"},
            "robotics_domains": pkg_domains,
            "capabilities": pkg_caps,
            "platforms": {
                "operating_systems": ["Linux", "Ubuntu 22.04", "Ubuntu 24.04"],
                "cpu_architectures": ["x86_64", "arm64"],
                "ros_versions": ["ROS 2 Humble", "ROS 2 Jazzy"],
            },
            "evidence": {
                "level": "upstream_declared" if pkg.license else "automatically_detected",
                "notes": f"Extracted from manifest '{pkg.rel_path}'.",
            },
            "dependencies": {
                "build": pkg.build_depends,
                "exec": pkg.exec_depends,
                "test": pkg.test_depends,
                "buildtool": pkg.buildtool_depends,
            },
            "provenance": {**base_provenance, "source_manifest_path": pkg.rel_path, "maintainers": pkg.maintainers},
        }
        candidates.append(single_candidate)

    # Case C: Non-ROS / Generic Robotics Repository
    else:
        repo_slug = sanitize_slug(evidence.repo)
        repo_domains, repo_caps = infer_domains_and_capabilities(
            evidence.repo, evidence.description, evidence.topics, evidence.robotics_markers
        )
        repo_license = normalize_spdx_license(evidence.spdx_license_id)

        res_type = "software"
        if "urdf_xacro" in evidence.robotics_markers or "3d_mesh" in evidence.robotics_markers:
            res_type = "simulation"
        elif "control" in evidence.robotics_markers:
            res_type = "driver"

        generic_candidate = {
            "id": f"{sanitize_slug(evidence.owner)}/{repo_slug}",
            "name": evidence.repo.replace("-", " ").replace("_", " ").title(),
            "version": "0.1.0",
            "type": res_type,
            "summary": (evidence.description or f"{evidence.repo} robotics project")[:280],
            "description": evidence.description or f"Robotics repository {evidence.owner}/{evidence.repo}",
            "source": {
                "repo_url": repo_url,
                "vcs_type": "git",
                "branch": evidence.default_branch,
                "commit": evidence.commit_sha or evidence.default_branch,
            },
            "license": {"spdx_id": repo_license, "license_url": f"{repo_url}/blob/{evidence.default_branch}/LICENSE"},
            "robotics_domains": repo_domains,
            "capabilities": repo_caps,
            "platforms": {
                "operating_systems": ["Linux", "Ubuntu 22.04", "Ubuntu 24.04"],
                "cpu_architectures": ["x86_64", "arm64"],
                "ros_versions": [],
            },
            "evidence": {"level": "automatically_detected", "notes": "Static inspection without package.xml manifest."},
            "provenance": base_provenance,
        }
        candidates.append(generic_candidate)

    return candidates
