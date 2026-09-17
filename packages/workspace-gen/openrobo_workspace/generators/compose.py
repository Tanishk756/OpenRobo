"""Docker Compose generator (Least-Privilege Hardened)."""

from typing import Any, Dict

import yaml
from openrobo_workspace.models import DockerDeploymentProfile, GeneratedFile, WorkspaceGenerationPlan


def generate_docker_compose(plan: WorkspaceGenerationPlan) -> GeneratedFile:
    pkg_name = plan.bringup_package_name
    has_gazebo = any(c.adapter_name == "gazebo" for c in plan.components)
    has_cyclonedds = any("cyclonedds" in c.resource_id.lower() for c in plan.components)
    has_fastdds = any("fastdds" in c.resource_id.lower() for c in plan.components)

    env_vars = ["ROS_DOMAIN_ID=0"]
    if has_cyclonedds:
        env_vars.append("RMW_IMPLEMENTATION=rmw_cyclonedds_cpp")
    elif has_fastdds:
        env_vars.append("RMW_IMPLEMENTATION=rmw_fastrtps_cpp")

    # Service definitions using least-privilege security posture
    robot_service: Dict[str, Any] = {
        "build": {
            "context": "..",
            "dockerfile": "docker/Dockerfile",
        },
        "container_name": f"openrobo_{plan.stack_name}",
        "environment": env_vars,
        "command": f"ros2 launch {pkg_name} robot_bringup.launch.py",
    }

    # If explicit hardware devices are requested, mount only those devices
    if plan.requested_devices:
        robot_service["devices"] = [f"{d}:{d}" for d in plan.requested_devices]

    # If hardware profile is explicitly chosen or devices needed, document security rationale
    if plan.docker_profile == DockerDeploymentProfile.HARDWARE:
        robot_service["privileged"] = False
        if not plan.requested_devices:
            robot_service["# SECURITY_NOTE"] = "Hardware profile active without specific device passthroughs."

    services: Dict[str, Any] = {"robot": robot_service}

    if has_gazebo or plan.docker_profile == DockerDeploymentProfile.SIMULATION:
        sim_env = list(env_vars) + ["DISPLAY=${DISPLAY}"]
        sim_service: Dict[str, Any] = {
            "build": {
                "context": "..",
                "dockerfile": "docker/Dockerfile",
            },
            "container_name": f"openrobo_sim_{plan.stack_name}",
            "environment": sim_env,
            "volumes": ["/tmp/.X11-unix:/tmp/.X11-unix:rw"],
            "devices": ["/dev/dri:/dev/dri:rw"],
            "command": f"ros2 launch {pkg_name} robot_bringup.launch.py use_sim_time:=true",
        }
        services["simulation"] = sim_service

    compose_dict = {
        "version": "3.8",
        "services": services,
    }

    content = (
        "# ====================================================================\n"
        "# OpenRobo Docker Compose Multi-Service Deployment (Least Privilege)\n"
        "# ====================================================================\n\n"
        + yaml.safe_dump(compose_dict, sort_keys=False)
    )

    return GeneratedFile(
        path="docker/docker-compose.yml",
        content=content,
        description="Least-privilege Docker Compose multi-service deployment configuration",
    )
