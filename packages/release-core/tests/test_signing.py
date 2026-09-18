"""Unit tests for Ed25519 Release Signing and Verification."""

from datetime import datetime, timedelta, timezone

import pytest
from openrobo_release import (
    FileEntry,
    ReleaseManifest,
    ReleaseSigner,
    ReleaseTarget,
    ReleaseVerifier,
    VerificationStatus,
)


@pytest.fixture
def sample_manifest() -> ReleaseManifest:
    return ReleaseManifest(
        release_id="rel_20260918_test",
        release_version="1.0.0",
        created_at=datetime.now(timezone.utc).isoformat(),
        workspace_digest="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        artifact_digest="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        target=ReleaseTarget(operating_system="linux", architecture="x86_64", ros_distro="humble"),
        files=[FileEntry(path="main.py", sha256="1111111111111111111111111111111111111111111111111111111111111111", size_bytes=50)],
        release_key_id="rel-test-key-01",
    )


def test_ed25519_sign_and_verify_success(sample_manifest):
    """Prove that a validly signed manifest verifies successfully against trusted public key."""
    sign_key, trust_key = ReleaseSigner.generate_keypair(key_id=sample_manifest.release_key_id)
    signer = ReleaseSigner(private_key_pem=sign_key.private_key_pem, key_id=sign_key.key_id, allow_dev=True)

    sig_b64 = signer.sign_manifest(sample_manifest)
    assert isinstance(sig_b64, str)
    assert len(sig_b64) > 30

    verifier = ReleaseVerifier(trusted_keys=[trust_key])
    result = verifier.verify_manifest_signature(sample_manifest, sig_b64)

    assert result.is_valid is True
    assert result.status == VerificationStatus.VERIFIED
    assert result.release_id == sample_manifest.release_id


def test_tampered_manifest_rejected(sample_manifest):
    """Prove that altering any field of the signed manifest fails verification."""
    sign_key, trust_key = ReleaseSigner.generate_keypair(key_id=sample_manifest.release_key_id)
    signer = ReleaseSigner(private_key_pem=sign_key.private_key_pem, key_id=sign_key.key_id, allow_dev=True)

    sig_b64 = signer.sign_manifest(sample_manifest)
    verifier = ReleaseVerifier(trusted_keys=[trust_key])

    # Tamper with workspace digest
    tampered_manifest = sample_manifest.model_copy(
        update={"workspace_digest": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"}
    )
    result = verifier.verify_manifest_signature(tampered_manifest, sig_b64)

    assert result.is_valid is False
    assert result.status == VerificationStatus.SIGNATURE_INVALID


def test_tampered_signature_rejected(sample_manifest):
    """Prove that corrupted signature string fails verification."""
    sign_key, trust_key = ReleaseSigner.generate_keypair(key_id=sample_manifest.release_key_id)
    verifier = ReleaseVerifier(trusted_keys=[trust_key])

    result = verifier.verify_manifest_signature(sample_manifest, "invalid_base64_sig_bytes==")
    assert result.is_valid is False
    assert result.status == VerificationStatus.SIGNATURE_INVALID


def test_untrusted_signing_key_rejected(sample_manifest):
    """Prove that key_id not present in agent trusted keys fails verification."""
    sign_key, _ = ReleaseSigner.generate_keypair(key_id="untrusted-key-999")
    sample_manifest.release_key_id = "untrusted-key-999"

    signer = ReleaseSigner(private_key_pem=sign_key.private_key_pem, key_id=sign_key.key_id, allow_dev=True)
    sig_b64 = signer.sign_manifest(sample_manifest)

    # Empty verifier has no trusted keys
    verifier = ReleaseVerifier(trusted_keys=[])
    result = verifier.verify_manifest_signature(sample_manifest, sig_b64)

    assert result.is_valid is False
    assert result.status == VerificationStatus.UNTRUSTED_SIGNING_KEY


def test_revoked_key_rejected(sample_manifest):
    """Prove that revoked signing key fails verification even if signature is valid."""
    sign_key, trust_key = ReleaseSigner.generate_keypair(key_id=sample_manifest.release_key_id)
    signer = ReleaseSigner(private_key_pem=sign_key.private_key_pem, key_id=sign_key.key_id, allow_dev=True)
    sig_b64 = signer.sign_manifest(sample_manifest)

    # Revoke key
    trust_key.status = "REVOKED"
    trust_key.revoked_at = datetime.now(timezone.utc).isoformat()

    verifier = ReleaseVerifier(trusted_keys=[trust_key])
    result = verifier.verify_manifest_signature(sample_manifest, sig_b64)

    assert result.is_valid is False
    assert result.status == VerificationStatus.KEY_REVOKED


def test_expired_key_rejected(sample_manifest):
    """Prove that expired signing key fails verification."""
    sign_key, trust_key = ReleaseSigner.generate_keypair(key_id=sample_manifest.release_key_id)
    signer = ReleaseSigner(private_key_pem=sign_key.private_key_pem, key_id=sign_key.key_id, allow_dev=True)
    sig_b64 = signer.sign_manifest(sample_manifest)

    # Set expiration in past
    trust_key.expires_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    verifier = ReleaseVerifier(trusted_keys=[trust_key])
    result = verifier.verify_manifest_signature(sample_manifest, sig_b64)

    assert result.is_valid is False
    assert result.status == VerificationStatus.KEY_EXPIRED
