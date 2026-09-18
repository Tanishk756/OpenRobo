"""Data models and state representations for the local A/B deployment slot manager."""

from enum import Enum

from pydantic import BaseModel, Field


class SlotState(str, Enum):
    """Lifecycle states of a workspace partition slot."""

    EMPTY = "EMPTY"
    STAGING = "STAGING"
    VERIFIED = "VERIFIED"
    ACTIVE = "ACTIVE"
    PREVIOUS = "PREVIOUS"
    FAILED = "FAILED"
    QUARANTINED = "QUARANTINED"


class SlotMetadata(BaseModel):
    """Persisted metadata tracking a single workspace slot partition."""

    slot_id: str
    state: SlotState = SlotState.EMPTY
    release_id: str | None = None
    release_version: str | None = None
    artifact_digest: str | None = None
    manifest_digest: str | None = None
    workspace_digest: str | None = None
    key_id: str | None = None
    installed_at: str | None = None
    verified_at: str | None = None
    activated_at: str | None = None
    previous_release_id: str | None = None


class ActivationIntent(BaseModel):
    """Crash-consistent transaction journal tracking an in-flight pointer switch."""

    transaction_id: str
    from_slot: str | None = None
    to_slot: str
    release_id: str
    state: str = "PENDING"  # PENDING -> SWITCHED -> COMPLETED
    created_at: str


class SlotsState(BaseModel):
    """Top-level deployment state recording slot allocations and active pointer."""

    active_slot: str | None = None
    slots: dict[str, SlotMetadata] = Field(default_factory=dict)
