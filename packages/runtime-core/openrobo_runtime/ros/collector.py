"""Live ROS 2 Graph Collector using rclpy or safe CLI fallback."""

import logging
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional

from openrobo_runtime.ros.availability import RosEnvironmentDetector

logger = logging.getLogger(__name__)


class LiveRosGraphCollector:
    """Collects real active ROS 2 nodes, topics, publishers, subscribers, and QoS settings."""

    def __init__(self, detector: Optional[RosEnvironmentDetector] = None):
        self.detector = detector or RosEnvironmentDetector()

    def collect(self) -> Dict[str, Any]:
        """Collect live computational graph telemetry safely."""
        env_info = self.detector.detect()
        if env_info.status.value != "AVAILABLE" and not env_info.ros2_cli_available and not env_info.rclpy_available:
            return {
                "status": "ROS_RUNTIME_UNAVAILABLE",
                "reason": env_info.details or "ROS 2 runtime not available on host.",
                "nodes": [],
                "topics": [],
            }

        # Try native rclpy first
        if env_info.rclpy_available:
            try:
                return self._collect_via_rclpy()
            except Exception as e:
                logger.warning("rclpy live collection failed, attempting CLI fallback: %s", e)

        # Fallback to ros2 CLI
        if env_info.ros2_cli_available:
            return self._collect_via_cli()

        return {
            "status": "ROS_RUNTIME_UNAVAILABLE",
            "reason": "Neither rclpy nor ros2 CLI could collect graph telemetry.",
            "nodes": [],
            "topics": [],
        }

    def _collect_via_rclpy(self) -> Dict[str, Any]:
        """Collect graph via native rclpy APIs with an ephemeral node."""
        import rclpy
        from rclpy.node import Node

        if not rclpy.ok():
            rclpy.init(args=None)
            should_shutdown = True
        else:
            should_shutdown = False

        temp_node = Node("_openrobo_graph_collector")
        try:
            # Allow DDS discovery to sync
            for _ in range(5):
                rclpy.spin_once(temp_node, timeout_sec=0.1)
                time.sleep(0.1)

            # 1. Get nodes and namespaces
            node_names_and_ns = temp_node.get_node_names_and_namespaces()
            nodes: List[Dict[str, Any]] = []

            for name, ns in node_names_and_ns:
                # Exclude self
                if name == "_openrobo_graph_collector":
                    continue

                full_name = f"{ns.rstrip('/')}/{name}" if ns != "/" else f"/{name}"
                pub_topics = [t[0] for t in temp_node.get_publisher_names_and_types_by_node(name, ns)]
                sub_topics = [t[0] for t in temp_node.get_subscriber_names_and_types_by_node(name, ns)]
                services = [s[0] for s in temp_node.get_service_names_and_types_by_node(name, ns)]

                nodes.append({
                    "name": name,
                    "namespace": ns,
                    "full_name": full_name,
                    "is_present": True,
                    "is_alive": True,
                    "pid": None,  # Provenance: cannot be verified from ROS graph alone
                    "publisher_topics": pub_topics,
                    "subscriber_topics": sub_topics,
                    "services": services,
                    "actions": [],
                })

            # 2. Get topics and QoS
            topic_names_and_types = temp_node.get_topic_names_and_types()
            topics: List[Dict[str, Any]] = []

            for topic_name, type_list in topic_names_and_types:
                primary_type = type_list[0] if type_list else "unknown"

                pubs_fn = getattr(temp_node, "get_publishers_info_by_topic", None)
                pubs_info = pubs_fn(topic_name) if pubs_fn else []

                subs_fn = getattr(temp_node, "get_subscriptions_info_by_topic", None) or getattr(
                    temp_node, "get_subscribers_info_by_topic", None
                )
                subs_info = subs_fn(topic_name) if subs_fn else []

                pub_names = [p.node_name for p in pubs_info]
                sub_names = [s.node_name for s in subs_info]

                pub_qos = self._extract_qos_dict(pubs_info[0].qos_profile) if pubs_info else {}
                sub_qos = self._extract_qos_dict(subs_info[0].qos_profile) if subs_info else {}

                topics.append({
                    "name": topic_name,
                    "type": primary_type,
                    "publishers": pub_names,
                    "subscribers": sub_names,
                    "publisher_qos": pub_qos,
                    "subscriber_qos": sub_qos,
                })

            return {
                "status": "COLLECTED_VIA_RCLPY",
                "method": "rclpy",
                "nodes": nodes,
                "topics": topics,
            }
        finally:
            temp_node.destroy_node()
            if should_shutdown and rclpy.ok():
                rclpy.shutdown()

    def _extract_qos_dict(self, qos_profile: Any) -> Dict[str, str]:
        """Convert rclpy QoSProfile to normalized string map."""
        if not qos_profile:
            return {}
        try:
            rel = str(qos_profile.reliability).split(".")[-1].upper()
            dur = str(qos_profile.durability).split(".")[-1].upper()
            hist = str(qos_profile.history).split(".")[-1].upper()
            return {
                "reliability": rel,
                "durability": dur,
                "history": hist,
                "depth": str(getattr(qos_profile, "depth", 10)),
            }
        except Exception:
            return {}

    def _collect_via_cli(self) -> Dict[str, Any]:
        """Fallback graph discovery using ros2 node/topic CLI."""
        ros2_cmd = shutil.which("ros2")
        if not ros2_cmd:
            return {"status": "ERROR", "reason": "ros2 executable not found", "nodes": [], "topics": []}

        try:
            # Nodes
            node_out = subprocess.run([ros2_cmd, "node", "list"], capture_output=True, text=True, timeout=5)
            node_lines = [line.strip() for line in node_out.stdout.splitlines() if line.strip()]

            nodes = []
            for n in node_lines:
                ns = "/"
                name = n.lstrip("/")
                if "/" in name:
                    parts = name.rsplit("/", 1)
                    ns = f"/{parts[0]}"
                    name = parts[1]
                nodes.append({
                    "name": name,
                    "namespace": ns,
                    "full_name": n,
                    "is_present": True,
                    "is_alive": True,
                    "pid": None,
                    "publisher_topics": [],
                    "subscriber_topics": [],
                    "services": [],
                    "actions": [],
                })

            # Topics
            topic_out = subprocess.run([ros2_cmd, "topic", "list", "-t"], capture_output=True, text=True, timeout=5)
            topics = []
            for line in topic_out.stdout.splitlines():
                line = line.strip()
                if not line or " [" not in line:
                    continue
                parts = line.split(" [")
                tname = parts[0].strip()
                ttype = parts[1].rstrip("]").strip()
                topics.append({
                    "name": tname,
                    "type": ttype,
                    "publishers": [],
                    "subscribers": [],
                    "publisher_qos": {},
                    "subscriber_qos": {},
                })

            return {
                "status": "COLLECTED_VIA_CLI",
                "method": "ros2_cli_fallback",
                "nodes": nodes,
                "topics": topics,
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "reason": f"CLI graph collection error: {str(e)}",
                "nodes": [],
                "topics": [],
            }
