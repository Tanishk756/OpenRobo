import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from jsonschema import Draft202012Validator
from openrobo_compat import (
    CompatibilityEngine,
    CompatibilityResult,
    CompatibilityStatus,
    DependencyResolver,
    EnvironmentTarget,
    GraphEdgeData,
    OpenRoboGraph,
    ResolutionProposal,
    ResourceCandidate,
    StackValidationResponse,
)
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models.graph import GraphEdgeModel
from apps.api.models.resource import ResourceModel
from apps.api.models.stack import StackModel
from apps.api.schemas.stack import (
    StackCreate,
    StackImportRequest,
    StackRead,
    StackResolveRequest,
    StackTemplate,
    StackUpdate,
    StackValidateRequest,
)

router = APIRouter(prefix="/stacks", tags=["Stacks"])

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
STACK_SCHEMA_PATH = ROOT_DIR / "schemas" / "stack.schema.json"

TEMPLATES: List[StackTemplate] = [
    StackTemplate(
        id="mobile_robot_navigation",
        name="turtlebot3_nav2_jazzy",
        title="Mobile Robot Navigation",
        description="Standard autonomous mobile robot navigation with Nav2, SLAM Toolbox, TurtleBot3 base, and CycloneDDS middleware.",
        robot_domain="mobile_robotics",
        robot_type="differential_drive",
        target_os="ubuntu_24_04",
        target_arch="x86_64",
        target_ros_distro="jazzy",
        components=[
            {"resource_id": "nav2", "version": "1.3.0", "category": "navigation", "optional": False},
            {"resource_id": "slam_toolbox", "version": "2.7.4", "category": "mapping", "optional": False},
            {"resource_id": "turtlebot3", "version": "2.1.5", "category": "robot", "optional": False},
            {"resource_id": "cyclonedds", "version": "0.10.4", "category": "middleware", "optional": True},
        ],
        metadata={"tags": ["navigation", "slam", "turtlebot3", "jazzy"]},
    ),
    StackTemplate(
        id="rgbd_perception_slam",
        name="realsense_slam_jazzy",
        title="RGB-D Perception & Mapping",
        description="3D vision depth perception and 2D spatial mapping using Intel RealSense and SLAM Toolbox.",
        robot_domain="mobile_robotics",
        robot_type="wheeled_robot",
        target_os="ubuntu_24_04",
        target_arch="x86_64",
        target_ros_distro="jazzy",
        components=[
            {"resource_id": "realsense", "version": "4.55.1", "category": "sensors", "optional": False},
            {"resource_id": "slam_toolbox", "version": "2.7.4", "category": "mapping", "optional": False},
            {"resource_id": "robot_state_publisher", "version": "3.3.0", "category": "localization", "optional": False},
        ],
        metadata={"tags": ["perception", "realsense", "mapping"]},
    ),
    StackTemplate(
        id="manipulation_control",
        name="ros2_control_manipulation",
        title="Manipulation & Arm Control",
        description="Real-time hardware abstraction and actuator controller lifecycle for robotic manipulators.",
        robot_domain="manipulation",
        robot_type="robotic_arm",
        target_os="ubuntu_24_04",
        target_arch="x86_64",
        target_ros_distro="jazzy",
        components=[
            {"resource_id": "ros2_control", "version": "4.10.0", "category": "control", "optional": False},
            {"resource_id": "joint_state_broadcaster", "version": "4.10.0", "category": "control", "optional": False},
            {"resource_id": "robot_state_publisher", "version": "3.3.0", "category": "localization", "optional": False},
        ],
        metadata={"tags": ["manipulation", "control", "actuation"]},
    ),
    StackTemplate(
        id="simulation_development",
        name="gazebo_nav2_simulation",
        title="Simulation & Digital Twin",
        description="Full virtual simulation environment in Gazebo Harmonic with ROS 2 control and Nav2 navigation.",
        robot_domain="simulation",
        robot_type="virtual_amr",
        target_os="ubuntu_24_04",
        target_arch="x86_64",
        target_ros_distro="jazzy",
        components=[
            {"resource_id": "gazebo_ros2_control", "version": "1.2.0", "category": "simulation", "optional": False},
            {"resource_id": "ros2_control", "version": "4.10.0", "category": "control", "optional": False},
            {"resource_id": "nav2", "version": "1.3.0", "category": "navigation", "optional": False},
        ],
        metadata={"tags": ["simulation", "gazebo", "digital_twin"]},
    ),
]


async def build_engine_and_registry(db: AsyncSession) -> tuple[CompatibilityEngine, Dict[str, ResourceCandidate], OpenRoboGraph]:
    graph = OpenRoboGraph()

    # Load all edges
    edge_res = await db.execute(select(GraphEdgeModel))
    edges = edge_res.scalars().all()
    for e in edges:
        graph.add_edge(
            GraphEdgeData(
                subject_id=e.subject_id,
                predicate=e.predicate,
                object_id=e.object_id,
                properties=e.properties_json or None,
            )
        )

    # Load all resources into registry
    res_res = await db.execute(select(ResourceModel))
    resources = res_res.scalars().all()
    registry: Dict[str, ResourceCandidate] = {}
    for r in resources:
        meta = r.metadata_json or {}
        registry[r.id] = ResourceCandidate(
            id=r.id,
            name=r.name,
            version=getattr(r, "version", "1.0.0"),
            type=r.type,
            robotics_domains=r.robotics_domains or [],
            capabilities=r.capabilities or [],
            platforms=meta.get("platforms"),
            metadata_json=meta,
            evidence_level="vendor_tested" if meta.get("verified") else "inferred",
        )

    engine = CompatibilityEngine(graph=graph)
    return engine, registry, graph


def evaluate_stack_components(
    components: List[dict],
    target_os: Optional[str],
    target_arch: Optional[str],
    target_ros_distro: Optional[str],
    engine: CompatibilityEngine,
    registry: Dict[str, ResourceCandidate],
    graph: OpenRoboGraph,
    stack_id: Optional[str] = None,
) -> StackValidationResponse:
    target_env = EnvironmentTarget(
        ros_version=target_ros_distro,
        ros_distribution=target_ros_distro,
        os=target_os,
        cpu_architecture=target_arch,
    )

    candidate_list: List[ResourceCandidate] = []
    for c in components:
        rid = c.get("resource_id", "")
        if rid in registry:
            cand = registry[rid].model_copy()
            if c.get("version"):
                cand.version = c["version"]
            candidate_list.append(cand)
        else:
            candidate_list.append(
                ResourceCandidate(
                    id=rid,
                    name=rid.split("/")[-1],
                    version=c.get("version", "1.0.0"),
                    type=c.get("category", "ros_package"),
                    evidence_level="inferred",
                )
            )

    compat_result: CompatibilityResult = engine.evaluate_stack(candidate_list, environment=target_env)

    resolver = DependencyResolver(graph, registry)
    resolution_proposal: ResolutionProposal = resolver.resolve(candidate_list, environment=target_env)

    total_components = len(components)
    verified_compatible_count = 0
    conditional_count = 0
    incompatible_count = 0
    unknown_count = 0

    for cand in candidate_list:
        cand_res = engine.evaluate_stack([cand], environment=target_env)
        if cand_res.status == CompatibilityStatus.COMPATIBLE:
            verified_compatible_count += 1
        elif cand_res.status == CompatibilityStatus.CONDITIONAL:
            conditional_count += 1
        elif cand_res.status == CompatibilityStatus.INCOMPATIBLE:
            incompatible_count += 1
        else:
            unknown_count += 1

    cycles = graph.find_dependency_cycles()
    active_component_ids = {c.get("resource_id") for c in components}
    cycles_count = len([cyc for cyc in cycles if any(node in active_component_ids for node in cyc)])
    version_conflicts_count = len([c for c in resolution_proposal.conflicts if c.conflict_type == "VERSION_MISMATCH"])

    # Determine overall status
    overall_status = compat_result.status
    if resolution_proposal.missing_mandatory_count > 0 and overall_status == CompatibilityStatus.COMPATIBLE:
        overall_status = CompatibilityStatus.CONDITIONAL

    return StackValidationResponse(
        stack_id=stack_id,
        status=overall_status,
        total_components=total_components,
        verified_compatible_count=verified_compatible_count,
        conditional_count=conditional_count,
        incompatible_count=incompatible_count,
        unknown_count=unknown_count,
        missing_dependencies_count=resolution_proposal.missing_mandatory_count,
        version_conflicts_count=version_conflicts_count,
        cycles_count=cycles_count,
        compatibility_result=compat_result,
        resolution_proposal=resolution_proposal,
    )


@router.get("/templates", response_model=List[StackTemplate], summary="List Starter Stack Templates")
async def list_stack_templates():
    return TEMPLATES


@router.post("/validate", response_model=StackValidationResponse, summary="Validate Ad-hoc Stack Components")
async def validate_adhoc_stack(payload: StackValidateRequest, db: AsyncSession = Depends(get_db)):
    engine, registry, graph = await build_engine_and_registry(db)
    raw_components = [c.model_dump() for c in payload.components]
    return evaluate_stack_components(
        components=raw_components,
        target_os=payload.target_os,
        target_arch=payload.target_arch,
        target_ros_distro=payload.target_ros_distro,
        engine=engine,
        registry=registry,
        graph=graph,
    )


@router.post("/resolve", response_model=ResolutionProposal, summary="Resolve Ad-hoc Stack Dependencies")
async def resolve_adhoc_stack(payload: StackResolveRequest, db: AsyncSession = Depends(get_db)):
    _, registry, graph = await build_engine_and_registry(db)
    target_env = EnvironmentTarget(
        ros_version=payload.target_ros_distro,
        ros_distribution=payload.target_ros_distro,
        os=payload.target_os,
        cpu_architecture=payload.target_arch,
    )
    candidate_list = [
        registry.get(c.resource_id, ResourceCandidate(id=c.resource_id, name=c.resource_id.split("/")[-1], version=c.version))
        for c in payload.components
    ]
    resolver = DependencyResolver(graph, registry)
    return resolver.resolve(candidate_list, environment=target_env)


@router.post("/import", response_model=Dict, summary="Import and Validate Untrusted Stack Manifest")
async def import_stack_manifest(payload: StackImportRequest, db: AsyncSession = Depends(get_db)):
    manifest = payload.manifest

    # Validate against canonical schema
    if not STACK_SCHEMA_PATH.exists():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Stack schema definition file not found")

    with open(STACK_SCHEMA_PATH, "r", encoding="utf-8") as sf:
        schema = json.load(sf)

    validator = Draft202012Validator(schema)
    errors = [e.message for e in validator.iter_errors(manifest)]
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Invalid OpenRobo stack manifest format", "errors": errors},
        )

    engine, registry, graph = await build_engine_and_registry(db)

    components = manifest.get("components", [])
    target_plat = manifest.get("target_platform", {})
    target_os = target_plat.get("os")
    target_arch = target_plat.get("arch")
    target_ros_distro = target_plat.get("ros_distribution") or target_plat.get("ros_version")

    # Check unavailable resources
    unavailable_resources = [c.get("resource_id") for c in components if c.get("resource_id") not in registry]

    validation = evaluate_stack_components(
        components=components,
        target_os=target_os,
        target_arch=target_arch,
        target_ros_distro=target_ros_distro,
        engine=engine,
        registry=registry,
        graph=graph,
    )

    return {
        "manifest": manifest,
        "unavailable_resources": unavailable_resources,
        "validation": validation,
        "is_valid": len(errors) == 0,
    }


@router.get("", response_model=List[StackRead], summary="List Saved Stacks")
async def list_stacks(
    response: Response,
    q: Optional[str] = Query(None, description="Search term for stack name or description"),
    domain: Optional[str] = Query(None, description="Filter by robot domain"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(StackModel)
    if q and q.strip():
        term = q.strip().lower()
        stmt = stmt.where(
            or_(
                func.lower(StackModel.name).contains(term),
                func.lower(StackModel.description).contains(term),
            )
        )
    if domain and domain.strip():
        stmt = stmt.where(func.lower(StackModel.robot_domain) == domain.strip().lower())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.order_by(StackModel.updated_at.desc()).offset(offset).limit(limit)
    res = await db.execute(stmt)
    stacks = res.scalars().all()

    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Offset"] = str(offset)

    return [
        StackRead(
            id=s.id,
            name=s.name,
            version=s.version,
            description=s.description,
            robot_domain=s.robot_domain,
            robot_type=s.robot_type,
            target_os=s.target_os,
            target_arch=s.target_arch,
            target_ros_distro=s.target_ros_distro,
            components=s.components_json or [],
            metadata=s.metadata_json or {},
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in stacks
    ]


@router.post("", response_model=StackRead, status_code=status.HTTP_201_CREATED, summary="Create/Save New Stack")
async def create_stack(payload: StackCreate, db: AsyncSession = Depends(get_db)):
    stack_id = f"stack_{uuid.uuid4().hex[:12]}"
    raw_components = [c.model_dump() for c in payload.components]

    stack = StackModel(
        id=stack_id,
        name=payload.name,
        version=payload.version,
        description=payload.description,
        robot_domain=payload.robot_domain,
        robot_type=payload.robot_type,
        target_os=payload.target_os,
        target_arch=payload.target_arch,
        target_ros_distro=payload.target_ros_distro,
        components_json=raw_components,
        metadata_json=payload.metadata or {},
    )
    db.add(stack)
    await db.commit()
    await db.refresh(stack)

    return StackRead(
        id=stack.id,
        name=stack.name,
        version=stack.version,
        description=stack.description,
        robot_domain=stack.robot_domain,
        robot_type=stack.robot_type,
        target_os=stack.target_os,
        target_arch=stack.target_arch,
        target_ros_distro=stack.target_ros_distro,
        components=stack.components_json or [],
        metadata=stack.metadata_json or {},
        created_at=stack.created_at,
        updated_at=stack.updated_at,
    )


@router.get("/{stack_id}", response_model=StackRead, summary="Get Stack by ID")
async def get_stack(stack_id: str, db: AsyncSession = Depends(get_db)):
    stack = await db.get(StackModel, stack_id)
    if not stack:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Stack with ID '{stack_id}' not found")
    return StackRead(
        id=stack.id,
        name=stack.name,
        version=stack.version,
        description=stack.description,
        robot_domain=stack.robot_domain,
        robot_type=stack.robot_type,
        target_os=stack.target_os,
        target_arch=stack.target_arch,
        target_ros_distro=stack.target_ros_distro,
        components=stack.components_json or [],
        metadata=stack.metadata_json or {},
        created_at=stack.created_at,
        updated_at=stack.updated_at,
    )


@router.patch("/{stack_id}", response_model=StackRead, summary="Update Saved Stack")
async def update_stack(stack_id: str, payload: StackUpdate, db: AsyncSession = Depends(get_db)):
    stack = await db.get(StackModel, stack_id)
    if not stack:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Stack with ID '{stack_id}' not found")

    if payload.name is not None:
        stack.name = payload.name
    if payload.version is not None:
        stack.version = payload.version
    if payload.description is not None:
        stack.description = payload.description
    if payload.robot_domain is not None:
        stack.robot_domain = payload.robot_domain
    if payload.robot_type is not None:
        stack.robot_type = payload.robot_type
    if payload.target_os is not None:
        stack.target_os = payload.target_os
    if payload.target_arch is not None:
        stack.target_arch = payload.target_arch
    if payload.target_ros_distro is not None:
        stack.target_ros_distro = payload.target_ros_distro
    if payload.components is not None:
        stack.components_json = [c.model_dump() for c in payload.components]
    if payload.metadata is not None:
        stack.metadata_json = payload.metadata

    await db.commit()
    await db.refresh(stack)

    return StackRead(
        id=stack.id,
        name=stack.name,
        version=stack.version,
        description=stack.description,
        robot_domain=stack.robot_domain,
        robot_type=stack.robot_type,
        target_os=stack.target_os,
        target_arch=stack.target_arch,
        target_ros_distro=stack.target_ros_distro,
        components=stack.components_json or [],
        metadata=stack.metadata_json or {},
        created_at=stack.created_at,
        updated_at=stack.updated_at,
    )


@router.delete("/{stack_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Saved Stack")
async def delete_stack(stack_id: str, db: AsyncSession = Depends(get_db)):
    stack = await db.get(StackModel, stack_id)
    if not stack:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Stack with ID '{stack_id}' not found")
    await db.delete(stack)
    await db.commit()
    return None


@router.post("/{stack_id}/validate", response_model=StackValidationResponse, summary="Validate Saved Stack")
async def validate_saved_stack(stack_id: str, db: AsyncSession = Depends(get_db)):
    stack = await db.get(StackModel, stack_id)
    if not stack:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Stack with ID '{stack_id}' not found")

    engine, registry, graph = await build_engine_and_registry(db)
    return evaluate_stack_components(
        components=stack.components_json or [],
        target_os=stack.target_os,
        target_arch=stack.target_arch,
        target_ros_distro=stack.target_ros_distro,
        engine=engine,
        registry=registry,
        graph=graph,
        stack_id=stack.id,
    )


@router.post("/{stack_id}/resolve", response_model=ResolutionProposal, summary="Resolve Saved Stack Dependencies")
async def resolve_saved_stack(stack_id: str, db: AsyncSession = Depends(get_db)):
    stack = await db.get(StackModel, stack_id)
    if not stack:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Stack with ID '{stack_id}' not found")

    _, registry, graph = await build_engine_and_registry(db)
    target_env = EnvironmentTarget(
        ros_version=stack.target_ros_distro,
        ros_distribution=stack.target_ros_distro,
        os=stack.target_os,
        cpu_architecture=stack.target_arch,
    )
    raw_comps = stack.components_json or []
    candidate_list = []
    for c in raw_comps:
        rid = c.get("resource_id", "")
        cand = registry.get(rid, ResourceCandidate(id=rid, name=rid, version=c.get("version")))
        candidate_list.append(cand)
    resolver = DependencyResolver(graph, registry)
    return resolver.resolve(candidate_list, environment=target_env)


@router.get("/{stack_id}/manifest", response_model=Dict, summary="Export Stack as Canonical .openrobo.stack.json Manifest")
async def get_stack_manifest(stack_id: str, db: AsyncSession = Depends(get_db)):
    stack = await db.get(StackModel, stack_id)
    if not stack:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Stack with ID '{stack_id}' not found")

    manifest = {
        "$schema": "https://openrobo.org/schemas/v1/stack.schema.json",
        "name": stack.name,
        "version": stack.version,
        "description": stack.description or f"Robotics stack manifest for {stack.name}",
        "created_at": stack.created_at.isoformat() if stack.created_at else None,
        "updated_at": stack.updated_at.isoformat() if stack.updated_at else None,
        "robot": {
            "domain": stack.robot_domain,
            "type": stack.robot_type,
        },
        "target_platform": {
            "os": stack.target_os,
            "arch": stack.target_arch,
            "ros_distribution": stack.target_ros_distro,
            "ros_version": stack.target_ros_distro,
        },
        "components": stack.components_json or [],
        "metadata": stack.metadata_json or {},
    }

    return manifest
