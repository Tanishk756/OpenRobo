from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SourceDetail(BaseModel):
    repo_url: Optional[str] = Field(default=None, json_schema_extra={'example': 'https://github.com/ros-controls/ros2_control'})
    vcs_type: Optional[str] = Field(default='git')
    branch: Optional[str] = None
    commit: Optional[str] = None

class LicenseDetail(BaseModel):
    spdx_id: str = Field(default='Apache-2.0', json_schema_extra={'example': 'Apache-2.0'})
    license_url: Optional[str] = None

class PlatformDetail(BaseModel):
    operating_systems: Optional[List[str]] = Field(default_factory=list)
    cpu_architectures: Optional[List[str]] = Field(default_factory=list)
    ros_versions: Optional[List[str]] = Field(default_factory=list)

class EvidenceDetail(BaseModel):
    level: str = Field(default='unknown', json_schema_extra={'example': 'ci_verified'})
    notes: Optional[str] = None

class ResourceBase(BaseModel):
    id: str = Field(..., json_schema_extra={'example': 'ros-controls/ros2_control'})
    name: str = Field(..., json_schema_extra={'example': 'ros2_control'})
    type: str = Field(..., json_schema_extra={'example': 'ros_package'})
    summary: Optional[str] = None
    description: Optional[str] = None
    spdx_license_id: str = Field(default='NOASSERTION', json_schema_extra={'example': 'Apache-2.0'})
    repo_url: Optional[str] = None
    evidence_level: str = Field(default='unknown', json_schema_extra={'example': 'ci_verified'})
    robotics_domains: Optional[List[str]] = Field(default_factory=list)
    capabilities: Optional[List[str]] = Field(default_factory=list)
    platforms: Optional[PlatformDetail] = Field(default_factory=PlatformDetail)
    source: Optional[SourceDetail] = Field(default_factory=SourceDetail)
    license: Optional[LicenseDetail] = Field(default_factory=LicenseDetail)
    evidence: Optional[EvidenceDetail] = Field(default_factory=EvidenceDetail)

class ResourceCreate(ResourceBase):
    version: str = Field(default='1.0.0', json_schema_extra={'example': '2.1.0'})

class ResourceRead(ResourceBase):
    version: Optional[str] = '1.0.0'
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
