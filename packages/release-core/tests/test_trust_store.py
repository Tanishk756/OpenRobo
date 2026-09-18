"""Tests for agent-side TrustedReleaseKeyStore."""

from openrobo_release.models import KeyStatus, TrustedReleaseKey
from openrobo_release.trust_store import TrustedReleaseKeyStore


def test_trust_store_lifecycle(tmp_path):
    trust_dir = tmp_path / "trusted_keys"
    store = TrustedReleaseKeyStore(trust_dir=trust_dir)

    key1 = TrustedReleaseKey(
        key_id="key-001",
        public_key="-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAz\n-----END PUBLIC KEY-----",
        created_at="2026-09-18T00:00:00Z",
        status=KeyStatus.ACTIVE,
    )

    store.add_key(key1)
    assert (trust_dir / "key-001.json").exists()

    # Retrieve key
    loaded = store.get_trusted_key("key-001")
    assert loaded is not None
    assert loaded.status == KeyStatus.ACTIVE

    # Revoke key
    store.revoke_key("key-001", revoked_at="2026-09-18T02:00:00Z")
    revoked = store.get_trusted_key("key-001")
    assert revoked.status == KeyStatus.REVOKED
    assert revoked.revoked_at == "2026-09-18T02:00:00Z"

    # Reload in a new store instance
    new_store = TrustedReleaseKeyStore(trust_dir=trust_dir)
    assert len(new_store.list_keys()) == 1
    assert new_store.get_trusted_key("key-001").status == KeyStatus.REVOKED
