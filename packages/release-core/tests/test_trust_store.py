"""Unit tests for TrustedReleaseKeyStore, key validation, and safe persistence."""

from datetime import datetime, timezone

import pytest
from openrobo_release.models import KeyStatus, TrustedReleaseKey
from openrobo_release.trust_store import TrustedReleaseKeyStore, validate_key_id


def test_trust_store_add_and_get(tmp_path):
    trust_dir = tmp_path / "trusted_keys"
    store = TrustedReleaseKeyStore(trust_dir=trust_dir)

    key = TrustedReleaseKey(
        key_id="release-key-2026",
        public_key="dummy-public-key-content",
        created_at="2026-09-18T00:00:00Z",
        status=KeyStatus.ACTIVE,
    )
    store.add_key(key)

    retrieved = store.get_trusted_key("release-key-2026")
    assert retrieved is not None
    assert retrieved.key_id == "release-key-2026"
    assert retrieved.status == KeyStatus.ACTIVE

    # Revoke key
    ok = store.revoke_key("release-key-2026")
    assert ok is True
    revoked = store.get_trusted_key("release-key-2026")
    assert revoked is not None
    assert revoked.status == KeyStatus.REVOKED
    assert revoked.revoked_at is not None
    # Ensure dynamic timestamp is ISO with timezone
    dt = datetime.fromisoformat(revoked.revoked_at)
    assert dt.tzinfo is not None


def test_unsafe_key_id_rejection(tmp_path):
    trust_dir = tmp_path / "trusted_keys"
    store = TrustedReleaseKeyStore(trust_dir=trust_dir)

    unsafe_ids = [
        "../escape",
        "..\\escape",
        "/etc/passwd",
        "\\windows\\system32",
        "key/sub",
        "key\\sub",
        "key\x00null",
        "",
        "a" * 65,  # Exceeds max length
        "key with spaces",
    ]

    for kid in unsafe_ids:
        with pytest.raises(ValueError, match="Invalid or unsafe key_id"):
            validate_key_id(kid)
        with pytest.raises(ValueError, match="Invalid or unsafe key_id"):
            store.add_key(
                TrustedReleaseKey(
                    key_id=kid,
                    public_key="dummy",
                    created_at="2026-09-18T00:00:00Z",
                )
            )
        assert store.get_trusted_key(kid) is None
        with pytest.raises(ValueError, match="Invalid or unsafe key_id"):
            store.revoke_key(kid)


def test_revocation_timestamp_dynamic(tmp_path):
    trust_dir = tmp_path / "trusted_keys"
    store = TrustedReleaseKeyStore(trust_dir=trust_dir)
    store.add_key(
        TrustedReleaseKey(
            key_id="dyn-key-1",
            public_key="dummy",
            created_at="2026-09-18T00:00:00Z",
            status=KeyStatus.ACTIVE,
        )
    )
    ok = store.revoke_key("dyn-key-1")
    assert ok is True
    rev = store.get_trusted_key("dyn-key-1")
    assert rev is not None
    assert rev.revoked_at != "2026-09-18T00:00:00Z"  # Not a static fallback
    dt = datetime.fromisoformat(rev.revoked_at)
    assert dt.tzinfo == timezone.utc or dt.tzinfo is not None
