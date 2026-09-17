"""Runtime Verification, Introspection & Simulation API Router (Milestone 6)."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from openrobo_runtime import (
    BuildRunner,
    BuildVerificationResult,
    ConnectionComparator,
    ConnectionInspectorAdapter,
    ConnectionInspectorReport,
    ExecutionProviderType,
    GazeboAdapter,
    MujocoAdapter,
    ProviderDetector,
    ProviderInfo,
    RosbagInspector,
    RuntimeSessionManager,
    RuntimeVerificationResult,
    WebotsAdapter,
)
from pydantic import BaseModel, Field

router = APIRouter(prefix="/runtime", tags=["Runtime & Simulation"])

session_manager = RuntimeSessionManager()
detector = ProviderDetector()
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Build verification failed: {str(e)}")


@router.get("/providers", response_model=Dict[str, ProviderInfo])
async def list_providers():
    """Discover available containerized and local build execution providers."""
    return detector.detect_all()


@router.get("/connection-inspector", response_model=ConnectionInspectorReport)
async def get_connection_inspector_status(distro: Optional[str] = None):
    """Detect presence, version, and licensing boundary for external Connection Inspector."""
    return ci_adapter.detect(target_distro=distro)


@router.post("/introspection/compare", response_model=RuntimeVerificationResult)
async def compare_runtime_graph(req: CompareRequest):
    """Compare planned stack manifest intent against observed running ROS 2 nodes and topics."""
    try:
        return comparator.compare(
            planned_manifest=req.planned_manifest,
            observed_nodes=req.observed_nodes,
            observed_topics=req.observed_topics,
            observed_tfs=req.observed_tfs,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Graph comparison failed: {str(e)}")


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
