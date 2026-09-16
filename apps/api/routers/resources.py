from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from openrobo_schemas import validate_resource_manifest
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models.resource import ResourceModel, ResourceVersionModel
from apps.api.schemas.resource import ResourceCreate, ResourceRead

router = APIRouter(prefix="/resources", tags=["Resources"])


@router.get("", response_model=List[ResourceRead], summary="List and Search Registered Resources")
async def list_resources(
    response: Response,
    q: Optional[str] = Query(None, description="Keyword search across ID, name, summary, and description"),
    kind: Optional[str] = Query(None, alias="type", description="Filter by canonical resource type"),
    domain: Optional[str] = Query(None, description="Filter by robotics domain"),
    capability: Optional[str] = Query(None, description="Filter by capability"),
    ecosystem: Optional[str] = Query(None, description="Filter by ecosystem/platform"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results (1-100)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ResourceModel)

    if q and q.strip():
        term = q.strip().lower()
        stmt = stmt.where(
            or_(
                func.lower(ResourceModel.id).contains(term),
                func.lower(ResourceModel.name).contains(term),
                func.lower(ResourceModel.summary).contains(term),
                func.lower(ResourceModel.description).contains(term),
            )
        )

    if kind and kind.strip():
        stmt = stmt.where(func.lower(ResourceModel.type) == kind.strip().lower())

    if domain and domain.strip():
        dom_term = domain.strip().lower()
        stmt = stmt.where(func.lower(cast(ResourceModel.robotics_domains, String)).contains(dom_term))

    if capability and capability.strip():
        cap_term = capability.strip().lower()
        stmt = stmt.where(func.lower(cast(ResourceModel.capabilities, String)).contains(cap_term))

    if ecosystem and ecosystem.strip():
        eco_term = ecosystem.strip().lower()
        stmt = stmt.where(
            or_(
                func.lower(cast(ResourceModel.platforms, String)).contains(eco_term),
                func.lower(ResourceModel.spdx_license_id).contains(eco_term),
                func.lower(ResourceModel.type).contains(eco_term),
            )
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.order_by(ResourceModel.name.asc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    resources = result.scalars().all()

    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Offset"] = str(offset)

    return resources


@router.get("/{resource_id:path}", response_model=ResourceRead, summary="Get Resource by ID")
async def get_resource(resource_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(ResourceModel).where(ResourceModel.id == resource_id)
    result = await db.execute(stmt)
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Resource with ID '{resource_id}' not found.")
    return resource


@router.post("", response_model=ResourceRead, status_code=status.HTTP_201_CREATED, summary="Create Resource Manifest")
async def create_resource(payload: ResourceCreate, db: AsyncSession = Depends(get_db)):
    raw_dict = payload.model_dump(exclude_none=True)

    if "source" not in raw_dict or not raw_dict["source"].get("repo_url"):
        raw_dict["source"] = {"repo_url": payload.repo_url or f"https://github.com/{payload.id}"}
    if "license" not in raw_dict:
        raw_dict["license"] = {"spdx_id": payload.spdx_license_id or "NOASSERTION"}

    valid, errors = validate_resource_manifest(raw_dict)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Resource manifest schema validation failed", "errors": errors},
        )

    existing = await db.get(ResourceModel, payload.id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Resource with ID '{payload.id}' already exists.")

    repo_url = payload.repo_url or (payload.source.repo_url if payload.source else None)
    spdx_license = (
        payload.spdx_license_id
        if payload.spdx_license_id != "NOASSERTION"
        else (payload.license.spdx_id if payload.license else "NOASSERTION")
    )
    evidence_level = (
        payload.evidence_level if payload.evidence_level != "unknown" else (payload.evidence.level if payload.evidence else "unknown")
    )

    resource = ResourceModel(
        id=payload.id,
        name=payload.name,
        type=payload.type,
        summary=payload.summary,
        description=payload.description,
        spdx_license_id=spdx_license,
        repo_url=repo_url,
        evidence_level=evidence_level,
        robotics_domains=payload.robotics_domains or [],
        capabilities=payload.capabilities or [],
        platforms=payload.platforms.model_dump() if payload.platforms else {},
        metadata_json={
            "source": payload.source.model_dump() if payload.source else {},
            "license": payload.license.model_dump() if payload.license else {},
            "evidence": payload.evidence.model_dump() if payload.evidence else {},
        },
    )
    db.add(resource)

    version_id = payload.id + "@" + payload.version
    version_entry = ResourceVersionModel(id=version_id, resource_id=payload.id, version_string=payload.version, manifest_json=raw_dict)
    db.add(version_entry)

    await db.commit()
    await db.refresh(resource)
    return resource
