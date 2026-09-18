"""Authoritative deployment protocol envelopes, state machines, validation logic, and schemas."""

import hashlib
import json
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DeploymentState(str, Enum):
    CREATED = "CREATED"
    PENDING = "PENDING"
    RESOLVING_TARGETS = "RESOLVING_TARGETS"
    STAGING_STAGE_0 = "STAGING_STAGE_0"
    STAGE_0_STAGING = "STAGING_STAGE_0"
    STAGE_0_WAITING_FOR_ACTIVATION_APPROVAL = "STAGE_0_WAITING_FOR_ACTIVATION_APPROVAL"
    ACTIVATING_STAGE_0 = "ACTIVATING_STAGE_0"
    STAGE_0_WAITING_FOR_STAGE_APPROVAL = "STAGE_0_WAITING_FOR_STAGE_APPROVAL"
    STAGE_0_ACTIVE = "STAGE_0_ACTIVE"
    STAGING_STAGE_1 = "STAGING_STAGE_1"
    STAGE_1_STAGING = "STAGING_STAGE_1"
    STAGE_1_WAITING_FOR_ACTIVATION_APPROVAL = "STAGE_1_WAITING_FOR_ACTIVATION_APPROVAL"
    ACTIVATING_STAGE_1 = "ACTIVATING_STAGE_1"
    STAGE_1_WAITING_FOR_STAGE_APPROVAL = "STAGE_1_WAITING_FOR_STAGE_APPROVAL"
    STAGE_1_ACTIVE = "STAGE_1_ACTIVE"
    STAGE_1_WAITING_FOR_STAGING_APPROVAL = "STAGE_1_WAITING_FOR_STAGE_APPROVAL"
    STAGING_STAGE_2 = "STAGING_STAGE_2"
    STAGE_2_STAGING = "STAGING_STAGE_2"
    STAGE_2_WAITING_FOR_ACTIVATION_APPROVAL = "STAGE_2_WAITING_FOR_ACTIVATION_APPROVAL"
    ACTIVATING_STAGE_2 = "ACTIVATING_STAGE_2"
    STAGE_2_WAITING_FOR_STAGING_APPROVAL = "STAGE_2_WAITING_FOR_STAGING_APPROVAL"
    STAGE_2_ACTIVE = "STAGE_2_ACTIVE"
    STAGE_0_FAILED = "STAGE_0_FAILED"
    STAGE_1_FAILED = "STAGE_1_FAILED"
    STAGE_2_FAILED = "STAGE_2_FAILED"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class DeviceDeploymentState(str, Enum):
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
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class InstructionType(str, Enum):
    STAGE_RELEASE = "STAGE_RELEASE"
    ACTIVATE_RELEASE = "ACTIVATE_RELEASE"
    CANCEL_DEPLOYMENT = "CANCEL_DEPLOYMENT"
    GET_DEPLOYMENT_STATUS = "GET_DEPLOYMENT_STATUS"


class InstructionStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ReleaseStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    DEPRECATED = "DEPRECATED"


class ApprovalAction(str, Enum):
    APPROVE_ACTIVATION = "APPROVE_ACTIVATION"
    APPROVE_CURRENT_COHORT_ACTIVATION = "APPROVE_CURRENT_COHORT_ACTIVATION"
    APPROVE_NEXT_STAGE = "APPROVE_NEXT_STAGE"
    APPROVE_COMPLETION = "APPROVE_COMPLETION"
    REJECT_AND_CANCEL = "REJECT_AND_CANCEL"


class RolloutStrategyType(str, Enum):
    IMMEDIATE_ALL = "IMMEDIATE_ALL"
    CANARY = "CANARY"


class CanaryStageConfig(BaseModel):
    stage_index: int = Field(..., ge=0)
    target_percentage: int = Field(..., gt=0, le=100)
    bake_time_sec: int = Field(default=0, ge=0)


class RolloutStrategy(BaseModel):
    strategy_type: RolloutStrategyType = Field(default=RolloutStrategyType.IMMEDIATE_ALL)
    stages: List[CanaryStageConfig] = Field(default_factory=list)

    @field_validator("stages")
    @classmethod
    def validate_cumulative_stages(cls, v: List[CanaryStageConfig]) -> List[CanaryStageConfig]:
        if not v:
            return v
        pcts = [s.target_percentage for s in v]
        for i in range(len(pcts)):
            if pcts[i] > 100:
                raise ValueError("Stage target percentage cannot exceed 100%")
            if i > 0 and pcts[i] <= pcts[i - 1]:
                raise ValueError("Canary stage target percentages must be strictly increasing")
        if pcts[-1] != 100:
            raise ValueError("Final canary stage must target exactly 100% cumulative coverage")
        return v


class TargetFilter(BaseModel):
    device_ids: Optional[List[str]] = None
    domains: Optional[List[str]] = None
    robot_types: Optional[List[str]] = None
    capabilities: Optional[List[str]] = None
    os: Optional[str] = None
    architecture: Optional[str] = None
    ros_distro: Optional[str] = None


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


# Typed Payload Schemas for Instructions
class StageReleasePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deployment_id: str
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


class ActivateReleasePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deployment_id: str
    slot: str  # "A" or "B"


class CancelDeploymentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deployment_id: str


class GetDeploymentStatusPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deployment_id: str


def canonical_instruction_digest(envelope: Union["DeploymentInstructionEnvelope", dict]) -> str:
    if isinstance(envelope, dict):
        proto = envelope.get("protocol_version", "1.0")
        inst_id = envelope.get("instruction_id")
        dep_id = envelope.get("deployment_id")
        dev_id = envelope.get("device_id")
        gen = envelope.get("generation")
        itype = envelope.get("instruction_type")
        payload = envelope.get("payload")
        c_at = envelope.get("created_at")
        e_at = envelope.get("expires_at")
    else:
        proto = envelope.protocol_version
        inst_id = envelope.instruction_id
        dep_id = envelope.deployment_id
        dev_id = envelope.device_id
        gen = envelope.generation
        itype = envelope.instruction_type
        payload = envelope.payload
        c_at = envelope.created_at
        e_at = envelope.expires_at

    fields = {
        "protocol_version": proto,
        "instruction_id": inst_id,
        "deployment_id": dep_id,
        "device_id": dev_id,
        "generation": gen,
        "instruction_type": itype.value if hasattr(itype, "value") else str(itype),
        "payload": payload,
        "created_at": c_at,
        "expires_at": e_at,
    }
    canon = json.dumps(fields, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


class DeploymentInstructionEnvelope(BaseModel):
    protocol_version: str = Field(default="1.0")
    instruction_id: str
    deployment_id: str
    device_id: Optional[str] = "unknown"
    generation: int
    instruction_type: InstructionType
    payload: Dict[str, Any]
    payload_digest: str
    created_at: str
    expires_at: str

    def get_canonical_instruction_digest(self) -> str:
        return canonical_instruction_digest(self)


class DeploymentAckEnvelope(BaseModel):
    protocol_version: str = Field(default="1.0")
    ack_id: str
    instruction_id: str
    deployment_id: str
    device_id: str
    generation: int
    accepted: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: str

    @property
    def reason(self) -> str:
        if self.error_code:
            return self.error_code
        return "ACCEPTED" if self.accepted else "REJECTED"


class DeploymentStatusReport(BaseModel):
    protocol_version: str = Field(default="1.0")
    report_id: str
    instruction_id: str
    deployment_id: str
    device_id: str
    generation: int
    state: DeviceDeploymentState
    current_slot: Optional[str] = None
    staged_slot: Optional[str] = None
    active_slot: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: str


class DeploymentEventPayload(BaseModel):
    protocol_version: str = Field(default="1.0")
    event_id: str
    deployment_id: str
    device_id: str
    event_type: str
    details: Dict[str, Any]
    timestamp: str


DEPLOYMENT_TRANSITIONS: Dict[DeploymentState, Set[DeploymentState]] = {
    DeploymentState.CREATED: {
        DeploymentState.PENDING,
        DeploymentState.RESOLVING_TARGETS,
        DeploymentState.STAGE_0_STAGING,
        DeploymentState.PAUSED,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.PENDING: {
        DeploymentState.RESOLVING_TARGETS,
        DeploymentState.STAGE_0_STAGING,
        DeploymentState.PAUSED,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.RESOLVING_TARGETS: {
        DeploymentState.STAGE_0_STAGING,
        DeploymentState.PAUSED,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.STAGE_0_STAGING: {
        DeploymentState.STAGE_0_WAITING_FOR_ACTIVATION_APPROVAL,
        DeploymentState.STAGE_0_FAILED,
        DeploymentState.PAUSED,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.STAGE_0_WAITING_FOR_ACTIVATION_APPROVAL: {
        DeploymentState.ACTIVATING_STAGE_0,
        DeploymentState.PAUSED,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.ACTIVATING_STAGE_0: {
        DeploymentState.STAGE_0_ACTIVE,
        DeploymentState.STAGE_0_WAITING_FOR_STAGE_APPROVAL,
        DeploymentState.STAGE_1_WAITING_FOR_STAGING_APPROVAL,
        DeploymentState.COMPLETED,
        DeploymentState.STAGE_0_FAILED,
        DeploymentState.PAUSED,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.STAGE_0_ACTIVE: {
        DeploymentState.STAGE_1_WAITING_FOR_STAGING_APPROVAL,
        DeploymentState.STAGE_0_WAITING_FOR_STAGE_APPROVAL,
        DeploymentState.COMPLETED,
        DeploymentState.PAUSED,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.STAGE_0_WAITING_FOR_STAGE_APPROVAL: {
        DeploymentState.STAGE_1_STAGING,
        DeploymentState.COMPLETED,
        DeploymentState.PAUSED,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.STAGE_1_WAITING_FOR_STAGING_APPROVAL: {
        DeploymentState.STAGE_1_STAGING,
        DeploymentState.COMPLETED,
        DeploymentState.PAUSED,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.STAGE_1_STAGING: {
        DeploymentState.STAGE_1_WAITING_FOR_ACTIVATION_APPROVAL,
        DeploymentState.STAGE_1_FAILED,
        DeploymentState.PAUSED,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.STAGE_1_WAITING_FOR_ACTIVATION_APPROVAL: {
        DeploymentState.ACTIVATING_STAGE_1,
        DeploymentState.PAUSED,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.ACTIVATING_STAGE_1: {
        DeploymentState.STAGE_1_ACTIVE,
        DeploymentState.STAGE_1_WAITING_FOR_STAGE_APPROVAL,
        DeploymentState.STAGE_2_WAITING_FOR_STAGING_APPROVAL,
        DeploymentState.COMPLETED,
        DeploymentState.STAGE_1_FAILED,
        DeploymentState.PAUSED,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.STAGE_1_ACTIVE: {
        DeploymentState.STAGE_2_WAITING_FOR_STAGING_APPROVAL,
        DeploymentState.STAGE_1_WAITING_FOR_STAGE_APPROVAL,
        DeploymentState.COMPLETED,
        DeploymentState.PAUSED,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.STAGE_1_WAITING_FOR_STAGE_APPROVAL: {
        DeploymentState.STAGE_2_STAGING,
        DeploymentState.COMPLETED,
        DeploymentState.PAUSED,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.STAGE_2_WAITING_FOR_STAGING_APPROVAL: {
        DeploymentState.STAGE_2_STAGING,
        DeploymentState.COMPLETED,
        DeploymentState.PAUSED,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.STAGE_2_STAGING: {
        DeploymentState.STAGE_2_WAITING_FOR_ACTIVATION_APPROVAL,
        DeploymentState.STAGE_2_FAILED,
        DeploymentState.PAUSED,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.STAGE_2_WAITING_FOR_ACTIVATION_APPROVAL: {
        DeploymentState.ACTIVATING_STAGE_2,
        DeploymentState.PAUSED,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.ACTIVATING_STAGE_2: {
        DeploymentState.STAGE_2_ACTIVE,
        DeploymentState.COMPLETED,
        DeploymentState.STAGE_2_FAILED,
        DeploymentState.PAUSED,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.STAGE_2_ACTIVE: {
        DeploymentState.COMPLETED,
        DeploymentState.PAUSED,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.PAUSED: {
        DeploymentState.STAGE_0_STAGING,
        DeploymentState.STAGE_0_WAITING_FOR_ACTIVATION_APPROVAL,
        DeploymentState.ACTIVATING_STAGE_0,
        DeploymentState.STAGE_0_ACTIVE,
        DeploymentState.STAGE_0_WAITING_FOR_STAGE_APPROVAL,
        DeploymentState.STAGE_1_WAITING_FOR_STAGING_APPROVAL,
        DeploymentState.STAGE_1_STAGING,
        DeploymentState.STAGE_1_WAITING_FOR_ACTIVATION_APPROVAL,
        DeploymentState.ACTIVATING_STAGE_1,
        DeploymentState.STAGE_1_ACTIVE,
        DeploymentState.STAGE_1_WAITING_FOR_STAGE_APPROVAL,
        DeploymentState.STAGE_2_WAITING_FOR_STAGING_APPROVAL,
        DeploymentState.STAGE_2_STAGING,
        DeploymentState.STAGE_2_WAITING_FOR_ACTIVATION_APPROVAL,
        DeploymentState.ACTIVATING_STAGE_2,
        DeploymentState.STAGE_2_ACTIVE,
        DeploymentState.CANCELLING,
        DeploymentState.CANCELLED,
        DeploymentState.FAILED,
    },
    DeploymentState.CANCELLING: {DeploymentState.CANCELLED, DeploymentState.FAILED},
    DeploymentState.COMPLETED: set(),
    DeploymentState.CANCELLED: set(),
    DeploymentState.FAILED: set(),
    DeploymentState.STAGE_0_FAILED: {DeploymentState.CANCELLED, DeploymentState.FAILED},
    DeploymentState.STAGE_1_FAILED: {DeploymentState.CANCELLED, DeploymentState.FAILED},
    DeploymentState.STAGE_2_FAILED: {DeploymentState.CANCELLED, DeploymentState.FAILED},
}

DEVICE_TRANSITIONS: Dict[DeviceDeploymentState, Set[DeviceDeploymentState]] = {
    DeviceDeploymentState.PENDING: {
        DeviceDeploymentState.INSTRUCTION_QUEUED,
        DeviceDeploymentState.FETCHING,
        DeviceDeploymentState.STAGING,
        DeviceDeploymentState.STAGED,
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


def validate_digest(digest: str, field_name: str = "digest") -> str:
    digest_clean = digest.strip().lower()
    if len(digest_clean) != 64 or not all(c in "0123456789abcdef" for c in digest_clean):
        raise ValueError(f"{field_name} must be a 64-character lowercase hex SHA-256 string")
    return digest_clean


def validate_release_key_id(key_id: str) -> str:
    key_id_clean = key_id.strip()
    if not key_id_clean or len(key_id_clean) > 128:
        raise ValueError("release_key_id must be non-empty and <= 128 characters")
    if not all(c.isalnum() or c in "-_." for c in key_id_clean):
        raise ValueError("release_key_id contains invalid characters")
    return key_id_clean
