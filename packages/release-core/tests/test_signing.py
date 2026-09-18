"""Tests for Ed25519 release signing, dev key gates, and private key validation."""

import pytest
from openrobo_release.models import (
    FileEntry,
    KeyStatus,
    ReleaseManifest,
    ReleaseTarget,
    TrustedReleaseKey,
    VerificationStatus,
)
from openrobo_release.signing import (
    ReleaseSigner,
    generate_development_keypair,
    validate_private_key_file,
)
from openrobo_release.verification import ReleaseVerifier


@pytest.fixture
def sample_manifest() -> ReleaseManifest:
    return ReleaseManifest(
        release_id="rel-test-001",
        release_version="1.0.0",
        created_at="2026-09-18T10:00:00Z",
        workspace_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
        artifact_digest="2222222222222222222222222222222222222222222222222222222222222222",
        target=ReleaseTarget(operating_system="linux", architecture="x86_64"),
        files=[FileEntry(path="src/main.py", sha256="abc", size_bytes=100)],
        release_key_id="test-key-1",
    )


def test_dev_signing_gate_enforcement(monkeypatch):
    monkeypatch.delenv("OPENROBO_DEV_RELEASE_SIGNING", raising=False)
    with pytest.raises(PermissionError, match="OPENROBO_DEV_RELEASE_SIGNING=true"):
        generate_development_keypair()

    monkeypatch.setenv("OPENROBO_DEV_RELEASE_SIGNING", "false")
    with pytest.raises(PermissionError):
        generate_development_keypair()

    monkeypatch.setenv("OPENROBO_DEV_RELEASE_SIGNING", "true")
    key_meta, priv_bytes = generate_development_keypair(key_id="dev-123")
    assert key_meta.key_id == "dev-123"
    assert b"PRIVATE KEY" in priv_bytes


def test_validate_private_key_file(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROBO_DEV_RELEASE_SIGNING", "true")
    _, priv_bytes = generate_development_keypair(key_id="valid-key")

    key_file = tmp_path / "valid.key"
    key_file.write_bytes(priv_bytes)

    # Valid key
    validate_private_key_file(key_file)

    # Missing file
    with pytest.raises(FileNotFoundError):
        validate_private_key_file(tmp_path / "nonexistent.key")

    # Corrupt key bytes
    bad_key = tmp_path / "bad.key"
    bad_key.write_bytes(b"not a private key")
    with pytest.raises(ValueError, match="Failed to parse"):
        validate_private_key_file(bad_key)


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
