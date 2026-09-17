"""Unit tests for agent read-only runtime dispatcher."""

import tempfile
from pathlib import Path

from openrobo_agent.config import AgentConfig
from openrobo_agent.identity import DeviceIdentityManager
from openrobo_agent.models import AgentOperationType
from openrobo_agent.runtime import AgentRuntimeDispatcher


def test_runtime_dispatcher_permitted_operations():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = AgentConfig(state_dir=Path(tmpdir) / "state", config_dir=Path(tmpdir) / "config")
        mgr = DeviceIdentityManager(cfg)
        dispatcher = AgentRuntimeDispatcher(mgr)

        # Ping
        ping_res = dispatcher.dispatch_operation(AgentOperationType.PING, {})
        assert ping_res["success"] is True
        assert ping_res["pong"] is True

        # Agent info
        info_res = dispatcher.dispatch_operation(AgentOperationType.GET_AGENT_INFO, {})
        assert info_res["success"] is True
        assert info_res["identity"]["device_id"] == mgr.device_id

        # ROS environment
        ros_res = dispatcher.dispatch_operation(AgentOperationType.GET_ROS_ENVIRONMENT, {})
        assert ros_res["success"] is True

        # Connection Inspector status
        ci_res = dispatcher.dispatch_operation(AgentOperationType.GET_CONNECTION_INSPECTOR_STATUS, {})
        assert ci_res["success"] is True


def test_runtime_dispatcher_rejects_forbidden_operations():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = AgentConfig(state_dir=Path(tmpdir) / "state", config_dir=Path(tmpdir) / "config")
        mgr = DeviceIdentityManager(cfg)
        dispatcher = AgentRuntimeDispatcher(mgr)

        forbidden_ops = ["SHELL", "EXEC", "RUN_COMMAND", "RUN_SCRIPT", "PYTHON", "eval", "DROP_TABLE"]
        for op in forbidden_ops:
            res = dispatcher.dispatch_operation(op, {})
            assert res["success"] is False
            assert "forbidden or unsupported" in res["error"]
