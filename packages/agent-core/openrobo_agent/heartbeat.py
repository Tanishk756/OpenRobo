"""OpenRobo Agent Heartbeat & Telemetry Sampler."""

import os
import shutil
import time
from typing import Optional

from openrobo_runtime.ros.availability import RosEnvironmentDetector

from openrobo_agent.identity import DeviceIdentityManager
from openrobo_agent.models import AgentCapability, DeviceStatus, HeartbeatPayload


class HeartbeatSampler:
    """Samples edge health, ROS runtime availability, and system metrics."""

    def __init__(self, identity_manager: DeviceIdentityManager):
        self.identity_manager = identity_manager
        self.ros_detector = RosEnvironmentDetector()
        self._start_time = time.time()

    def sample_capabilities(self) -> AgentCapability:
        """Discover live host capabilities on the robot."""
        ros_info = self.ros_detector.detect()
        has_docker = shutil.which("docker") is not None
        has_podman = shutil.which("podman") is not None
        has_gz = (shutil.which("gz") is not None) or (shutil.which("ign") is not None)
        has_ci = shutil.which("inspect_cli") is not None or os.path.exists("/opt/ros/humble/lib/connection_inspector")

        return AgentCapability(
            ros_runtime=ros_info.status.value == "AVAILABLE" or ros_info.rclpy_available,
            docker=has_docker,
            podman=has_podman,
            gazebo=has_gz,
            connection_inspector=has_ci,
            gpu=False,
            hardware_telemetry=True,
            distro=ros_info.distro,
            rmw=ros_info.rmw_implementation,
        )

    def sample_heartbeat(self, status: DeviceStatus = DeviceStatus.ONLINE, runtime_status: Optional[str] = None) -> HeartbeatPayload:
        """Sample periodic heartbeat metrics."""
        uptime = time.time() - self._start_time
        capabilities = self.sample_capabilities()

        cpu_percent = None
        mem_percent = None
        disk_percent = None

        # Try to sample hardware metrics safely
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=None)
            mem_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage("/").percent if os.name != "nt" else psutil.disk_usage("C:\\").percent
        except Exception:
            # psutil optional
            pass

        return HeartbeatPayload(
            device_id=self.identity_manager.device_id,
            agent_version="0.7.0",
            status=status,
            uptime_seconds=round(uptime, 2),
            ros_distro=capabilities.distro,
            runtime_status=runtime_status or ("RUNNING" if capabilities.ros_runtime else "IDLE"),
            cpu_percent=cpu_percent,
            memory_percent=mem_percent,
            disk_percent=disk_percent,
            capabilities=capabilities,
        )
