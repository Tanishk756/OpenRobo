"""Release signing engine using Ed25519 digital signatures and secure key lifecycle management."""

import base64
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple, Union

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from openrobo_release.manifest import canonical_manifest_bytes
from openrobo_release.models import ReleaseManifest, ReleaseSigningKey, TrustedReleaseKey


def set_secure_file_permissions(file_path: Path) -> None:
    """Set secure 0600 (owner read/write only) permissions on sensitive key files."""
    try:
        os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass


class ReleaseSigner:
    """
    Cryptographic authority for signing OpenRobo release manifests using Ed25519.

    In production, release signing operates in secure build/CI environments with strict key gating.
    Development signing is protected behind OPENROBO_DEV_RELEASE_SIGNING=true.
    """

    def __init__(self, private_key_pem: Optional[str] = None, key_id: Optional[str] = None, allow_dev: bool = False):
        self.private_key_pem = private_key_pem
        self.key_id = key_id

        if not allow_dev and not private_key_pem:
            dev_mode = os.environ.get("OPENROBO_DEV_RELEASE_SIGNING", "false").lower() in ("true", "1", "yes")
            if not dev_mode:
                raise PermissionError(
                    "Development release signing is disabled. Set OPENROBO_DEV_RELEASE_SIGNING=true or supply a private key."
                )

    @classmethod
    def generate_keypair(cls, key_id: str, validity_days: int = 365) -> Tuple[ReleaseSigningKey, TrustedReleaseKey]:
        """Generate a new Ed25519 release signing keypair and return (signing_key, trusted_public_key)."""
        priv_key = ed25519.Ed25519PrivateKey.generate()
        pub_key = priv_key.public_key()

        priv_pem = priv_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        pub_pem = pub_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(days=validity_days)).isoformat()

        signing_key = ReleaseSigningKey(
            key_id=key_id,
            algorithm="Ed25519",
            public_key_pem=pub_pem,
            private_key_pem=priv_pem,
            created_at=now.isoformat(),
            expires_at=expires_at,
            status="ACTIVE",
        )

        trusted_key = TrustedReleaseKey(
            key_id=key_id,
            algorithm="Ed25519",
            public_key_pem=pub_pem,
            created_at=now.isoformat(),
            expires_at=expires_at,
            status="ACTIVE",
        )

        return signing_key, trusted_key

    def sign_bytes(self, data: bytes, private_key_pem: Optional[str] = None) -> str:
        """Sign arbitrary raw bytes using Ed25519 and return base64-encoded signature string."""
        pem_to_use = private_key_pem or self.private_key_pem
        if not pem_to_use:
            raise ValueError("No private key available for release signing.")

        priv_key = serialization.load_pem_private_key(pem_to_use.encode("utf-8"), password=None)
        if not isinstance(priv_key, ed25519.Ed25519PrivateKey):
            raise ValueError(f"Expected Ed25519PrivateKey, got {type(priv_key).__name__}")

        raw_sig = priv_key.sign(data)
        return base64.b64encode(raw_sig).decode("utf-8")

    def sign_manifest(self, manifest: Union[ReleaseManifest, dict], private_key_pem: Optional[str] = None) -> str:
        """Canonicalize release manifest and compute detached Ed25519 base64 signature."""
        canonical_bytes = canonical_manifest_bytes(manifest)
        return self.sign_bytes(canonical_bytes, private_key_pem=private_key_pem)
