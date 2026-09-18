"""Verification engine for cryptographic release manifests, signatures, and target compatibility."""

import base64
import hashlib
import platform
from datetime import datetime, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from openrobo_release.manifest import canonical_manifest_bytes
from openrobo_release.models import (
    KeyStatus,
    ReleaseManifest,
    ReleaseVerificationResult,
    TrustedReleaseKey,
    VerificationStatus,
)
from openrobo_release.trust_store import TrustedReleaseKeyStore

ARCH_ALIASES = {
    "x86_64": "x86_64",
    "amd64": "x86_64",
    "x64": "x86_64",
    "aarch64": "aarch64",
    "arm64": "aarch64",
}


def _normalize_arch(arch: str) -> str:
    cleaned = arch.lower().strip()
    return ARCH_ALIASES.get(cleaned, cleaned)


def _parse_iso_datetime(dt_str: str) -> datetime | None:
    """Parses an ISO 8601 datetime string and ensures it is timezone-aware."""
    if not dt_str or not isinstance(dt_str, str):
        return None
    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            return None  # Naive timestamps fail closed
        return dt
    except Exception:
        return None


class ReleaseVerifier:
    """Verifies digital signatures, digests, and target constraints for OpenRobo releases."""

    def __init__(
        self,
        trust_store: TrustedReleaseKeyStore | None = None,
        trusted_keys: list[TrustedReleaseKey] | None = None,
    ) -> None:
        self.trust_store = trust_store
        self.trusted_keys: dict[str, TrustedReleaseKey] = {k.key_id: k for k in trusted_keys} if trusted_keys else {}

    def _resolve_trusted_key(self, key_id: str) -> tuple[TrustedReleaseKey | None, str | None]:
        if key_id in self.trusted_keys:
            return self.trusted_keys[key_id], None

        if not self.trust_store:
            return None, "No trust store configured."

        key = self.trust_store.get_trusted_key(key_id)
        if not key:
            return None, f"Key ID '{key_id}' not found in trusted release key store."

        return key, None

    def verify_manifest_signature(
        self,
        manifest: ReleaseManifest,
        detached_signature_b64: str,
        trusted_key: TrustedReleaseKey | None = None,
    ) -> ReleaseVerificationResult:
        """Verifies an Ed25519 detached signature against a trusted release public key."""
        key_id = manifest.release_key_id

        # Resolve trusted key if not explicitly passed
        if not trusted_key:
            trusted_key, err = self._resolve_trusted_key(key_id)

        if not trusted_key:
            return ReleaseVerificationResult(
                status=VerificationStatus.UNTRUSTED_SIGNING_KEY,
                is_valid=False,
                details=f"Release key ID '{key_id}' is not in the trusted release key store.",
                release_id=manifest.release_id,
                key_id=key_id,
            )

        # Validate metadata timestamps strictly
        if trusted_key.created_at:
            if _parse_iso_datetime(trusted_key.created_at) is None:
                return ReleaseVerificationResult(
                    status=VerificationStatus.KEY_METADATA_INVALID,
                    is_valid=False,
                    details=f"Release key '{key_id}' has invalid/naive created_at timestamp: {trusted_key.created_at}",
                    release_id=manifest.release_id,
                    key_id=key_id,
                )

        if trusted_key.revoked_at:
            rev_dt = _parse_iso_datetime(trusted_key.revoked_at)
            if rev_dt is None:
                return ReleaseVerificationResult(
                    status=VerificationStatus.KEY_METADATA_INVALID,
                    is_valid=False,
                    details=f"Release key '{key_id}' has invalid/naive revoked_at timestamp: {trusted_key.revoked_at}",
                    release_id=manifest.release_id,
                    key_id=key_id,
                )
            # If revoked_at is present, key is revoked regardless of status field
            return ReleaseVerificationResult(
                status=VerificationStatus.REVOKED_SIGNING_KEY,
                is_valid=False,
                details=f"Release key '{key_id}' has been revoked at {trusted_key.revoked_at}.",
                release_id=manifest.release_id,
                key_id=key_id,
            )

        if trusted_key.status == KeyStatus.REVOKED:
            return ReleaseVerificationResult(
                status=VerificationStatus.REVOKED_SIGNING_KEY,
                is_valid=False,
                details=f"Release key '{key_id}' is marked as REVOKED.",
                release_id=manifest.release_id,
                key_id=key_id,
            )

        if trusted_key.status == KeyStatus.EXPIRED:
            return ReleaseVerificationResult(
                status=VerificationStatus.EXPIRED_SIGNING_KEY,
                is_valid=False,
                details=f"Release key '{key_id}' is marked as EXPIRED.",
                release_id=manifest.release_id,
                key_id=key_id,
            )

        if trusted_key.status != KeyStatus.ACTIVE:
            return ReleaseVerificationResult(
                status=VerificationStatus.UNTRUSTED_SIGNING_KEY,
                is_valid=False,
                details=f"Release key '{key_id}' has non-active status '{trusted_key.status}'.",
                release_id=manifest.release_id,
                key_id=key_id,
            )

        if trusted_key.expires_at:
            exp_dt = _parse_iso_datetime(trusted_key.expires_at)
            if exp_dt is None:
                return ReleaseVerificationResult(
                    status=VerificationStatus.KEY_METADATA_INVALID,
                    is_valid=False,
                    details=f"Release key '{key_id}' has invalid/naive expires_at timestamp: {trusted_key.expires_at}",
                    release_id=manifest.release_id,
                    key_id=key_id,
                )
            now = datetime.now(timezone.utc)
            if now > exp_dt:
                return ReleaseVerificationResult(
                    status=VerificationStatus.EXPIRED_SIGNING_KEY,
                    is_valid=False,
                    details=f"Release key '{key_id}' expired at {trusted_key.expires_at}.",
                    release_id=manifest.release_id,
                    key_id=key_id,
                )

        # Load public key
        try:
            pub_key = serialization.load_pem_public_key(trusted_key.public_key.encode("utf-8"))
            if not isinstance(pub_key, ed25519.Ed25519PublicKey):
                return ReleaseVerificationResult(
                    status=VerificationStatus.KEY_METADATA_INVALID,
                    is_valid=False,
                    details=f"Trusted key '{key_id}' is not an Ed25519 public key.",
                    release_id=manifest.release_id,
                    key_id=key_id,
                )
        except Exception as e:
            return ReleaseVerificationResult(
                status=VerificationStatus.KEY_METADATA_INVALID,
                is_valid=False,
                details=f"Failed to parse trusted public key '{key_id}': {e}",
                release_id=manifest.release_id,
                key_id=key_id,
            )

        # Decode signature
        try:
            sig_bytes = base64.b64decode(detached_signature_b64)
        except Exception as e:
            return ReleaseVerificationResult(
                status=VerificationStatus.SIGNATURE_INVALID,
                is_valid=False,
                details=f"Malformed base64 detached signature: {e}",
                release_id=manifest.release_id,
                key_id=key_id,
            )

        # Verify signature
        canonical_bytes = canonical_manifest_bytes(manifest)
        try:
            pub_key.verify(sig_bytes, canonical_bytes)
        except Exception as e:
            return ReleaseVerificationResult(
                status=VerificationStatus.SIGNATURE_INVALID,
                is_valid=False,
                details=f"Cryptographic signature verification failed: {e}",
                release_id=manifest.release_id,
                key_id=key_id,
            )

        return ReleaseVerificationResult(
            status=VerificationStatus.SIGNATURE_VALID,
            is_valid=True,
            details="Manifest signature verified successfully.",
            release_id=manifest.release_id,
            key_id=key_id,
        )

    def verify_artifact_digest(self, artifact_bytes: bytes, manifest: ReleaseManifest) -> ReleaseVerificationResult:
        """Verifies the SHA-256 digest of the archive artifact against manifest.artifact_digest."""
        actual_digest = hashlib.sha256(artifact_bytes).hexdigest()
        if actual_digest != manifest.artifact_digest:
            return ReleaseVerificationResult(
                status=VerificationStatus.ARTIFACT_DIGEST_MISMATCH,
                is_valid=False,
                details=f"Artifact digest mismatch: expected {manifest.artifact_digest}, got {actual_digest}",
                release_id=manifest.release_id,
                artifact_digest=actual_digest,
            )

        return ReleaseVerificationResult(
            status=VerificationStatus.VERIFIED,
            is_valid=True,
            details="Artifact digest verified successfully.",
            release_id=manifest.release_id,
            artifact_digest=actual_digest,
        )

    def verify_target_compatibility(
        self,
        manifest: ReleaseManifest,
        current_os: str | None = None,
        current_arch: str | None = None,
        current_ros_distro: str | None = None,
    ) -> ReleaseVerificationResult:
        """Verifies target OS, architecture, and ROS distribution compatibility."""
        os_name = (current_os or platform.system()).lower()
        arch_name = _normalize_arch(current_arch or platform.machine())

        target = manifest.target
        if target.operating_system.lower() not in (os_name, "any", "all"):
            return ReleaseVerificationResult(
                status=VerificationStatus.TARGET_INCOMPATIBLE,
                is_valid=False,
                details=f"Target OS mismatch: release requires {target.operating_system}, host is {os_name}",
                release_id=manifest.release_id,
            )

        target_arch = _normalize_arch(target.architecture)
        if target_arch not in (arch_name, "any", "all"):
            return ReleaseVerificationResult(
                status=VerificationStatus.TARGET_INCOMPATIBLE,
                is_valid=False,
                details=f"Target architecture mismatch: release requires {target.architecture}, host is {arch_name}",
                release_id=manifest.release_id,
            )

        if target.ros_distro and target.ros_distro.lower() not in ("any", "all", "none", ""):
            if not current_ros_distro:
                return ReleaseVerificationResult(
                    status=VerificationStatus.TARGET_ENVIRONMENT_UNKNOWN,
                    is_valid=False,
                    details=f"Target requires ROS distro '{target.ros_distro}', but host ROS environment is unknown.",
                    release_id=manifest.release_id,
                )
            if target.ros_distro.lower() != current_ros_distro.lower():
                return ReleaseVerificationResult(
                    status=VerificationStatus.TARGET_INCOMPATIBLE,
                    is_valid=False,
                    details=f"Target ROS distro mismatch: release requires {target.ros_distro}, host is {current_ros_distro}",
                    release_id=manifest.release_id,
                )

        return ReleaseVerificationResult(
            status=VerificationStatus.VERIFIED,
            is_valid=True,
            details="Target environment is compatible.",
            release_id=manifest.release_id,
        )
