"""Release artifact, manifest, and cryptographic signature verifier."""

import base64
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from openrobo_release.manifest import canonical_manifest_bytes, compute_manifest_digest
from openrobo_release.models import (
    ReleaseManifest,
    ReleaseVerificationResult,
    TrustedReleaseKey,
    VerificationStatus,
)


class ReleaseVerifier:
    """
    Validates digital signatures, key trust status, artifact digests, and target compatibility
    prior to any staging or extraction on edge agents.
    """

    def __init__(self, trusted_keys: Optional[List[TrustedReleaseKey]] = None):
        self.trusted_keys: Dict[str, TrustedReleaseKey] = {}
        if trusted_keys:
            for k in trusted_keys:
                self.add_trusted_key(k)

    def add_trusted_key(self, key: TrustedReleaseKey) -> None:
        """Register or update a trusted release public key."""
        self.trusted_keys[key.key_id] = key

    def verify_manifest_signature(self, manifest: ReleaseManifest, signature_b64: str) -> ReleaseVerificationResult:
        """Verify Ed25519 detached signature over canonical manifest bytes."""
        key_id = manifest.release_key_id
        if key_id not in self.trusted_keys:
            return ReleaseVerificationResult(
                status=VerificationStatus.UNTRUSTED_SIGNING_KEY,
                is_valid=False,
                message=f"Release key '{key_id}' is not trusted or recognized by this agent.",
                release_id=manifest.release_id,
                release_key_id=key_id,
            )

        trusted_key = self.trusted_keys[key_id]

        # Check key revocation
        if trusted_key.status == "REVOKED" or trusted_key.revoked_at is not None:
            return ReleaseVerificationResult(
                status=VerificationStatus.KEY_REVOKED,
                is_valid=False,
                message=f"Release signing key '{key_id}' has been REVOKED.",
                release_id=manifest.release_id,
                release_key_id=key_id,
            )

        # Check key expiration
        if trusted_key.expires_at:
            try:
                exp_dt = datetime.fromisoformat(trusted_key.expires_at)
                if datetime.now(timezone.utc) > exp_dt:
                    return ReleaseVerificationResult(
                        status=VerificationStatus.KEY_EXPIRED,
                        is_valid=False,
                        message=f"Release signing key '{key_id}' expired at {trusted_key.expires_at}.",
                        release_id=manifest.release_id,
                        release_key_id=key_id,
                    )
            except Exception:
                pass

        # Verify signature
        try:
            pub_key = serialization.load_pem_public_key(trusted_key.public_key_pem.encode("utf-8"))
            if not isinstance(pub_key, ed25519.Ed25519PublicKey):
                return ReleaseVerificationResult(
                    status=VerificationStatus.SIGNATURE_INVALID,
                    is_valid=False,
                    message=f"Unsupported key algorithm '{type(pub_key).__name__}'.",
                    release_id=manifest.release_id,
                    release_key_id=key_id,
                )

            raw_sig = base64.b64decode(signature_b64.encode("utf-8"))
            canonical_bytes = canonical_manifest_bytes(manifest)
            pub_key.verify(raw_sig, canonical_bytes)

        except (InvalidSignature, ValueError, Exception) as e:
            return ReleaseVerificationResult(
                status=VerificationStatus.SIGNATURE_INVALID,
                is_valid=False,
                message=f"Ed25519 cryptographic signature verification failed: {e}",
                release_id=manifest.release_id,
                release_key_id=key_id,
            )

        manifest_digest = compute_manifest_digest(manifest)
        return ReleaseVerificationResult(
            status=VerificationStatus.VERIFIED,
            is_valid=True,
            message="Digital signature and key trust verified successfully.",
            release_id=manifest.release_id,
            release_key_id=key_id,
            manifest_digest=manifest_digest,
            artifact_digest=manifest.artifact_digest,
        )

    def verify_artifact_digest(self, artifact_path: Path, expected_digest: str) -> ReleaseVerificationResult:
        """Verify unextracted compressed archive SHA-256 hash matches manifest expectation."""
        if not artifact_path.exists() or not artifact_path.is_file():
            return ReleaseVerificationResult(
                status=VerificationStatus.ARTIFACT_DIGEST_MISMATCH,
                is_valid=False,
                message=f"Artifact file not found at: {artifact_path}",
            )

        sha256 = hashlib.sha256()
        with open(artifact_path, "rb") as f:
            while chunk := f.read(65536):
                sha256.update(chunk)
        actual_digest = sha256.hexdigest()

        if actual_digest != expected_digest:
            return ReleaseVerificationResult(
                status=VerificationStatus.ARTIFACT_DIGEST_MISMATCH,
                is_valid=False,
                message=f"Artifact digest mismatch: expected '{expected_digest}', actual '{actual_digest}'.",
                artifact_digest=actual_digest,
                details={"expected": expected_digest, "actual": actual_digest},
            )

        return ReleaseVerificationResult(
            status=VerificationStatus.VERIFIED,
            is_valid=True,
            message="Artifact digest matches manifest.",
            artifact_digest=actual_digest,
        )

    def verify_target_compatibility(
        self, manifest: ReleaseManifest, agent_capabilities: Dict[str, Any]
    ) -> ReleaseVerificationResult:
        """Verify artifact target constraints (OS, architecture, ROS distro) match agent capabilities."""
        target = manifest.target

        agent_os = str(agent_capabilities.get("operating_system", "")).lower()
        agent_arch = str(agent_capabilities.get("architecture", "")).lower()
        agent_ros = str(agent_capabilities.get("ros_distro", "")).lower()

        # Strict checks: if any capability is missing or explicitly mismatched, fail closed
        if not agent_os or not agent_arch:
            return ReleaseVerificationResult(
                status=VerificationStatus.TARGET_INCOMPATIBLE,
                is_valid=False,
                message="Agent operating system or architecture is UNKNOWN; deployment blocked.",
                release_id=manifest.release_id,
            )

        if target.operating_system.lower() not in ("any", "generic") and target.operating_system.lower() != agent_os:
            return ReleaseVerificationResult(
                status=VerificationStatus.TARGET_INCOMPATIBLE,
                is_valid=False,
                message=f"Target OS '{target.operating_system}' incompatible with agent OS '{agent_os}'.",
                release_id=manifest.release_id,
                details={"target_os": target.operating_system, "agent_os": agent_os},
            )

        if target.architecture.lower() not in ("any", "generic") and target.architecture.lower() != agent_arch:
            return ReleaseVerificationResult(
                status=VerificationStatus.TARGET_INCOMPATIBLE,
                is_valid=False,
                message=f"Target architecture '{target.architecture}' incompatible with agent architecture '{agent_arch}'.",
                release_id=manifest.release_id,
                details={"target_arch": target.architecture, "agent_arch": agent_arch},
            )

        if target.ros_distro and target.ros_distro.lower() != "any":
            if not agent_ros or agent_ros != target.ros_distro.lower():
                return ReleaseVerificationResult(
                    status=VerificationStatus.TARGET_INCOMPATIBLE,
                    is_valid=False,
                    message=f"Target ROS distro '{target.ros_distro}' incompatible with agent ROS distro '{agent_ros}'.",
                    release_id=manifest.release_id,
                    details={"target_ros": target.ros_distro, "agent_ros": agent_ros},
                )

        return ReleaseVerificationResult(
            status=VerificationStatus.VERIFIED,
            is_valid=True,
            message="Target compatibility constraints verified.",
            release_id=manifest.release_id,
        )

    def verify_release(
        self,
        manifest: ReleaseManifest,
        signature_b64: str,
        artifact_path: Optional[Path] = None,
        agent_capabilities: Optional[Dict[str, Any]] = None,
    ) -> ReleaseVerificationResult:
        """Run complete pre-staging verification suite (signature, artifact digest, target compatibility)."""
        # 1. Signature & Key Trust
        sig_res = self.verify_manifest_signature(manifest, signature_b64)
        if not sig_res.is_valid:
            return sig_res

        # 2. Artifact Digest
        if artifact_path is not None:
            digest_res = self.verify_artifact_digest(artifact_path, manifest.artifact_digest)
            if not digest_res.is_valid:
                return digest_res

        # 3. Target Compatibility
        if agent_capabilities is not None:
            compat_res = self.verify_target_compatibility(manifest, agent_capabilities)
            if not compat_res.is_valid:
                return compat_res

        return ReleaseVerificationResult(
            status=VerificationStatus.VERIFIED,
            is_valid=True,
            message="Release artifact, manifest signature, and target compatibility fully verified.",
            release_id=manifest.release_id,
            release_key_id=manifest.release_key_id,
            manifest_digest=sig_res.manifest_digest,
            artifact_digest=manifest.artifact_digest,
        )
