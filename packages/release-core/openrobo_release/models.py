"""Data models for OpenRobo release artifacts, manifests, keys, and safety policies."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class VerificationStatus(str, Enum):
    """Status outcomes of release verification."""

    VERIFIED = "VERIFIED"
    SIGNATURE_VALID = "SIGNATURE_VALID"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    UNTRUSTED_SIGNING_KEY = "UNTRUSTED_SIGNING_KEY"
    REVOKED_SIGNING_KEY = "REVOKED_SIGNING_KEY"
    EXPIRED_SIGNING_KEY = "EXPIRED_SIGNING_KEY"
    KEY_METADATA_INVALID = "KEY_METADATA_INVALID"
    MANIFEST_INVALID = "MANIFEST_INVALID"
    ARTIFACT_DIGEST_MISMATCH = "ARTIFACT_DIGEST_MISMATCH"
    FILE_DIGEST_MISMATCH = "FILE_DIGEST_MISMATCH"
    TARGET_INCOMPATIBLE = "TARGET_INCOMPATIBLE"
    TARGET_ENVIRONMENT_UNKNOWN = "TARGET_ENVIRONMENT_UNKNOWN"
    STALE_TELEMETRY = "STALE_TELEMETRY"
    POLICY_CONFIGURATION_INVALID = "POLICY_CONFIGURATION_INVALID"
    POLICY_FAILED = "POLICY_FAILED"


class KeyStatus(str, Enum):
    """Lifecycle status of a release signing key."""

    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class FileEntry(BaseModel):
    """Metadata and digest for a single file packaged in a release."""

    path: str
    sha256: str
    size_bytes: int


class ReleaseTarget(BaseModel):
    """Explicit target execution environment constraints."""

    operating_system: str
    architecture: str
    ros_distro: str | None = None


class ReleaseManifest(BaseModel):
    """Cryptographically signed release manifest describing an immutable OpenRobo release."""

    schema_version: str = "1.0.0"
    release_id: str
    release_version: str
    created_at: str

    stack_id: str | None = None
    workspace_digest: str
    artifact_digest: str

    source_commit_sha: str | None = None
    openrobo_version: str = "0.7.2"

    target: ReleaseTarget
    files: list[FileEntry]

    runtime_contract_digest: str | None = None
    required_capabilities: list[str] = Field(default_factory=list)
    deployment_policy_id: str | None = None
    release_key_id: str


class ReleaseVerificationResult(BaseModel):
    """Structured evidence returned by release verification."""

    status: VerificationStatus
    is_valid: bool
    details: str
    release_id: str | None = None
    manifest_digest: str | None = None
    artifact_digest: str | None = None
    key_id: str | None = None
    failed_files: list[str] = Field(default_factory=list)


class ReleaseSigningKey(BaseModel):
    """Metadata for a release signing keypair."""

    key_id: str
    algorithm: str = "ed25519"
    public_key_pem: str
    created_at: str
    expires_at: str | None = None
    revoked_at: str | None = None
    status: KeyStatus = KeyStatus.ACTIVE


class TrustedReleaseKey(BaseModel):
    """Public release verification key trusted by an agent."""

    key_id: str
    algorithm: str = "ed25519"
    public_key: str = ""  # PEM format
    created_at: str
    expires_at: str | None = None
    revoked_at: str | None = None
    status: KeyStatus = KeyStatus.ACTIVE

    @model_validator(mode="before")
    @classmethod
    def _normalize_pub_key(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "public_key_pem" in data and "public_key" not in data:
                data["public_key"] = data["public_key_pem"]
        return data


class BatteryRequirement(BaseModel):
    """Platform-specific battery constraint for deployment."""

    enabled: bool = False
    threshold_percent: float | None = None
    telemetry_source: str | None = None


class MotionRequirement(BaseModel):
    """Platform-specific motion constraint for deployment."""

    enabled: bool = False
    required_state: str | None = None
    telemetry_source: str | None = None


class EstopRequirement(BaseModel):
    """Platform-specific emergency stop constraint for deployment."""

    enabled: bool = False
    safe_states: list[str] | None = None
    state_source: str | None = None


class DeploymentSafetyPolicy(BaseModel):
    """Configurable safety gate evaluated before staging and activation."""

    policy_id: str = "default-safety"
    platform_type: str = "generic"
    battery_requirement: BatteryRequirement = Field(default_factory=BatteryRequirement)
    motion_requirement: MotionRequirement = Field(default_factory=MotionRequirement)
    estop_requirement: EstopRequirement = Field(default_factory=EstopRequirement)
    custom_runtime_contract: dict[str, Any] = Field(default_factory=dict)
    max_age_seconds: float = 30.0
    on_unknown_state: str = "BLOCK_DEPLOYMENT"


class ExclusionReport(BaseModel):
    """Structured audit report of included and excluded files during release build."""

    included_files: list[str] = Field(default_factory=list)
    excluded_files: list[str] = Field(default_factory=list)
    exclusion_reasons: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
