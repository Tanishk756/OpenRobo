"""Cryptographic and integrity verification of OpenRobo release manifests and artifacts."""

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


def _parse_iso_datetime(dt_str: str) -> datetime | None:
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


class ReleaseVerifier:
    """Verifies cryptographic signatures, digests, and target compatibility of release manifests."""

    def __init__(
        self,
        trust_store: TrustedReleaseKeyStore | None = None,
        trusted_keys: list[TrustedReleaseKey] | None = None,
    ) -> None:
        self.trust_store = trust_store
        self._trusted_keys: dict[str, TrustedReleaseKey] = {}

        if trusted_keys:
            for k in trusted_keys:
                self._trusted_keys[k.key_id] = k

    def get_trusted_key(self, key_id: str) -> TrustedReleaseKey | None:
        if key_id in self._trusted_keys:
            return self._trusted_keys[key_id]
        if self.trust_store:
            return self.trust_store.get_trusted_key(key_id)
        return None

    def verify_manifest_signature(self, manifest: ReleaseManifest, detached_signature_b64: str) -> ReleaseVerificationResult:
        """Verifies the Ed25519 detached signature of a manifest against trusted keys with strict fail-closed metadata checks."""
        key_id = manifest.release_key_id
        trusted_key = self.get_trusted_key(key_id)
        if not trusted_key:
            return ReleaseVerificationResult(
                status=VerificationStatus.UNTRUSTED_SIGNING_KEY,
                is_valid=False,
                details=f"Release key ID '{key_id}' is not in the trusted release key store.",
                release_id=manifest.release_id,
                key_id=key_id,
            )

        if trusted_key.status == KeyStatus.REVOKED:
            return ReleaseVerificationResult(
                status=VerificationStatus.REVOKED_SIGNING_KEY,
                is_valid=False,
                details=f"Release key '{key_id}' has been revoked at {trusted_key.revoked_at}.",
                release_id=manifest.release_id,
                key_id=key_id,
            )

        # Validate metadata timestamps strictly
        if trusted_key.created_at:
            if _parse_iso_datetime(trusted_key.created_at) is None:
                return ReleaseVerificationResult(
                    status=VerificationStatus.KEY_METADATA_INVALID,
                    is_valid=False,
                    details=f"Release key '{key_id}' has unparseable created_at timestamp: {trusted_key.created_at}",
                    release_id=manifest.release_id,
                    key_id=key_id,
                )

        if trusted_key.revoked_at:
            if _parse_iso_datetime(trusted_key.revoked_at) is None:
                return ReleaseVerificationResult(
                    status=VerificationStatus.KEY_METADATA_INVALID,
                    is_valid=False,
                    details=f"Release key '{key_id}' has unparseable revoked_at timestamp: {trusted_key.revoked_at}",
                    release_id=manifest.release_id,
                    key_id=key_id,
                )

        if trusted_key.expires_at:
            exp_dt = _parse_iso_datetime(trusted_key.expires_at)
            if exp_dt is None:
                return ReleaseVerificationResult(
                    status=VerificationStatus.KEY_METADATA_INVALID,
                    is_valid=False,
                    details=f"Release key '{key_id}' has unparseable expires_at timestamp: {trusted_key.expires_at}",
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
        arch_name = (current_arch or platform.machine()).lower()

        target = manifest.target
        if target.operating_system.lower() not in (os_name, "any", "all"):
            return ReleaseVerificationResult(
                status=VerificationStatus.TARGET_INCOMPATIBLE,
                is_valid=False,
                details=f"Target OS mismatch: release requires {target.operating_system}, host is {os_name}",
                release_id=manifest.release_id,
            )

        target_arch = target.architecture.lower()
        if target_arch not in (arch_name, "any", "all"):
            # Handle x86_64 / amd64 aliases
            x86_aliases = ("x86_64", "amd64")
            if not (target_arch in x86_aliases and arch_name in x86_aliases):
                return ReleaseVerificationResult(
                    status=VerificationStatus.TARGET_INCOMPATIBLE,
                    is_valid=False,
                    details=f"Target architecture mismatch: release requires {target.architecture}, host is {arch_name}",
                    release_id=manifest.release_id,
                )

        if target.ros_distro and current_ros_distro:
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
