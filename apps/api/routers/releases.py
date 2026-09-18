"""Release catalog and artifact source management endpoints."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models.deployment import ArtifactSourceModel, ReleaseArtifactModel
from apps.api.schemas.deployment import (
    ArtifactSourceCreate,
    ArtifactSourceResponse,
    ReleaseArtifactCreate,
    ReleaseArtifactResponse,
)
from apps.api.services.deployment_service import DeploymentService
from apps.api.services.fleet_security import verify_admin_authorization

logger = logging.getLogger("openrobo.releases.router")

router = APIRouter(prefix="/api/v1/releases", tags=["Release Catalog"])


@router.post(
    "/sources",
    response_model=ArtifactSourceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_admin_authorization)],
)
async def register_artifact_source(
    req: ArtifactSourceCreate,
    db: AsyncSession = Depends(get_db),
):
    # Register or update a trusted artifact distribution endpoint.
    try:
        source = await DeploymentService.register_artifact_source(db, req)
        await db.commit()
        await db.refresh(source)
        return source
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/sources",
    response_model=List[ArtifactSourceResponse],
    dependencies=[Depends(verify_admin_authorization)],
)
async def list_artifact_sources(
    db: AsyncSession = Depends(get_db),
):
    # List configured artifact sources.
    stmt = select(ArtifactSourceModel).order_by(ArtifactSourceModel.created_at.desc())
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.post(
    "",
    response_model=ReleaseArtifactResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_admin_authorization)],
)
async def register_release(
    req: ReleaseArtifactCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Register release metadata in authoritative catalog.
    try:
        release = await DeploymentService.register_release(
            session=db,
            req=req,
            registered_by="configured-admin",
        )
        await db.commit()
        await db.refresh(release)
        return release
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to register release")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get(
    "",
    response_model=List[ReleaseArtifactResponse],
)
async def list_releases(
    db: AsyncSession = Depends(get_db),
):
    # List all registered releases.
    stmt = select(ReleaseArtifactModel).order_by(ReleaseArtifactModel.created_at.desc())
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.get(
    "/{release_id}",
    response_model=ReleaseArtifactResponse,
)
async def get_release(
    release_id: str,
    db: AsyncSession = Depends(get_db),
):
    # Get metadata for a specific release.
    stmt = select(ReleaseArtifactModel).where(ReleaseArtifactModel.release_id == release_id)
    res = await db.execute(stmt)
    release = res.scalar_one_or_none()
    if not release:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Release '{release_id}' not found")
    return release
