"""Canonical Protocol Definitions, Envelopes, State Machines & Validation for Remote Deployment Orchestration (M7.2.2)."""

import enum
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

# ==============================================================================
# Enums
# ==============================================================================


class DeploymentState(str, enum.Enum):
    # Lifecycle States
    CREATED = "CREATED"
    TARGETS_RESOLVED = "TARGETS_RESOLVED"
    STAGING_STAGE_0 = "STAGING_STAGE_0"
    STAGE_0_WAITING_FOR_ACTIVATION_APPROVAL = "STAGE_0_WAITING_FOR_ACTIVATION_APPROVAL"
    ACTIVATING_STAGE_0 = "ACTIVATING_STAGE_0"
    STAGE_0_WAITING_FOR_STAGE_APPROVAL = "STAGE_0_WAITING_FOR_STAGE_APPROVAL"
    STAGE_0_FAILED = "STAGE_0_FAILED"

    STAGING_STAGE_1 = "STAGING_STAGE_1"
    STAGE_1_WAITING_FOR_ACTIVATION_APPROVAL = "STAGE_1_WAITING_FOR_ACTIVATION_APPROVAL"
    ACTIVATING_STAGE_1 = "ACTIVATING_STAGE_1"
    STAGE_1_WAITING_FOR_STAGE_APPROVAL = "STAGE_1_WAITING_FOR_STAGE_APPROVAL"
    STAGE_1_FAILED = "STAGE_1_FAILED"

    STAGING_STAGE_2 = "STAGING_STAGE_2"
    STAGE_2_WAITING_FOR_ACTIVATION_APPROVAL = "STAGE_2_WAITING_FOR_ACTIVATION_APPROVAL"
    ACTIVATING_STAGE_2 = "ACTIVATING_STAGE_2"
    STAGE_2_FAILED = "STAGE_2_FAILED"

    # Generic Canaries and Stages
    STAGING_CANARY = "STAGING_CANARY"
    CANARY_STAGED = "CANARY_STAGED"
    AWAITING_ACTIVATION_APPROVAL = "AWAITING_ACTIVATION_APPROVAL"
    ACTIVATING_CANARY = "ACTIVATING_CANARY"
    CANARY_ACTIVE = "CANARY_ACTIVE"
    AWAITING_NEXT_STAGE_APPROVAL = "AWAITING_NEXT_STAGE_APPROVAL"
    STAGING_NEXT_COHORT = "STAGING_NEXT_COHORT"
    ACTIVATING_NEXT_COHORT = "ACTIVATING_NEXT_COHORT"

    # Terminal & Operational States
    PAUSED = "PAUSED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DeviceDeploymentState(str, enum.Enum):
    PENDING = "PENDING"
    INSTRUCTION_QUEUED = "INSTRUCTION_QUEUED"
    FETCHING = "FETCHING"
    DOWNLOADED = "DOWNLOADED"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    STAGING = "STAGING"
    STAGED = "STAGED"
    AWAITING_ACTIVATION = "AWAITING_ACTIVATION"
    ACTIVATING = "ACTIVATING"
    ACTIVE = "ACTIVE"
    OFFLINE = "OFFLINE"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class RolloutStrategyType(str, enum.Enum):
    IMMEDIATE_ALL = "IMMEDIATE_ALL"
    CANARY = "CANARY"
    LINEAR = "LINEAR"


class InstructionType(str, enum.Enum):
    STAGE_RELEASE = "STAGE_RELEASE"
    ACTIVATE_RELEASE = "ACTIVATE_RELEASE"
    CANCEL_DEPLOYMENT = "CANCEL_DEPLOYMENT"
    GET_DEPLOYMENT_STATUS = "GET_DEPLOYMENT_STATUS"


class ReleaseStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    RETIRED = "RETIRED"


class InstructionStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class ApprovalAction(str, enum.Enum):
    APPROVE_CURRENT_COHORT_ACTIVATION = "APPROVE_CURRENT_COHORT_ACTIVATION"
    APPROVE_NEXT_COHORT_STAGING = "APPROVE_NEXT_COHORT_STAGING"
    APPROVE_COMPLETION = "APPROVE_COMPLETION"
    REJECT_AND_CANCEL = "REJECT_AND_CANCEL"


# ==============================================================================
# Helper Validators
# ==============================================================================

DIGEST_REGEX = re.compile(r"^[a-fA-F0-9]{64}$")
KEY_ID_REGEX = re.compile(r"^[-a-zA-Z0-9_.:]{3,64}$")


def validate_digest(digest: str, field_name: str = "digest") -> None:
    if not isinstance(digest, str) or not DIGEST_REGEX.match(digest):
        raise ValueError(f"Invalid SHA-256 {field_name}: '{digest}'. Must be 64-character lowercase hex string.")


def validate_release_key_id(key_id: str) -> None:
    if not isinstance(key_id, str) or not KEY_ID_REGEX.match(key_id):
        raise ValueError(f"Invalid release key identifier: '{key_id}'. Must match {KEY_ID_REGEX.pattern}")


# ==============================================================================
# Schemas & Envelopes
# ==============================================================================


class RolloutStageConfig(BaseModel):
    stage_index: int = Field(ge=0)
    target_percentage: int = Field(ge=1, le=100)
    require_approval: bool = Field(default=True)
    description: Optional[str] = None


class RolloutStrategy(BaseModel):
    strategy_type: RolloutStrategyType = Field(default=RolloutStrategyType.IMMEDIATE_ALL)
    stages: Optional[List[RolloutStageConfig]] = None


class TargetFilter(BaseModel):
    device_ids: Optional[List[str]] = Field(default=None)
    domains: Optional[List[str]] = Field(default=None)
    robot_types: Optional[List[str]] = Field(default=None)
    capabilities: Optional[List[str]] = Field(default=None)
    tags: Optional[List[str]] = Field(default=None)
    platform: Optional[str] = Field(default=None)
    architecture: Optional[str] = Field(default=None)
    ros_distro: Optional[str] = Field(default=None)


class ReleaseSnapshot(BaseModel):
    release_id: str
    release_version: str
    manifest_digest: str
    artifact_digest: str
    workspace_digest: str
    release_key_id: str
    artifact_source_id: str
    target_os: str = "linux"
    target_architecture: str = "x86_64"
    target_ros_distro: Optional[str] = None


class DeploymentInstructionEnvelope(BaseModel):
    instruction_id: str
    deployment_id: str
    generation: int = Field(ge=1)
    instruction_type: InstructionType
    payload: Dict[str, Any] = Field(default_factory=dict)
    payload_digest: str
    created_at: str
    expires_at: str
    protocol_version: str = Field(default="1.0.0")

    def canonical_digest(self) -> str:
        canonical_bytes = json.dumps(self.payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical_bytes).hexdigest()


class DeploymentAckEnvelope(BaseModel):
    instruction_id: str
    deployment_id: str
    device_id: str
    generation: int
    accepted: bool
    reason: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    protocol_version: str = Field(default="1.0.0")


class DeploymentStatusReport(BaseModel):
    deployment_id: str
    device_id: str
    generation: int
    state: DeviceDeploymentState
    staged_slot: Optional[str] = None
    active_slot: Optional[str] = None
    error_message: Optional[str] = None
    reported_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    protocol_version: str = Field(default="1.0.0")


# ==============================================================================
# Transition Graphs
# ==============================================================================

DEPLOYMENT_TRANSITIONS: Dict[DeploymentState, Set[DeploymentState]] = {
    DeploymentState.CREATED: {
        DeploymentState.TARGETS_RESOLVED,
        DeploymentState.STAGING_STAGE_0,
        DeploymentState.STAGING_CANARY,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.STAGING_STAGE_0: {
        DeploymentState.STAGE_0_WAITING_FOR_ACTIVATION_APPROVAL,
        DeploymentState.STAGE_0_FAILED,
        DeploymentState.CANCELLED,
        DeploymentState.PAUSED,
    },
    DeploymentState.STAGE_0_WAITING_FOR_ACTIVATION_APPROVAL: {
        DeploymentState.ACTIVATING_STAGE_0,
        DeploymentState.CANCELLED,
        DeploymentState.PAUSED,
    },
    DeploymentState.ACTIVATING_STAGE_0: {
        DeploymentState.STAGE_0_WAITING_FOR_STAGE_APPROVAL,
        DeploymentState.STAGE_0_FAILED,
        DeploymentState.COMPLETED,
        DeploymentState.CANCELLED,
        DeploymentState.PAUSED,
    },
    DeploymentState.STAGE_0_WAITING_FOR_STAGE_APPROVAL: {
        DeploymentState.STAGING_STAGE_1,
        DeploymentState.COMPLETED,
        DeploymentState.CANCELLED,
        DeploymentState.PAUSED,
    },
    DeploymentState.STAGING_STAGE_1: {
        DeploymentState.STAGE_1_WAITING_FOR_ACTIVATION_APPROVAL,
        DeploymentState.STAGE_1_FAILED,
        DeploymentState.CANCELLED,
        DeploymentState.PAUSED,
    },
    DeploymentState.STAGE_1_WAITING_FOR_ACTIVATION_APPROVAL: {
        DeploymentState.ACTIVATING_STAGE_1,
        DeploymentState.CANCELLED,
        DeploymentState.PAUSED,
    },
    DeploymentState.ACTIVATING_STAGE_1: {
        DeploymentState.STAGE_1_WAITING_FOR_STAGE_APPROVAL,
        DeploymentState.STAGE_1_FAILED,
        DeploymentState.COMPLETED,
        DeploymentState.CANCELLED,
        DeploymentState.PAUSED,
    },
    DeploymentState.STAGE_1_WAITING_FOR_STAGE_APPROVAL: {
        DeploymentState.STAGING_STAGE_2,
        DeploymentState.COMPLETED,
        DeploymentState.CANCELLED,
        DeploymentState.PAUSED,
    },
    DeploymentState.STAGING_STAGE_2: {
        DeploymentState.STAGE_2_WAITING_FOR_ACTIVATION_APPROVAL,
        DeploymentState.STAGE_2_FAILED,
        DeploymentState.CANCELLED,
        DeploymentState.PAUSED,
    },
    DeploymentState.STAGE_2_WAITING_FOR_ACTIVATION_APPROVAL: {
        DeploymentState.ACTIVATING_STAGE_2,
        DeploymentState.CANCELLED,
        DeploymentState.PAUSED,
    },
    DeploymentState.ACTIVATING_STAGE_2: {
        DeploymentState.COMPLETED,
        DeploymentState.STAGE_2_FAILED,
        DeploymentState.CANCELLED,
        DeploymentState.PAUSED,
    },
    DeploymentState.PAUSED: {
        DeploymentState.STAGING_STAGE_0,
        DeploymentState.ACTIVATING_STAGE_0,
        DeploymentState.STAGING_STAGE_1,
        DeploymentState.ACTIVATING_STAGE_1,
        DeploymentState.CANCELLED,
    },
    DeploymentState.CANCELLING: {DeploymentState.CANCELLED, DeploymentState.FAILED},
    DeploymentState.CANCELLED: set(),
    DeploymentState.COMPLETED: set(),
    DeploymentState.FAILED: set(),
    DeploymentState.STAGE_0_FAILED: {DeploymentState.CANCELLED},
    DeploymentState.STAGE_1_FAILED: {DeploymentState.CANCELLED},
    DeploymentState.STAGE_2_FAILED: {DeploymentState.CANCELLED},
}

DEVICE_TRANSITIONS: Dict[DeviceDeploymentState, Set[DeviceDeploymentState]] = {
    DeviceDeploymentState.PENDING: {
        DeviceDeploymentState.INSTRUCTION_QUEUED,
        DeviceDeploymentState.FETCHING,
        DeviceDeploymentState.OFFLINE,
        DeviceDeploymentState.CANCELLED,
        DeviceDeploymentState.FAILED,
        DeviceDeploymentState.REJECTED,
    },
    DeviceDeploymentState.INSTRUCTION_QUEUED: {
        DeviceDeploymentState.FETCHING,
        DeviceDeploymentState.OFFLINE,
        DeviceDeploymentState.CANCELLED,
        DeviceDeploymentState.FAILED,
        DeviceDeploymentState.REJECTED,
    },
    DeviceDeploymentState.FETCHING: {
        DeviceDeploymentState.DOWNLOADED,
        DeviceDeploymentState.VERIFYING,
        DeviceDeploymentState.OFFLINE,
        DeviceDeploymentState.CANCELLED,
        DeviceDeploymentState.FAILED,
    },
    DeviceDeploymentState.DOWNLOADED: {
        DeviceDeploymentState.VERIFYING,
        DeviceDeploymentState.CANCELLED,
        DeviceDeploymentState.FAILED,
    },
    DeviceDeploymentState.VERIFYING: {
        DeviceDeploymentState.VERIFIED,
        DeviceDeploymentState.STAGING,
        DeviceDeploymentState.CANCELLED,
        DeviceDeploymentState.FAILED,
        DeviceDeploymentState.REJECTED,
    },
    DeviceDeploymentState.VERIFIED: {
        DeviceDeploymentState.STAGING,
        DeviceDeploymentState.STAGED,
        DeviceDeploymentState.AWAITING_ACTIVATION,
        DeviceDeploymentState.CANCELLED,
        DeviceDeploymentState.FAILED,
    },
    DeviceDeploymentState.STAGING: {
        DeviceDeploymentState.STAGED,
        DeviceDeploymentState.AWAITING_ACTIVATION,
        DeviceDeploymentState.CANCELLED,
        DeviceDeploymentState.FAILED,
    },
    DeviceDeploymentState.STAGED: {
        DeviceDeploymentState.AWAITING_ACTIVATION,
        DeviceDeploymentState.ACTIVATING,
        DeviceDeploymentState.ACTIVE,
        DeviceDeploymentState.CANCELLED,
        DeviceDeploymentState.FAILED,
    },
    DeviceDeploymentState.AWAITING_ACTIVATION: {
        DeviceDeploymentState.ACTIVATING,
        DeviceDeploymentState.ACTIVE,
        DeviceDeploymentState.CANCELLED,
        DeviceDeploymentState.FAILED,
    },
    DeviceDeploymentState.ACTIVATING: {
        DeviceDeploymentState.ACTIVE,
        DeviceDeploymentState.FAILED,
        DeviceDeploymentState.CANCELLED,
    },
    DeviceDeploymentState.OFFLINE: {
        DeviceDeploymentState.PENDING,
        DeviceDeploymentState.FETCHING,
        DeviceDeploymentState.CANCELLED,
        DeviceDeploymentState.FAILED,
    },
    DeviceDeploymentState.ACTIVE: set(),
    DeviceDeploymentState.FAILED: set(),
    DeviceDeploymentState.CANCELLED: set(),
    DeviceDeploymentState.REJECTED: set(),
}


def validate_deployment_transition(current: DeploymentState, target: DeploymentState) -> None:
    if current == target:
        return
    allowed = DEPLOYMENT_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValueError(f"Invalid deployment state transition from {current.value} to {target.value}")


def validate_device_transition(current: DeviceDeploymentState, target: DeviceDeploymentState) -> None:
    if current == target:
        return
    allowed = DEVICE_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValueError(f"Invalid device deployment state transition from {current.value} to {target.value}")


def validate_deployment_state_transition(current: DeploymentState, target: DeploymentState) -> bool:
    try:
        validate_deployment_transition(current, target)
        return True
    except ValueError:
        return False


def validate_device_state_transition(current: DeviceDeploymentState, target: DeviceDeploymentState) -> bool:
    try:
        validate_device_transition(current, target)
        return True
    except ValueError:
        return False
