"""Data models for OpenRobo Release Packaging, Verification, and Safety Policies."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ReleaseTarget(BaseModel):
    """Target environment specifications for a release."""
    operating_system: str = Field(default="linux", description="Target OS, e.g., 'linux', 'ubuntu'")
    architecture: str = Field(default="x86_64", description="Target CPU architecture, e.g., 'x86_64', 'aarch64'")
    ros_distro: Optional[str] = Field(default="humble", description="Target ROS 2 distribution, e.g., 'humble', 'iron', 'jazzy'")


class FileEntry(BaseModel):
    """Metadata and integrity hash for an individual packaged file."""
    path: str = Field(..., description="Relative normalized POSIX path within workspace")
    sha256: str = Field(..., description="Hex-encoded SHA-256 digest of file content")
    size_bytes: int = Field(..., ge=0, description="Size of file in bytes")


class ReleaseManifest(BaseModel):
    """Cryptographic manifest describing a deterministic OpenRobo release artifact."""
    schema_version: str = Field(default="openrobo-release-v1", description="Manifest schema version")
    release_id: str = Field(..., description="Unique release identifier (e.g., 'rel_20260918_001')")
    release_version: str = Field(..., description="Semver release version (e.g., '1.0.0')")
    created_at: str = Field(..., description="ISO 8601 UTC timestamp of release creation")
    stack_id: Optional[str] = Field(default=None, description="Source stack identifier")
    workspace_digest: str = Field(..., description="Hex SHA-256 tree digest of uncompressed workspace files")
    artifact_digest: str = Field(..., description="Hex SHA-256 digest of compressed archive (.tar.gz)")
    source_commit_sha: Optional[str] = Field(default=None, description="Source git commit SHA")
    openrobo_version: str = Field(default="0.7.2", description="OpenRobo generator version")
    target: ReleaseTarget = Field(default_factory=ReleaseTarget, description="Target environment constraints")
    files: List[FileEntry] = Field(default_factory=list, description="Ordered list of packaged files and hashes")
    runtime_contract_digest: Optional[str] = Field(default=None, description="Digest of runtime contract requirements")
    required_capabilities: List[str] = Field(default_factory=list, description="List of required hardware/software capabilities")
    deployment_policy_id: Optional[str] = Field(default=None, description="Optional deployment safety policy identifier")
    release_key_id: str = Field(..., description="ID of trusted release key used for signature")


class VerificationStatus(str, Enum):
    """Exhaustive status codes for release artifact verification."""
    VERIFIED = "VERIFIED"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    UNTRUSTED_SIGNING_KEY = "UNTRUSTED_SIGNING_KEY"
    KEY_EXPIRED = "KEY_EXPIRED"
    KEY_REVOKED = "KEY_REVOKED"
    MANIFEST_INVALID = "MANIFEST_INVALID"
    ARTIFACT_DIGEST_MISMATCH = "ARTIFACT_DIGEST_MISMATCH"
    FILE_DIGEST_MISMATCH = "FILE_DIGEST_MISMATCH"
    TARGET_INCOMPATIBLE = "TARGET_INCOMPATIBLE"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"


class ReleaseVerificationResult(BaseModel):
    """Structured evidence returned from release artifact and signature verification."""
    status: VerificationStatus
    is_valid: bool
    message: str
    release_id: Optional[str] = None
    release_key_id: Optional[str] = None
    manifest_digest: Optional[str] = None
    artifact_digest: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class ReleaseSigningKey(BaseModel):
    """Metadata and keys for release signing authorities."""
    key_id: str
    algorithm: str = "Ed25519"
    public_key_pem: str
    private_key_pem: Optional[str] = None
    created_at: str
    expires_at: Optional[str] = None
    revoked_at: Optional[str] = None
    status: str = "ACTIVE"


class TrustedReleaseKey(BaseModel):
    """Public key representation distributed to edge agents for release verification."""
    key_id: str
    algorithm: str = "Ed25519"
    public_key_pem: str
    created_at: str
    expires_at: Optional[str] = None
    revoked_at: Optional[str] = None
    status: str = "ACTIVE"


class DeploymentSafetyPolicy(BaseModel):
    """Platform-specific pre-flight safety policy evaluated prior to deployment staging/activation."""
    platform_type: str = Field(default="generic_robot", description="Robot platform identifier")
    battery_requirement: Optional[Dict[str, Any]] = Field(default=None, description="Battery requirements config")
    motion_requirement: Optional[Dict[str, Any]] = Field(default=None, description="Motion requirements config")
    estop_requirement: Optional[Dict[str, Any]] = Field(default=None, description="E-stop state requirements config")
    custom_runtime_contract: Optional[Dict[str, Any]] = Field(default=None, description="Custom contract constraints")
    on_unknown_state: str = Field(default="BLOCK_DEPLOYMENT", description="Action when telemetry state is unknown")
