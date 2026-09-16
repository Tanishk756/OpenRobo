from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.database import get_db
from apps.api.services.ingestion import (
    GitHubAPIError,
    GithubIngestionRequest,
    GithubIngestionResponse,
    IngestionSecurityError,
    IngestionService,
)

router = APIRouter(prefix="/ingestion", tags=["Ingestion"])


@router.post(
    "/github",
    response_model=GithubIngestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest a public GitHub robotics repository",
    description=(
        "Inspects a public GitHub repository, extracts robotics manifests (package.xml, CMake, URDF), "
        "validates against canonical schemas, and records resources in the OpenRobo registry."
    )
)
async def ingest_github_repository(
    request: GithubIngestionRequest,
    db: AsyncSession = Depends(get_db)
):
    service = IngestionService(github_token=getattr(settings, "github_token", None))
    try:
        result = await service.ingest_github_repository(
            db=db,
            repository_url=request.repository_url,
            force_refresh=request.force_refresh
        )
        return result
    except IngestionSecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except GitHubAPIError as e:
        if e.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        elif e.status_code in (403, 429):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(e)
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during ingestion: {e}"
        )
