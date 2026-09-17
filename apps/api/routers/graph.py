from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from openrobo_schemas import validate_graph_edge
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models.graph import GraphEdgeModel, GraphNodeModel
from apps.api.schemas.graph import GraphEdgeCreate, GraphEdgeRead

router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])


@router.get("/edges", response_model=List[GraphEdgeRead], summary="List Knowledge Graph Edges")
async def list_graph_edges(
    subject_id: Optional[str] = Query(None, description="Filter by subject node ID"),
    predicate: Optional[str] = Query(None, description="Filter by relationship predicate"),
    object_id: Optional[str] = Query(None, description="Filter by object node ID"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(GraphEdgeModel)
    if subject_id:
        stmt = stmt.where(GraphEdgeModel.subject_id == subject_id)
    if predicate:
        stmt = stmt.where(GraphEdgeModel.predicate == predicate)
    if object_id:
        stmt = stmt.where(GraphEdgeModel.object_id == object_id)

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/edges", response_model=GraphEdgeRead, status_code=status.HTTP_201_CREATED, summary="Add Knowledge Graph Edge")
async def create_graph_edge(payload: GraphEdgeCreate, db: AsyncSession = Depends(get_db)):
    data = payload.model_dump(exclude_none=True)
    # Ensure properties is present if properties_json was used
    valid, errors = validate_graph_edge(data)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Graph edge schema validation failed", "errors": errors},
        )

    # Auto-ensure graph nodes exist for FK constraints
    subject_node = await db.get(GraphNodeModel, payload.subject_id)
    if not subject_node:
        db.add(GraphNodeModel(id=payload.subject_id, node_type="resource"))

    object_node = await db.get(GraphNodeModel, payload.object_id)
    if not object_node:
        db.add(GraphNodeModel(id=payload.object_id, node_type="resource"))

    await db.flush()

    edge = GraphEdgeModel(
        subject_id=payload.subject_id,
        predicate=payload.predicate,
        object_id=payload.object_id,
        properties_json=payload.properties,
    )
    db.add(edge)
    await db.commit()
    await db.refresh(edge)
    return edge
