from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any

class SourceDetail(BaseModel):
    repo_url: Optional[str] = Field(default=None, json_schema_extra={"example": "https://github.com/ros-controls/ros2_control"})

class LicenseDetail(BaseModel):
    spdx_id: str = Field(default="Apache-2.0", json_schema_extra={"example": "Apache-2.0"})

class ResourceBase(BaseModel):
    id: str = Field(..., json_schema_extra={"example": "ros-controls/ros2_control"})
    name: str = Field(..., json_schema_extra={"example": "ros2_control"})
    type: str = Field(..., json_schema_extra={"example": "ros_package"})
    summary: Optional[str] = None
    description: Optional[str] = None
    spdx_license_id: str = Field(default="NOASSERTION", json_schema_extra={"example": "Apache-2.0"})
    repo_url: Optional[str] = None
    evidence_level: str = Field(default="unknown", json_schema_extra={"example": "ci_verified"})
    source: Optional[SourceDetail] = Field(default_factory=lambda: SourceDetail())
    license: Optional[LicenseDetail] = Field(default_factory=lambda: LicenseDetail())

class ResourceCreate(ResourceBase):
    version: str = Field(..., json_schema_extra={"example": "2.1.0"})

class ResourceRead(ResourceBase):
    model_config = ConfigDict(from_attributes=True)
