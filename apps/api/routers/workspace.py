"""Workspace generation API router for OpenRobo (Milestone 5)."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from openrobo_workspace import WorkspaceGenerator, WorkspacePreviewResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models.resource import ResourceModel
from apps.api.models.stack import StackModel

router = APIRouter(prefix="", tags=["Workspace Generation"])


class WorkspaceRequest(BaseModel):
    stack_id: Optional[str] = Field(None, description="Saved stack ID in database")
    manifest: Optional[Dict[str, Any]] = Field(None, description="Direct OpenRobo stack manifest dict")
    allow_incompatible: bool = Field(False, description="Allow generation for conditional or non-strictly-compatible stacks")


async def resolve_manifest_and_metadata(
    req: WorkspaceRequest,
    db: AsyncSession,
) -> tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    manifest: Dict[str, Any] = {}
    if req.manifest:
        manifest = req.manifest
    elif req.stack_id:
        result = await db.execute(select(StackModel).where(StackModel.id == req.stack_id))
        stack_record = result.scalars().first()
        if not stack_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Stack '{req.stack_id}' not found.")

        resources_list = []
        for c in (stack_record.components_json or []):
            rid = c.get("resource_id") or c.get("id") if isinstance(c, dict) else str(c)
            if rid:
                resources_list.append({
                    "id": rid,
                    "name": c.get("name") or rid if isinstance(c, dict) else rid,
                    "version": c.get("version", "1.0.0") if isinstance(c, dict) else "1.0.0",
                })

        manifest = {
            "id": stack_record.id,
            "name": stack_record.name,
            "version": stack_record.version,
            "description": stack_record.description,
            "target": {
                "ros_distro": stack_record.target_ros_distro or "humble",
                "os": stack_record.target_os or "ubuntu-22.04",
                "architecture": stack_record.target_arch or "x86_64",
            },
            "resources": resources_list,
            "metadata": stack_record.metadata_json or {},
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either 'manifest' or 'stack_id' must be provided."
        )

    # Fetch registry metadata for all resources in manifest
    resources_list = manifest.get("resources", [])
    resource_ids = []
    for r in resources_list:
        if isinstance(r, str):
            resource_ids.append(r)
        elif isinstance(r, dict) and "id" in r:
            resource_ids.append(r["id"])

    registry_metadata: Dict[str, Dict[str, Any]] = {}
    if resource_ids:
        res_stmt = select(ResourceModel).where(ResourceModel.id.in_(resource_ids))
        res_results = await db.execute(res_stmt)
        for r_obj in res_results.scalars().all():
            registry_metadata[r_obj.id] = {
                "name": r_obj.name,
                "version": r_obj.version,
                "category": r_obj.category,
                "repository_url": r_obj.repository_url,
                "license": r_obj.license,
                "dependencies": r_obj.dependencies or [],
            }

    return manifest, registry_metadata


@router.post("/workspace/preview", response_model=WorkspacePreviewResponse)
async def preview_workspace(
    req: WorkspaceRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate in-memory preview of workspace files and directory structure."""
    manifest, registry_metadata = await resolve_manifest_and_metadata(req, db)
    try:
        gen = WorkspaceGenerator(
            stack_manifest=manifest,
            registry_metadata=registry_metadata,
            allow_incompatible=req.allow_incompatible,
        )
        return gen.preview()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Workspace preview failed: {str(e)}")


@router.post("/workspace/generate", response_model=WorkspacePreviewResponse)
async def generate_workspace_meta(
    req: WorkspaceRequest,
    db: AsyncSession = Depends(get_db),
):
    """Synthesize workspace files and return preview metadata."""
    manifest, registry_metadata = await resolve_manifest_and_metadata(req, db)
    try:
        gen = WorkspaceGenerator(
            stack_manifest=manifest,
            registry_metadata=registry_metadata,
            allow_incompatible=req.allow_incompatible,
        )
        return gen.preview()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Workspace generation failed: {str(e)}")


@router.post("/workspace/download")
async def download_workspace_from_manifest(
    req: WorkspaceRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate and stream downloadable ZIP bundle for a direct manifest."""
    manifest, registry_metadata = await resolve_manifest_and_metadata(req, db)
    try:
        gen = WorkspaceGenerator(
            stack_manifest=manifest,
            registry_metadata=registry_metadata,
            allow_incompatible=req.allow_incompatible,
        )
        preview = gen.preview()
        zip_bytes = gen.export_archive()
        filename = f"{preview.workspace_name}.zip"

        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(zip_bytes)),
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Download failed: {str(e)}")


@router.get("/stacks/{stack_id}/workspace/download")
async def download_stack_workspace(
    stack_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Generate and stream downloadable ZIP bundle for a stored stack."""
    req = WorkspaceRequest(stack_id=stack_id)
    return await download_workspace_from_manifest(req, db)
