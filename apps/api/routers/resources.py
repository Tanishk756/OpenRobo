from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from openrobo_schemas import validate_resource_manifest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models.resource import ResourceModel
from apps.api.schemas.resource import ResourceCreate, ResourceRead

router = APIRouter(prefix="/resources", tags=["Resources"])

@router.get("", response_model=List[ResourceRead], summary="List Registered Resources")
async def list_resources(limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db)):
    stmt = select(ResourceModel).offset(offset).limit(limit)
    result = await db.execute(stmt)
    resources = result.scalars().all()
    return resources

@router.get("/{resource_id:path}", response_model=ResourceRead, summary="Get Resource by ID")
async def get_resource(resource_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(ResourceModel).where(ResourceModel.id == resource_id)
    result = await db.execute(stmt)
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resource with ID '{resource_id}' not found."
        )
    return resource

@router.post("", response_model=ResourceRead, status_code=status.HTTP_201_CREATED, summary="Create/Submit Resource Manifest")
async def create_resource(payload: ResourceCreate, db: AsyncSession = Depends(get_db)):
    # Validate against JSON Schema
    valid, errors = validate_resource_manifest(payload.model_dump(exclude_none=True))
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Resource manifest schema validation failed", "errors": errors}
        )

    # Check existing
    existing = await db.get(ResourceModel, payload.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Resource with ID '{payload.id}' already exists."
        )

    resource = ResourceModel(
        id=payload.id,
        name=payload.name,
        type=payload.type,
        summary=payload.summary,
        description=payload.description,
        spdx_license_id=payload.spdx_license_id,
        repo_url=payload.repo_url,
        evidence_level=payload.evidence_level
    )
    db.add(resource)
    await db.commit()
    await db.refresh(resource)
    return resource
