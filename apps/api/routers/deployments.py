"""Deployment orchestration, approval gates, and execution status endpoints."""

import json
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from openrobo_release.deployment_protocol import (
    DeploymentState,
    ReleaseSnapshot,
    RolloutStrategy,
    TargetFilter,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models.deployment import (
    DeploymentEventModel,
    DeploymentModel,
    DeviceDeploymentModel,
)
from apps.api.schemas.deployment import (
    DeploymentApprovalRequest,
    DeploymentCreate,
    DeploymentEventResponse,
    DeploymentResponse,
    DeviceDeploymentResponse,
)
from apps.api.services.deployment_service import DeploymentService
from apps.api.services.fleet_security import verify_admin_authorization

logger = logging.getLogger("openrobo.deployments.router")

router = APIRouter(prefix="/api/v1/deployments", tags=["Deployment Orchestration"])


def _format_deployment_response(dep_data: Dict[str, Any]) -> DeploymentResponse:
    deployment: DeploymentModel = dep_data["deployment"]
    snapshot = ReleaseSnapshot.model_validate_json(deployment.release_snapshot_json)
    strategy = RolloutStrategy.model_validate_json(deployment.rollout_strategy)
    target_filter = TargetFilter.model_validate_json(deployment.target_filter)

    return DeploymentResponse(
        id=deployment.id,
        release_id=deployment.release_id,
        release_snapshot=snapshot,
        rollout_strategy=strategy,
        target_filter=target_filter,
        status=DeploymentState(deployment.status),
        current_stage=deployment.current_stage,
        total_stages=deployment.total_stages,
        generation=deployment.generation,
        version=deployment.version,
        idempotency_key=deployment.idempotency_key,
        created_by=deployment.created_by,
        created_at=deployment.created_at,
        updated_at=deployment.updated_at,
        cancelled_at=deployment.cancelled_at,
        completed_at=deployment.completed_at,
        stages=dep_data.get("stages"),
    )


@router.post(
    "",
    response_model=DeploymentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_admin_authorization)],
)
async def create_deployment(
    req: DeploymentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Create a new deployment orchestration record.
    try:
        deployment = await DeploymentService.create_deployment(
            session=db,
            req=req,
            created_by="configured-admin",
        )
        await db.commit()
        summary = await DeploymentService.get_deployment_summary(db, deployment.id)
        if not summary:
            raise HTTPException(status_code=500, detail="Failed to load created deployment summary")
        return _format_deployment_response(summary)
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to create deployment")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get(
    "",
    response_model=List[DeploymentResponse],
)
async def list_deployments(
    db: AsyncSession = Depends(get_db),
):
    # List all deployment records.
    stmt = select(DeploymentModel).order_by(DeploymentModel.created_at.desc())
    res = await db.execute(stmt)
    deployments = list(res.scalars().all())

    results: List[DeploymentResponse] = []
    for dep in deployments:
        summary = await DeploymentService.get_deployment_summary(db, dep.id)
        if summary:
            results.append(_format_deployment_response(summary))
    return results


@router.get(
    "/{deployment_id}",
    response_model=DeploymentResponse,
)
async def get_deployment(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
):
    # Get details and stage summaries for a deployment.
    summary = await DeploymentService.get_deployment_summary(db, deployment_id)
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deployment '{deployment_id}' not found")
    return _format_deployment_response(summary)


@router.post(
    "/{deployment_id}/approve",
    response_model=DeploymentResponse,
    dependencies=[Depends(verify_admin_authorization)],
)
async def approve_stage_progression(
    deployment_id: str,
    req: DeploymentApprovalRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Optimistic concurrency operator approval gate.
    try:
        deployment = await DeploymentService.approve_stage_progression(
            session=db,
            deployment_id=deployment_id,
            req=req,
            approved_by="configured-admin",
        )
        await db.commit()
        summary = await DeploymentService.get_deployment_summary(db, deployment.id)
        if not summary:
            raise HTTPException(status_code=500, detail="Failed to load deployment summary after approval")
        return _format_deployment_response(summary)
    except ValueError as e:
        await db.rollback()
        # Distinguish optimistic concurrency conflict
        if "Optimistic conflict" in str(e) or "mismatch" in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to approve deployment progression")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.post(
    "/{deployment_id}/cancel",
    response_model=DeploymentResponse,
    dependencies=[Depends(verify_admin_authorization)],
)
async def cancel_deployment(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
):
    # Cancel an ongoing deployment.
    stmt = select(DeploymentModel).where(DeploymentModel.id == deployment_id).with_for_update()
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deployment '{deployment_id}' not found")

    curr_state = DeploymentState(deployment.status)
    if curr_state in (DeploymentState.COMPLETED, DeploymentState.CANCELLED):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Deployment is already {curr_state.value}")

    deployment.status = DeploymentState.CANCELLED.value
    deployment.version += 1
    await DeploymentService.cancel_remaining_devices(db, deployment_id, deployment.generation)
    await db.commit()

    summary = await DeploymentService.get_deployment_summary(db, deployment_id)
    return _format_deployment_response(summary)


@router.get(
    "/{deployment_id}/devices",
    response_model=List[DeviceDeploymentResponse],
)
async def list_deployment_devices(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
):
    # List device deployment statuses for a deployment.
    stmt = select(DeviceDeploymentModel).where(DeviceDeploymentModel.deployment_id == deployment_id)
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.get(
    "/{deployment_id}/events",
    response_model=List[DeploymentEventResponse],
)
async def list_deployment_events(
    deployment_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    # List paginated audit events for a deployment.
    stmt = (
        select(DeploymentEventModel)
        .where(DeploymentEventModel.deployment_id == deployment_id)
        .order_by(DeploymentEventModel.timestamp.desc(), DeploymentEventModel.id.desc())
        .limit(limit)
        .offset(offset)
    )
    res = await db.execute(stmt)
    events = list(res.scalars().all())

    results: List[DeploymentEventResponse] = []
    for ev in events:
        details_dict = {}
        try:
            details_dict = json.loads(ev.details)
        except Exception:
            pass
        results.append(
            DeploymentEventResponse(
                id=ev.id,
                deployment_id=ev.deployment_id,
                device_id=ev.device_id,
                event_type=ev.event_type,
                details=details_dict,
                timestamp=ev.timestamp,
            )
        )
    return results
