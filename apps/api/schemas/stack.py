from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class StackComponentBase(BaseModel):
    resource_id: str
    version: Optional[str] = "1.0.0"
    category: Optional[str] = "general"
    optional: bool = False
    notes: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = Field(default_factory=dict)


class StackComponentCreate(StackComponentBase):
    pass


class StackComponentRead(StackComponentBase):
    pass


class StackCreate(BaseModel):
    name: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$")
    version: str = "1.0.0"
    description: Optional[str] = None
    robot_domain: str = "general_robotics"
    robot_type: str = "custom"
    target_os: Optional[str] = "ubuntu_24_04"
    target_arch: Optional[str] = "x86_64"
    target_ros_distro: Optional[str] = "jazzy"
    components: List[StackComponentCreate] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class StackUpdate(BaseModel):
    name: Optional[str] = Field(None, pattern=r"^[a-zA-Z0-9_-]+$")
    version: Optional[str] = None
    description: Optional[str] = None
    robot_domain: Optional[str] = None
    robot_type: Optional[str] = None
    target_os: Optional[str] = None
    target_arch: Optional[str] = None
    target_ros_distro: Optional[str] = None
    components: Optional[List[StackComponentCreate]] = None
    metadata: Optional[Dict[str, Any]] = None


class StackRead(BaseModel):
    id: str
    name: str
    version: str
    description: Optional[str] = None
    robot_domain: str
    robot_type: str
    target_os: Optional[str] = None
    target_arch: Optional[str] = None
    target_ros_distro: Optional[str] = None
    components: List[StackComponentRead] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StackValidateRequest(BaseModel):
    components: List[StackComponentCreate] = Field(default_factory=list)
    target_os: Optional[str] = None
    target_arch: Optional[str] = None
    target_ros_distro: Optional[str] = None


class StackResolveRequest(BaseModel):
    components: List[StackComponentCreate] = Field(default_factory=list)
    target_os: Optional[str] = None
    target_arch: Optional[str] = None
    target_ros_distro: Optional[str] = None


class StackImportRequest(BaseModel):
    manifest: Dict[str, Any]


class StackTemplate(BaseModel):
    id: str
    name: str
    title: str
    description: str
    robot_domain: str
    robot_type: str
    target_os: str
    target_arch: str
    target_ros_distro: str
    components: List[StackComponentCreate]
    metadata: Dict[str, Any] = Field(default_factory=dict)
