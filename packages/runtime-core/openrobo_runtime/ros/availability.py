"""ROS Environment Detector and Capability Discovery."""

import os
import shutil
from typing import Optional

from openrobo_runtime.models import (
    RosEnvironmentInfo,
    RosEnvironmentStatus,
)


class RosEnvironmentDetector:
    """Detects active ROS 2 installation, environment variables, RMW, and CLI tools."""

    def detect(self) -> RosEnvironmentInfo:
        ros_distro = os.environ.get("ROS_DISTRO")
        ros_version = os.environ.get("ROS_VERSION")
        rmw_impl = os.environ.get("RMW_IMPLEMENTATION")
        domain_id_str = os.environ.get("ROS_DOMAIN_ID")
        domain_id = int(domain_id_str) if domain_id_str and domain_id_str.isdigit() else None

        ros2_cli = shutil.which("ros2") is not None

        # Check rclpy without crashing if absent
        rclpy_available = False
        try:
            import rclpy  # noqa: F401
            rclpy_available = True
        except (ImportError, Exception):
            rclpy_available = False

        # Installation prefix discovery
        installation_prefix: Optional[str] = None
        ament_prefix_path = os.environ.get("AMENT_PREFIX_PATH", "")
        if ament_prefix_path:
            for p in ament_prefix_path.split(os.pathsep):
                if p.strip() and os.path.isdir(p.strip()):
                    installation_prefix = p.strip()
                    break

        # Determine overall status
        if ros2_cli and (rclpy_available or ros_distro):
            status = RosEnvironmentStatus.AVAILABLE
            details = f"ROS 2 environment detected (distro={ros_distro or 'unknown'}, rclpy={'yes' if rclpy_available else 'no'})."
        elif ros2_cli or ros_distro:
            status = RosEnvironmentStatus.MISCONFIGURED
            details = "Partial ROS 2 configuration detected (missing source setup or rclpy python path)."
        else:
            status = RosEnvironmentStatus.UNAVAILABLE
            details = "No ROS 2 distribution, CLI, or rclpy detected in current host environment."

        return RosEnvironmentInfo(
            status=status,
            distro=ros_distro,
            ros_version=ros_version,
            rmw_implementation=rmw_impl,
            domain_id=domain_id,
            rclpy_available=rclpy_available,
            ros2_cli_available=ros2_cli,
            installation_prefix=installation_prefix,
            details=details,
        )
