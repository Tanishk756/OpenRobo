"""Pydantic schemas for release catalog, artifact sources, deployments, approvals, and events."""

import hashlib
import json
import os
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional

from openrobo_release.deployment_protocol import (
    ApprovalAction,
    DeploymentState,
    DeviceDeploymentState,
    ReleaseSnapshot,
    ReleaseStatus,
    RolloutStrategy,
    TargetFilter,
    validate_digest,
    validate_release_key_id,
)
from pydantic import BaseModel, Field, field_validator


class ReleaseArtifactCreate(BaseModel):
    release_id: str = Field(..., min_length=3, max_length=128)
    release_version: str = Field(..., min_length=1, max_length=64)
    manifest_digest: str = Field(..., min_length=64, max_length=64)
    artifact_digest: str = Field(..., min_length=64, max_length=64)
    workspace_digest: str = Field(..., min_length=64, max_length=64)
    release_key_id: str = Field(..., min_length=1, max_length=64)
    artifact_source_id: str = Field(..., min_length=1, max_length=64)
    target_os: str = Field(default="linux", max_length=32)
    target_architecture: str = Field(default="x86_64", max_length=32)
    target_ros_distro: Optional[str] = Field(default=None, max_length=64)

    @field_validator("manifest_digest", "artifact_digest", "workspace_digest")
    @classmethod
    def validate_sha256(cls, v: str) -> str:
        validate_digest(v, "digest")
        return v.lower()

    @field_validator("release_key_id")
    @classmethod
    def validate_key_id(cls, v: str) -> str:
        validate_release_key_id(v)
        return v


class ReleaseArtifactResponse(BaseModel):
    id: str
    release_id: str
    release_version: str
    manifest_digest: str
    artifact_digest: str
    workspace_digest: str
    release_key_id: str
    artifact_source_id: str
    target_os: str
    target_architecture: str
    target_ros_distro: Optional[str] = None
    status: ReleaseStatus
    immutable_after_deployment: bool
    registered_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ArtifactSourceCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=64)
    base_url: str = Field(..., min_length=8, max_length=512)
    allowed_host: str = Field(..., min_length=1, max_length=255)
    ca_policy: Optional[str] = Field(default=None, max_length=255)
    max_artifact_bytes: int = Field(default=104857600, gt=0, le=1073741824)  # max 1 GB
    allow_private_network: bool = Field(default=False)

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        parsed = urllib.parse.urlparse(v.strip())
        if not parsed.scheme or not parsed.hostname:
            raise ValueError("base_url must include scheme and hostname")
        if parsed.username or parsed.password:
            raise ValueError("base_url must not contain embedded user credentials")
        if parsed.query or parsed.fragment:
            raise ValueError("base_url must not contain query parameters or fragments")

        is_dev = os.getenv("ENVIRONMENT") == "development"
        allow_dev_http = os.getenv("OPENROBO_ALLOW_DEV_ARTIFACT_HTTP", "false").lower() in ("true", "1")

        if parsed.scheme.lower() == "http":
            if not (is_dev and allow_dev_http):
                raise ValueError(
                    "HTTP artifact sources are only permitted when ENVIRONMENT=development and OPENROBO_ALLOW_DEV_ARTIFACT_HTTP=true"
                )
        elif parsed.scheme.lower() != "https":
            raise ValueError("Artifact source base_url must use HTTPS (or HTTP in dev mode with OPENROBO_ALLOW_DEV_ARTIFACT_HTTP=true)")

        return v.strip().rstrip("/")


class ArtifactSourceResponse(BaseModel):
    id: str
    base_url: str
    enabled: bool
    allowed_host: str
    ca_policy: Optional[str] = None
    max_artifact_bytes: int
    allow_private_network: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DeploymentCreate(BaseModel):
    release_id: str = Field(..., min_length=1, max_length=128)
    rollout_strategy: RolloutStrategy = Field(default_factory=RolloutStrategy)
    target_filter: TargetFilter = Field(default_factory=TargetFilter)
    idempotency_key: Optional[str] = Field(default=None, max_length=128)

    def compute_request_digest(self) -> str:
        data = {
            "release_id": self.release_id,
            "rollout_strategy": self.rollout_strategy.model_dump(),
            "target_filter": self.target_filter.model_dump(),
        }
        canon = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()


class DeviceDeploymentResponse(BaseModel):
    id: str
    deployment_id: str
    device_id: str
    stage_index: int
    status: DeviceDeploymentState
    generation: int
    error_message: Optional[str] = None
    staged_slot: Optional[str] = None
    active_slot: Optional[str] = None
    last_attempt_at: Optional[datetime] = None
    retry_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StageSummary(BaseModel):
    stage_index: int
    target_percentage: int
    total_devices: int
    pending: int = 0
    fetching: int = 0
    verifying: int = 0
    staging: int = 0
    staged: int = 0
    activating: int = 0
    active: int = 0
    failed: int = 0
    cancelled: int = 0


class DeploymentResponse(BaseModel):
    id: str
    release_id: str
    release_snapshot: ReleaseSnapshot
    rollout_strategy: RolloutStrategy
    target_filter: TargetFilter
    status: DeploymentState
    current_stage: int
    total_stages: int
    generation: int
    version: int
    idempotency_key: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    cancelled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    stages: Optional[List[StageSummary]] = None

    class Config:
        from_attributes = True


class DeploymentApprovalRequest(BaseModel):
    stage_index: int = Field(..., ge=0)
    action: ApprovalAction
    expected_version: int = Field(..., ge=1)
    expected_state: DeploymentState
    notes: Optional[str] = Field(default=None, max_length=1024)


class DeploymentApprovalResponse(BaseModel):
    id: str
    deployment_id: str
    stage_index: int
    action: ApprovalAction
    approved_by: str
    previous_state: DeploymentState
    new_state: DeploymentState
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DeploymentEventResponse(BaseModel):
    id: str
    deployment_id: str
    device_id: Optional[str] = None
    event_type: str
    details: Dict[str, Any]
    timestamp: datetime

    class Config:
        from_attributes = True
