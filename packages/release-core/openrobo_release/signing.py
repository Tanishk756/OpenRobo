"""Cryptographic signing of OpenRobo release manifests using Ed25519."""

import base64
import os
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from openrobo_release.manifest import canonical_manifest_bytes
from openrobo_release.models import KeyStatus, ReleaseManifest, ReleaseSigningKey


def validate_private_key_file(path: Path | str) -> None:
    """Validates that a private key file exists, is regular, has safe permissions, and contains valid Ed25519 bytes."""
    key_path = Path(path)
    if not key_path.exists():
        raise FileNotFoundError(f"Private key file does not exist: {key_path}")
    if not key_path.is_file():
        raise ValueError(f"Private key path must be a regular file: {key_path}")
    if key_path.is_symlink():
        raise ValueError(f"Private key path must not be a symlink: {key_path}")

    size = key_path.stat().st_size
    if size == 0 or size > 100 * 1024:
        raise ValueError(f"Private key file size invalid ({size} bytes)")

    # POSIX permissions check
    if os.name != "nt":
        mode = key_path.stat().st_mode
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            import warnings

            warnings.warn(f"Private key file {key_path} has loose permissions ({oct(mode)}). Recommended: 0600.")

    # Try loading as Ed25519
    with open(key_path, "rb") as f:
        raw = f.read()
    try:
        key = serialization.load_pem_private_key(raw, password=None)
        if not isinstance(key, ed25519.Ed25519PrivateKey):
            raise ValueError("Private key is not an Ed25519 private key.")
    except Exception as e:
        raise ValueError(f"Failed to parse Ed25519 private key: {e}") from e


def generate_development_keypair(key_id: str | None = None) -> tuple[ReleaseSigningKey, bytes]:
    """Generates a development release signing keypair when OPENROBO_DEV_RELEASE_SIGNING=true."""
    dev_gate = os.environ.get("OPENROBO_DEV_RELEASE_SIGNING", "").lower()
    if dev_gate not in ("true", "1", "yes"):
        raise PermissionError(
            "Development release signing key generation requires OPENROBO_DEV_RELEASE_SIGNING=true. "
            "Implicit key generation is disabled in production."
        )

    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()

    priv_bytes = priv_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    pub_bytes = pub_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    actual_key_id = key_id or f"dev-key-{uuid.uuid4().hex[:8]}"
    now_str = datetime.now(timezone.utc).isoformat()

    signing_key = ReleaseSigningKey(
        key_id=actual_key_id,
        algorithm="ed25519",
        public_key_pem=pub_bytes.decode("utf-8"),
        created_at=now_str,
        status=KeyStatus.ACTIVE,
    )

    return signing_key, priv_bytes


class ReleaseSigner:
    """Signs release manifests using an Ed25519 private key."""

    def __init__(self, private_key_pem: bytes | str, key_id: str) -> None:
        self.key_id = key_id
        if isinstance(private_key_pem, str):
            private_key_pem = private_key_pem.encode("utf-8")

        self._private_key = serialization.load_pem_private_key(private_key_pem, password=None)
        if not isinstance(self._private_key, ed25519.Ed25519PrivateKey):
            raise ValueError("ReleaseSigner requires an Ed25519 private key.")

    def sign_manifest(self, manifest: ReleaseManifest) -> str:
        """Signs the canonical bytes of a release manifest and returns base64 detached signature."""
        if manifest.release_key_id != self.key_id:
            raise ValueError(f"Manifest release_key_id ({manifest.release_key_id}) does not match signer key_id ({self.key_id}).")

        canonical_bytes = canonical_manifest_bytes(manifest)
        signature = self._private_key.sign(canonical_bytes)
        return base64.b64encode(signature).decode("utf-8")

    @classmethod
    def generate_keypair(cls, key_id: str | None = None, *, allow_development: bool = False) -> tuple[ReleaseSigningKey, bytes]:
        """Explicitly generates a signing keypair. Enforces development gate if allow_development=True."""
        if not allow_development:
            dev_gate = os.environ.get("OPENROBO_DEV_RELEASE_SIGNING", "").lower()
            if dev_gate not in ("true", "1", "yes"):
                raise PermissionError(
                    "Automatic release key generation is disabled in production. "
                    "Provide an explicit signing authority or set OPENROBO_DEV_RELEASE_SIGNING=true."
                )
        return generate_development_keypair(key_id=key_id)
