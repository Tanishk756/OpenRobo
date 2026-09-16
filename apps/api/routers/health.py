from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.database import get_db
from apps.api.schemas.health import HealthResponse

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=HealthResponse, summary="System Health Status")
async def get_health(db: AsyncSession = Depends(get_db)):
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded", version="0.1.0", environment=settings.environment, database=db_status
    )


@router.get("/readiness", summary="Readiness Probe Endpoint")
async def get_readiness():
    return {"ready": True}
