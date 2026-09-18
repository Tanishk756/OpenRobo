"""Runtime Verification, Introspection & Simulation API Router (Milestone 6.1)."""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from openrobo_runtime import (
    BuildRunner,
    BuildVerificationResult,
    ConnectionComparator,
    ConnectionInspectorAdapter,
    ConnectionInspectorReport,
    ExecutionProviderType,
    GazeboAdapter,
    LiveRosGraphCollector,
    MujocoAdapter,
    ProviderDetector,
    ProviderInfo,
    RosbagInspector,
    RosEnvironmentDetector,
    RosEnvironmentInfo,
    RuntimeContract,
    RuntimeSession,
    RuntimeSessionManager,
    RuntimeVerificationResult,
    WebotsAdapter,
)
from pydantic import BaseModel, Field

router = APIRouter(prefix="/runtime", tags=["Runtime & Simulation"])

session_manager = RuntimeSessionManager()
detector = ProviderDetector()
env_detector = RosEnvironmentDetector()
graph_collector = LiveRosGraphCollector(detector=env_detector)
build_runner = BuildRunner(detector=detector)
ci_adapter = ConnectionInspectorAdapter()
comparator = ConnectionComparator()
gazebo_adapter = GazeboAdapter()
webots_adapter = WebotsAdapter()
mujoco_adapter = MujocoAdapter()


class BuildVerifyRequest(BaseModel):
    workspace_dir: str
    target_distro: str = "humble"
    provider: Optional[ExecutionProviderType] = None
    timeout_sec: int = 300


class CompareRequest(BaseModel):
    planned_manifest: Dict[str, Any]
    observed_nodes: List[Dict[str, Any]] = Field(default_factory=list)
    observed_topics: List[Dict[str, Any]] = Field(default_factory=list)
    observed_tfs: Optional[List[Dict[str, Any]]] = None
    runtime_contract: Optional[RuntimeContract] = None


class CreateSessionRequest(BaseModel):
    stack_id: str
    workspace_path: str
    workspace_digest: str = ""
    ros_distro: str = "humble"
    domain_id: int = 0
    provider: ExecutionProviderType = ExecutionProviderType.LOCAL_PROCESS


class RosbagInspectRequest(BaseModel):
    bag_path: str


@router.post("/build/verify", response_model=BuildVerificationResult)
async def verify_build(req: BuildVerifyRequest):
    """Execute controlled colcon/container build verification on a generated workspace."""
    try:
        res = build_runner.verify_workspace_build(
            workspace_dir=req.workspace_dir,
            target_distro=req.target_distro,
            requested_provider=req.provider,
            timeout_sec=req.timeout_sec,
        )
        return res
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Build verification failed: {str(e)}",
        )


@router.get("/providers", response_model=Dict[str, ProviderInfo])
async def list_providers():
    """Discover available containerized and local build execution providers."""
    return detector.detect_all()


@router.get("/environment", response_model=RosEnvironmentInfo)
async def get_ros_environment():
    """Detect presence, active distribution, RMW implementation, and CLI tools for host ROS."""
    return env_detector.detect()


@router.get("/connection-inspector", response_model=ConnectionInspectorReport)
async def get_connection_inspector_status(distro: Optional[str] = None):
    """Detect presence, version, and licensing boundary for external Connection Inspector."""
    return ci_adapter.detect(target_distro=distro)


@router.post("/connection-inspector/cli")
async def run_connection_inspector_cli(timeout_sec: int = 10):
    """Execute external inspect_cli process safely on explicit user request."""
    res = ci_adapter.run_cli_inspection(timeout_sec=timeout_sec)
    if res.get("status") == "NOT_EXECUTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res.get("error", "Connection Inspector is not installed."),
        )
    return res


@router.post("/connection-inspector/gui")
async def launch_connection_inspector_gui():
    """Return command string for launch on explicit user interaction (no automated background spawn)."""
    detection = ci_adapter.detect()
    if detection.status.value != "INSTALLED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connection Inspector is not installed in the ROS environment.",
        )
    cmd = ci_adapter.build_gui_launch_command()
    return {
        "status": "COMMAND_PREPARED",
        "command": cmd,
        "note": "Launch via desktop terminal in active display session.",
    }


@router.get("/introspection/live")
async def collect_live_graph():
    """Query real-time ROS 2 computational graph telemetry via rclpy or CLI fallback."""
    return graph_collector.collect()


@router.post("/introspection/compare", response_model=RuntimeVerificationResult)
async def compare_runtime_graph(req: CompareRequest):
    """Compare planned stack manifest intent or explicit runtime contract against observed graph."""
    try:
        return comparator.compare(
            planned_manifest=req.planned_manifest,
            observed_nodes=req.observed_nodes,
            observed_topics=req.observed_topics,
            observed_tfs=req.observed_tfs,
            runtime_contract=req.runtime_contract,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph comparison failed: {str(e)}",
        )


@router.get("/simulators")
async def list_simulators():
    """Detect available simulation toolchains (Gazebo, Webots, MuJoCo)."""
    return {
        "gazebo": gazebo_adapter.detect(),
        "webots": webots_adapter.detect(),
        "mujoco": mujoco_adapter.detect(),
    }


@router.post("/telemetry/rosbag")
async def inspect_rosbag(req: RosbagInspectRequest):
    """Inspect metadata and topic statistics for a rosbag2 dataset."""
    res = RosbagInspector.inspect_bag_directory(req.bag_path)
    if "error" in res:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res["error"])
    return res


# --- Session Lifecycle Endpoints ---


@router.post("/sessions", response_model=RuntimeSession, status_code=status.HTTP_201_CREATED)
async def create_runtime_session(req: CreateSessionRequest):
    """Create a tracked runtime session for a robot stack."""
    if not os.path.exists(req.workspace_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workspace path '{req.workspace_path}' does not exist.",
        )
    return session_manager.create_session(
        stack_id=req.stack_id,
        workspace_path=req.workspace_path,
        workspace_digest=req.workspace_digest,
        ros_distro=req.ros_distro,
        domain_id=req.domain_id,
        provider=req.provider,
    )


@router.get("/sessions", response_model=List[RuntimeSession])
async def list_runtime_sessions():
    """List all active and past runtime sessions."""
    return session_manager.list_sessions()


@router.get("/sessions/{session_id}", response_model=RuntimeSession)
async def get_runtime_session(session_id: str):
    """Retrieve details for a specific runtime session."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return session


@router.post("/sessions/{session_id}/stop", response_model=RuntimeSession)
async def stop_runtime_session(session_id: str):
    """Stop an active runtime session and clean child processes."""
    session = session_manager.stop_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return session


@router.get("/sessions/{session_id}/graph")
async def get_session_graph(session_id: str):
    """Query live ROS computational graph for the specified runtime session."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return graph_collector.collect()


@router.get("/events")
async def stream_runtime_events():
    """Server-Sent Events (SSE) stream for real-time runtime state updates."""

    async def event_generator():
        env_info = env_detector.detect()
        initial_event = {
            "event": "runtime_state_sync",
            "ros_status": env_info.status.value,
            "distro": env_info.distro,
            "sessions_count": len(session_manager.sessions),
        }
        yield f"data: {json.dumps(initial_event)}\n\n"
        # Heartbeat pulse
        for _ in range(5):
            await asyncio.sleep(2)
            pulse = {"event": "heartbeat", "active_sessions": len(session_manager.list_sessions())}
            yield f"data: {json.dumps(pulse)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
