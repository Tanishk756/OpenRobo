from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.services.search import (
    SearchFacetDistribution,
    SearchRequest,
    SearchResponse,
    SearchService,
)

router = APIRouter(prefix="/search", tags=["Search"])
search_service = SearchService()


@router.get(
    "",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Ranked Full-Text & Fuzzy Robotics Search",
    description=(
        "Searches the OpenRobo registry using weighted full-text and fuzzy "
        "trigram relevance matching with multi-taxonomy faceting."
    ),
)
async def search_resources(
    q: Optional[str] = Query(None, description="Search query string"),
    type: Optional[str] = Query(None, description="Filter by resource type"),
    domain: Optional[str] = Query(None, description="Filter by robotics domain"),
    capability: Optional[str] = Query(None, description="Filter by capability"),
    ecosystem: Optional[str] = Query(None, description="Filter by ecosystem / platform"),
    license: Optional[str] = Query(None, description="Filter by SPDX license"),
    ros_version: Optional[str] = Query(None, description="Filter by ROS version"),
    os: Optional[str] = Query(None, description="Filter by operating system"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    fuzzy: bool = Query(True, description="Enable fuzzy/trigram matching for typo tolerance"),
    db: AsyncSession = Depends(get_db),
):
    request = SearchRequest(
        q=q,
        type=type,
        domain=domain,
        capability=capability,
        ecosystem=ecosystem,
        license=license,
        ros_version=ros_version,
        os=os,
        limit=limit,
        offset=offset,
        fuzzy=fuzzy,
    )
    return await search_service.search(db, request)


@router.get(
    "/facets",
    response_model=SearchFacetDistribution,
    status_code=status.HTTP_200_OK,
    summary="Aggregate Search Taxonomy Facets",
    description=(
        "Computes global or query-specific category facet counts across "
        "types, domains, capabilities, licenses, and ROS versions."
    ),
)
async def get_search_facets(
    q: Optional[str] = Query(None, description="Optional search query to calculate scoped facets"),
    db: AsyncSession = Depends(get_db),
):
    return await search_service.get_facets(db, q)
