from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SearchFacetDistribution(BaseModel):
    types: Dict[str, int] = Field(default_factory=dict)
    domains: Dict[str, int] = Field(default_factory=dict)
    capabilities: Dict[str, int] = Field(default_factory=dict)
    licenses: Dict[str, int] = Field(default_factory=dict)
    ros_versions: Dict[str, int] = Field(default_factory=dict)


class SearchResultHit(BaseModel):
    id: str
    name: str
    type: str
    version: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    spdx_license_id: str
    repo_url: Optional[str] = None
    robotics_domains: List[str] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    platforms: Dict[str, Any] = Field(default_factory=dict)
    evidence_level: str = "unknown"
    score: float = Field(default=1.0, description="Relevance ranking score")
    highlight: Optional[str] = Field(default=None, description="Highlighted text snippet")


class SearchRequest(BaseModel):
    q: Optional[str] = Field(default=None, description="Search query string")
    type: Optional[str] = Field(default=None, description="Filter by resource type")
    domain: Optional[str] = Field(default=None, description="Filter by robotics domain")
    capability: Optional[str] = Field(default=None, description="Filter by robotics capability")
    ecosystem: Optional[str] = Field(default=None, description="Filter by ecosystem / platform")
    license: Optional[str] = Field(default=None, description="Filter by SPDX license")
    ros_version: Optional[str] = Field(default=None, description="Filter by ROS version")
    os: Optional[str] = Field(default=None, description="Filter by operating system")
    limit: int = Field(default=20, ge=1, le=1000, description="Page limit")
    offset: int = Field(default=0, ge=0, description="Pagination offset")
    fuzzy: bool = Field(default=True, description="Enable fuzzy/trigram matching for typo tolerance")


class SearchResponse(BaseModel):
    query: Optional[str] = None
    total: int
    limit: int
    offset: int
    items: List[SearchResultHit] = Field(default_factory=list)
    facets: SearchFacetDistribution = Field(default_factory=SearchFacetDistribution)
