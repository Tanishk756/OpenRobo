from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def utc_now():
    return datetime.now(timezone.utc)


class ProvenanceClassification(str, Enum):
    UPSTREAM_DATA = "UPSTREAM_DATA"
    OPENROBO_DERIVED_DATA = "OPENROBO_DERIVED_DATA"
    COMMUNITY_DATA = "COMMUNITY_DATA"
    AUTOMATICALLY_INFERRED_DATA = "AUTOMATICALLY_INFERRED_DATA"


class EvidenceLevel(str, Enum):
    UPSTREAM_DECLARED = "upstream_declared"
    AUTOMATICALLY_DETECTED = "automatically_detected"
    CI_VERIFIED = "ci_verified"
    INTEGRATION_TESTED = "integration_tested"
    COMMUNITY_REPORTED = "community_reported"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class IngestionAction(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    FAILED = "failed"


class PackageXmlMetadata(BaseModel):
    name: str
    version: str = "0.1.0"
    description: Optional[str] = None
    maintainers: List[str] = Field(default_factory=list)
    license: Optional[str] = None
    build_depends: List[str] = Field(default_factory=list)
    exec_depends: List[str] = Field(default_factory=list)
    test_depends: List[str] = Field(default_factory=list)
    buildtool_depends: List[str] = Field(default_factory=list)
    group_depends: List[str] = Field(default_factory=list)
    export_tags: List[str] = Field(default_factory=list)
    format_version: int = 3
    rel_path: str = "package.xml"


class RepoInspectionEvidence(BaseModel):
    owner: str
    repo: str
    default_branch: str = "main"
    commit_sha: Optional[str] = None
    description: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    spdx_license_id: Optional[str] = None
    license_url: Optional[str] = None
    primary_language: Optional[str] = None
    homepage: Optional[str] = None
    has_package_xml: bool = False
    packages: List[PackageXmlMetadata] = Field(default_factory=list)
    build_systems: List[str] = Field(default_factory=list)
    robotics_markers: List[str] = Field(default_factory=list)
    inspected_files: List[str] = Field(default_factory=list)


class IngestionResourceSummary(BaseModel):
    id: str
    name: str
    version: str
    type: str
    action: IngestionAction
    validation_status: str
    provenance: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)


class GithubIngestionRequest(BaseModel):
    repository_url: str = Field(
        ...,
        description="Public GitHub repository URL (e.g. https://github.com/ros-navigation/navigation2)",
        examples=["https://github.com/ros-navigation/navigation2"],
    )
    force_refresh: bool = Field(default=False, description="Force update even if revision matches")


class GithubIngestionResponse(BaseModel):
    repository: str
    revision: Optional[str] = None
    resources_discovered: int
    resources_created: int
    resources_updated: int
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    resources: List[IngestionResourceSummary] = Field(default_factory=list)
