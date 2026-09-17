"""OpenRobo Agent Read-Only Introspection & Operations Handler."""

from typing import Any, Dict

from openrobo_runtime.integrations.connection_inspector import ConnectionInspectorAdapter
from openrobo_runtime.ros.availability import RosEnvironmentDetector
from openrobo_runtime.ros.collector import LiveRosGraphCollector
from openrobo_runtime.simulators.gazebo import GazeboAdapter

from openrobo_agent.identity import DeviceIdentityManager
from openrobo_agent.models import AgentOperationType


class AgentRuntimeDispatcher:
    """Dispatches strictly typed, read-only introspection requests on the edge."""

    def __init__(self, identity_manager: DeviceIdentityManager):
        self.identity_manager = identity_manager
        self.ros_detector = RosEnvironmentDetector()
        self.graph_collector = LiveRosGraphCollector(self.ros_detector)
        self.ci_adapter = ConnectionInspectorAdapter()
        self.gazebo_adapter = GazeboAdapter()

    def dispatch_operation(self, op_type: str | AgentOperationType, params: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch a typed operation. Rejects any non-read-only or arbitrary commands."""
        try:
            if isinstance(op_type, str):
                op_enum = AgentOperationType(op_type)
            else:
                op_enum = op_type
        except ValueError:
            return {
                "success": False,
                "error": f"Operation '{op_type}' is forbidden or unsupported. Only read-only fleet operations permitted.",
            }

        if op_enum == AgentOperationType.PING:
            return {"success": True, "pong": True, "timestamp": self.identity_manager.get_identity().created_at}

        elif op_enum == AgentOperationType.GET_AGENT_INFO:
            identity = self.identity_manager.get_identity()
            return {"success": True, "identity": identity.model_dump()}

        elif op_enum == AgentOperationType.GET_ROS_ENVIRONMENT:
            env_info = self.ros_detector.detect()
            return {"success": True, "environment": env_info.model_dump()}

        elif op_enum == AgentOperationType.GET_ROS_GRAPH:
            graph_data = self.graph_collector.collect()
            return {"success": True, "graph": graph_data}

        elif op_enum == AgentOperationType.GET_CONNECTION_INSPECTOR_STATUS:
            ci_info = self.ci_adapter.detect()
            return {"success": True, "connection_inspector": ci_info.model_dump()}

        elif op_enum == AgentOperationType.GET_SIMULATOR_STATUS:
            gz_info = self.gazebo_adapter.detect()
            return {"success": True, "simulators": {"gazebo": gz_info.model_dump()}}

        elif op_enum == AgentOperationType.GET_RUNTIME_STATUS:
            ros_info = self.ros_detector.detect()
            return {
                "success": True,
                "runtime_status": "RUNNING" if ros_info.status.value == "AVAILABLE" else "IDLE",
                "ros_distro": ros_info.distro,
            }

        elif op_enum == AgentOperationType.GET_RUNTIME_DIAGNOSTICS:
            graph_data = self.graph_collector.collect()
            return {
                "success": True,
                "node_count": len(graph_data.get("nodes", [])),
                "topic_count": len(graph_data.get("topics", [])),
                "collector_status": graph_data.get("status"),
            }

        return {
            "success": False,
            "error": f"Unhandled operation: {op_enum}",
        }

    def get_ros_environment(self) -> Dict[str, Any]:
        res = self.dispatch_operation(AgentOperationType.GET_ROS_ENVIRONMENT, {})
        return res.get("environment", {})

    def get_connection_inspector_status(self) -> Dict[str, Any]:
        res = self.dispatch_operation(AgentOperationType.GET_CONNECTION_INSPECTOR_STATUS, {})
        return res.get("connection_inspector", {})
