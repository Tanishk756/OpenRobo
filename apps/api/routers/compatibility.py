from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from openrobo_compat import (
    CompatibilityEngine,
    CompatibilityMatrixResponse,
    CompatibilityResult,
    EnvironmentTarget,
    EvaluationRequest,
    GraphEdgeData,
    MatrixRequest,
    OpenRoboGraph,
    ResourceCandidate,
    ResourceCompatibilityProfile,
)
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models.graph import GraphEdgeModel
from apps.api.models.resource import ResourceModel

router = APIRouter(prefix="/compatibility", tags=["Compatibility Engine"])


async def build_compatibility_engine(db: AsyncSession, resource_ids: Optional[List[str]] = None) -> CompatibilityEngine:
    graph = OpenRoboGraph()

    # Load edges
    if resource_ids:
        edge_stmt = select(GraphEdgeModel).where(
            or_(
                GraphEdgeModel.subject_id.in_(resource_ids),
                GraphEdgeModel.object_id.in_(resource_ids),
            )
        )
    else:
        edge_stmt = select(GraphEdgeModel)

    edge_res = await db.execute(edge_stmt)
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

    return CompatibilityEngine(graph=graph)


async def get_candidate_map(db: AsyncSession, resource_ids: List[str]) -> Dict[str, ResourceCandidate]:
    stmt = select(ResourceModel).where(ResourceModel.id.in_(resource_ids))
    result = await db.execute(stmt)
    resources = result.scalars().all()

    cand_map: Dict[str, ResourceCandidate] = {}
    for r in resources:
        meta = r.metadata_json or {}
        cand_map[r.id] = ResourceCandidate(
            id=r.id,
            name=r.name,
            version=r.version,
            type=r.type,
            robotics_domains=r.robotics_domains or [],
            capabilities=r.capabilities or [],
            platforms=meta.get("platforms"),
            metadata_json=meta,
            evidence_level="vendor_tested" if meta.get("verified") else "inferred",
        )

    # For any requested ID not in DB, create inferred candidate placeholder
    for rid in resource_ids:
        if rid not in cand_map:
            cand_map[rid] = ResourceCandidate(
                id=rid,
                name=rid.split("/")[-1],
                version="1.0.0",
                type="ros_package",
                evidence_level="inferred",
            )

    return cand_map


@router.post("/evaluate", response_model=CompatibilityResult, summary="Evaluate Stack Compatibility")
async def evaluate_compatibility(payload: EvaluationRequest, db: AsyncSession = Depends(get_db)):
    if not payload.resource_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="resource_ids list cannot be empty",
        )

    cand_map = await get_candidate_map(db, payload.resource_ids)
    candidates = [cand_map[rid] for rid in payload.resource_ids if rid in cand_map]

    engine = await build_compatibility_engine(db, payload.resource_ids)
    return engine.evaluate_stack(candidates, environment=payload.environment)


@router.get("/matrix", response_model=CompatibilityMatrixResponse, summary="Evaluate Pairwise Compatibility Matrix (Query)")
async def get_compatibility_matrix(
    ids: str = Query(..., description="Comma-separated list of resource IDs"),
    ros_version: Optional[str] = Query(None, description="Target ROS distribution"),
    os: Optional[str] = Query(None, description="Target OS"),
    cpu_architecture: Optional[str] = Query(None, description="Target CPU architecture"),
    db: AsyncSession = Depends(get_db),
):
    resource_ids = [rid.strip() for rid in ids.split(",") if rid.strip()]
    if len(resource_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least 2 resource IDs are required to compute a compatibility matrix",
        )

    env = None
    if ros_version or os or cpu_architecture:
        env = EnvironmentTarget(
            ros_version=ros_version,
            os=os,
            cpu_architecture=cpu_architecture,
        )

    cand_map = await get_candidate_map(db, resource_ids)
    candidates = [cand_map[rid] for rid in resource_ids if rid in cand_map]

    engine = await build_compatibility_engine(db, resource_ids)
    return engine.evaluate_matrix(candidates, environment=env)


@router.post("/matrix", response_model=CompatibilityMatrixResponse, summary="Evaluate Pairwise Compatibility Matrix (Body)")
async def post_compatibility_matrix(payload: MatrixRequest, db: AsyncSession = Depends(get_db)):
    if len(payload.resource_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least 2 resource IDs are required to compute a compatibility matrix",
        )

    cand_map = await get_candidate_map(db, payload.resource_ids)
    candidates = [cand_map[rid] for rid in payload.resource_ids if rid in cand_map]

    engine = await build_compatibility_engine(db, payload.resource_ids)
    return engine.evaluate_matrix(candidates, environment=payload.environment)


@router.get("/resource/{resource_id:path}", response_model=ResourceCompatibilityProfile, summary="Get Resource Compatibility Profile")
async def get_resource_compatibility_profile(resource_id: str, db: AsyncSession = Depends(get_db)):
    resource = await db.get(ResourceModel, resource_id)
    meta = resource.metadata_json or {} if resource else {}

    candidate = ResourceCandidate(
        id=resource.id if resource else resource_id,
        name=resource.name if resource else resource_id.split("/")[-1],
        version=resource.version if resource else "1.0.0",
        type=resource.type if resource else "ros_package",
        robotics_domains=resource.robotics_domains or [] if resource else [],
        capabilities=resource.capabilities or [] if resource else [],
        platforms=meta.get("platforms"),
        metadata_json=meta,
        evidence_level="vendor_tested" if meta.get("verified") else "inferred",
    )

    engine = await build_compatibility_engine(db, [resource_id])
    return engine.get_resource_compatibility_profile(candidate)
