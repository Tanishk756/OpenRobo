"""Unit and security tests for release signing, verification engine, and fail-closed metadata."""

import pytest
from openrobo_release.models import (
    FileEntry,
    KeyStatus,
    ReleaseManifest,
    ReleaseTarget,
    TrustedReleaseKey,
    VerificationStatus,
)
from openrobo_release.signing import ReleaseSigner, generate_development_keypair
from openrobo_release.verification import ReleaseVerifier


@pytest.fixture
def sample_manifest() -> ReleaseManifest:
    return ReleaseManifest(
        release_id="rel-test-001",
        release_version="1.0.0",
        created_at="2026-09-18T10:00:00Z",
        workspace_digest="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        artifact_digest="sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        target=ReleaseTarget(operating_system="linux", architecture="x86_64"),
        files=[FileEntry(path="app.py", sha256="dummy", size_bytes=100)],
        release_key_id="test-key-1",
    )


def test_sign_and_verify_success(monkeypatch, sample_manifest):
    monkeypatch.setenv("OPENROBO_DEV_RELEASE_SIGNING", "true")
    key_meta, priv_bytes = generate_development_keypair(key_id="test-key-1")

    signer = ReleaseSigner(priv_bytes, key_id="test-key-1")
    sig = signer.sign_manifest(sample_manifest)

    trusted_key = TrustedReleaseKey(
        key_id="test-key-1",
        public_key=key_meta.public_key_pem,
        created_at="2026-09-18T00:00:00Z",
    )

    verifier = ReleaseVerifier(trusted_keys=[trusted_key])
    res = verifier.verify_manifest_signature(sample_manifest, sig)
    assert res.is_valid is True
    assert res.status == VerificationStatus.SIGNATURE_VALID


def test_tampered_manifest_fails_verification(monkeypatch, sample_manifest):
    monkeypatch.setenv("OPENROBO_DEV_RELEASE_SIGNING", "true")
    key_meta, priv_bytes = generate_development_keypair(key_id="test-key-1")

    signer = ReleaseSigner(priv_bytes, key_id="test-key-1")
    sig = signer.sign_manifest(sample_manifest)

    trusted_key = TrustedReleaseKey(
        key_id="test-key-1",
        public_key=key_meta.public_key_pem,
        created_at="2026-09-18T00:00:00Z",
    )

    tampered_manifest = sample_manifest.model_copy(update={"release_version": "2.0.0"})
    verifier = ReleaseVerifier(trusted_keys=[trusted_key])
    res = verifier.verify_manifest_signature(tampered_manifest, sig)
    assert res.is_valid is False
    assert res.status == VerificationStatus.SIGNATURE_INVALID


def test_revoked_key_fails_verification(monkeypatch, sample_manifest):
    monkeypatch.setenv("OPENROBO_DEV_RELEASE_SIGNING", "true")
    key_meta, priv_bytes = generate_development_keypair(key_id="test-key-1")

    signer = ReleaseSigner(priv_bytes, key_id="test-key-1")
    sig = signer.sign_manifest(sample_manifest)

    revoked_key = TrustedReleaseKey(
        key_id="test-key-1",
        public_key=key_meta.public_key_pem,
        created_at="2026-09-18T00:00:00Z",
        revoked_at="2026-09-18T01:00:00Z",
        status=KeyStatus.REVOKED,
    )

    verifier = ReleaseVerifier(trusted_keys=[revoked_key])
    res = verifier.verify_manifest_signature(sample_manifest, sig)
    assert res.is_valid is False
    assert res.status == VerificationStatus.REVOKED_SIGNING_KEY


def test_active_status_with_revoked_at_fails_closed(monkeypatch, sample_manifest):
    """If revoked_at is populated, key must be treated as revoked even if status is ACTIVE."""
    monkeypatch.setenv("OPENROBO_DEV_RELEASE_SIGNING", "true")
    key_meta, priv_bytes = generate_development_keypair(key_id="test-key-1")
    signer = ReleaseSigner(priv_bytes, key_id="test-key-1")
    sig = signer.sign_manifest(sample_manifest)

    key_with_revocation = TrustedReleaseKey(
        key_id="test-key-1",
        public_key=key_meta.public_key_pem,
        created_at="2026-09-18T00:00:00Z",
        revoked_at="2026-09-18T02:00:00Z",
        status=KeyStatus.ACTIVE,  # Mislabeled as ACTIVE
    )

    verifier = ReleaseVerifier(trusted_keys=[key_with_revocation])
    res = verifier.verify_manifest_signature(sample_manifest, sig)
    assert res.is_valid is False
    assert res.status == VerificationStatus.REVOKED_SIGNING_KEY


def test_expired_key_fails_closed(monkeypatch, sample_manifest):
    monkeypatch.setenv("OPENROBO_DEV_RELEASE_SIGNING", "true")
    key_meta, priv_bytes = generate_development_keypair(key_id="test-key-1")
    signer = ReleaseSigner(priv_bytes, key_id="test-key-1")
    sig = signer.sign_manifest(sample_manifest)

    expired_key = TrustedReleaseKey(
        key_id="test-key-1",
        public_key=key_meta.public_key_pem,
        created_at="2026-09-18T00:00:00Z",
        status=KeyStatus.EXPIRED,
    )

    verifier = ReleaseVerifier(trusted_keys=[expired_key])
    res = verifier.verify_manifest_signature(sample_manifest, sig)
    assert res.is_valid is False
    assert res.status == VerificationStatus.EXPIRED_SIGNING_KEY


def test_invalid_key_metadata_fails_closed(monkeypatch, sample_manifest):
    monkeypatch.setenv("OPENROBO_DEV_RELEASE_SIGNING", "true")
    key_meta, priv_bytes = generate_development_keypair(key_id="test-key-1")

    signer = ReleaseSigner(priv_bytes, key_id="test-key-1")
    sig = signer.sign_manifest(sample_manifest)

    # Unparseable expires_at timestamp
    invalid_key = TrustedReleaseKey(
        key_id="test-key-1",
        public_key=key_meta.public_key_pem,
        created_at="2026-09-18T00:00:00Z",
        expires_at="not-a-timestamp",
        status=KeyStatus.ACTIVE,
    )

    verifier = ReleaseVerifier(trusted_keys=[invalid_key])
    res = verifier.verify_manifest_signature(sample_manifest, sig)
    assert res.is_valid is False
    assert res.status == VerificationStatus.KEY_METADATA_INVALID


def test_naive_timestamp_fails_closed(monkeypatch, sample_manifest):
    monkeypatch.setenv("OPENROBO_DEV_RELEASE_SIGNING", "true")
    key_meta, priv_bytes = generate_development_keypair(key_id="test-key-1")
    signer = ReleaseSigner(priv_bytes, key_id="test-key-1")
    sig = signer.sign_manifest(sample_manifest)

    # Naive timestamp (no UTC timezone offset)
    naive_key = TrustedReleaseKey(
        key_id="test-key-1",
        public_key=key_meta.public_key_pem,
        created_at="2026-09-18T10:00:00",
        status=KeyStatus.ACTIVE,
    )

    verifier = ReleaseVerifier(trusted_keys=[naive_key])
    res = verifier.verify_manifest_signature(sample_manifest, sig)
    assert res.is_valid is False
    assert res.status == VerificationStatus.KEY_METADATA_INVALID


def test_target_compatibility_arch_normalization(sample_manifest):
    verifier = ReleaseVerifier()

    # x86_64 vs amd64
    man_amd64 = sample_manifest.model_copy(
        update={"target": ReleaseTarget(operating_system="linux", architecture="amd64")}
    )
    res = verifier.verify_target_compatibility(man_amd64, current_os="Linux", current_arch="x86_64")
    assert res.is_valid is True

    # aarch64 vs arm64
    man_arm64 = sample_manifest.model_copy(
        update={"target": ReleaseTarget(operating_system="linux", architecture="arm64")}
    )
    res = verifier.verify_target_compatibility(man_arm64, current_os="Linux", current_arch="aarch64")
    assert res.is_valid is True


def test_target_compatibility_ros_distro_unknown_fails_closed(sample_manifest):
    verifier = ReleaseVerifier()
    man_ros = sample_manifest.model_copy(
        update={"target": ReleaseTarget(operating_system="any", architecture="any", ros_distro="humble")}
    )

    # Unknown host ROS environment
    res = verifier.verify_target_compatibility(man_ros, current_ros_distro=None)
    assert res.is_valid is False
    assert res.status == VerificationStatus.TARGET_ENVIRONMENT_UNKNOWN

    # Matching host ROS environment
    res_ok = verifier.verify_target_compatibility(man_ros, current_ros_distro="humble")
    assert res_ok.is_valid is True
