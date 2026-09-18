"""Data models for A/B Workspace Partitioning and Local Deployment Lifecycle."""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SlotState(str, Enum):
    """Lifecycle state of a workspace deployment slot."""
    EMPTY = "EMPTY"
    STAGING = "STAGING"
    STAGED = "STAGED"
    VERIFIED = "VERIFIED"
    ACTIVE = "ACTIVE"
    PREVIOUS = "PREVIOUS"
    FAILED = "FAILED"
    QUARANTINED = "QUARANTINED"


class SlotMetadata(BaseModel):
    """Persisted metadata for an A/B workspace slot."""
    slot_id: str = Field(..., description="Unique slot identifier ('slot-a' or 'slot-b')")
    release_id: Optional[str] = Field(default=None, description="Installed release ID")
    release_version: Optional[str] = Field(default=None, description="Installed release version")
    artifact_digest: Optional[str] = Field(default=None, description="SHA-256 digest of source artifact")
    manifest_digest: Optional[str] = Field(default=None, description="SHA-256 digest of canonical manifest")
    workspace_digest: Optional[str] = Field(default=None, description="SHA-256 tree digest of workspace")
    installed_at: Optional[str] = Field(default=None, description="ISO 8601 timestamp of installation")
    verified_at: Optional[str] = Field(default=None, description="ISO 8601 timestamp of verification")
    activated_at: Optional[str] = Field(default=None, description="ISO 8601 timestamp of activation")
    previous_release_id: Optional[str] = Field(default=None, description="Prior release ID before switch")
    status: SlotState = Field(default=SlotState.EMPTY, description="Current slot lifecycle state")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional diagnostic metadata")
