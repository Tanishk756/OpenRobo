"""OpenRobo Device Identity & Keypair Management."""

import json
import os
import platform
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives.asymmetric import ed25519

from openrobo_agent.certificates import (
    compute_cert_fingerprint,
    compute_public_key_fingerprint,
    create_device_csr,
    generate_keypair,
    parse_certificate,
    private_key_from_pem,
    private_key_to_pem,
)
from openrobo_agent.config import AgentConfig
from openrobo_agent.models import DeviceIdentity
from openrobo_agent.security import set_secure_file_permissions, validate_file_permissions


class DeviceIdentityManager:
    """Manages on-device cryptographic identity, keypairs, and certificates."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.config.ensure_directories()
        self._private_key: Optional[ed25519.Ed25519PrivateKey] = None
        self._public_key: Optional[ed25519.Ed25519PublicKey] = None
        self._device_id: Optional[str] = config.device_id
        self._load_or_initialize()

    @property
    def device_id(self) -> str:
        if not self._device_id:
            self._device_id = str(uuid.uuid4())
        return self._device_id

    @property
    def key_path(self) -> Path:
        return self.config.key_path

    @property
    def cert_path(self) -> Path:
        return self.config.cert_path

    @property
    def ca_cert_path(self) -> Path:
        return self.config.ca_cert_path

    @property
    def private_key(self) -> ed25519.Ed25519PrivateKey:
        if self._private_key is None:
            self._load_or_initialize()
        return self._private_key  # type: ignore

    @property
    def public_key(self) -> ed25519.Ed25519PublicKey:
        if self._public_key is None:
            self._load_or_initialize()
        return self._public_key  # type: ignore

    def _load_or_initialize(self) -> None:
        """Load existing private key and identity or generate a new local keypair."""
        if self.config.key_path.exists():
            if not validate_file_permissions(self.config.key_path, 0o600):
                set_secure_file_permissions(self.config.key_path, 0o600)

            pem_content = self.config.key_path.read_text(encoding="utf-8")
            self._private_key = private_key_from_pem(pem_content)
            self._public_key = self._private_key.public_key()
        else:
            self._private_key, self._public_key = generate_keypair()
            pem_str = private_key_to_pem(self._private_key)
            self.config.key_path.write_text(pem_str, encoding="utf-8")
            set_secure_file_permissions(self.config.key_path, 0o600)

        if self.config.identity_path.exists():
            try:
                data = json.loads(self.config.identity_path.read_text(encoding="utf-8"))
                if "device_id" in data and not self._device_id:
                    self._device_id = data["device_id"]
                if "display_name" in data and data["display_name"]:
                    self.config.display_name = data["display_name"]
            except Exception:
                pass

        if not self._device_id:
            self._device_id = str(uuid.uuid4())

        self._save_identity_metadata()

    def _save_identity_metadata(self) -> None:
        """Persist identity metadata to identity.json."""
        identity = self.get_identity()
        self.config.identity_path.write_text(identity.model_dump_json(indent=2), encoding="utf-8")

    def get_or_create_identity(self, display_name: Optional[str] = None) -> DeviceIdentity:
        if display_name:
            self.config.display_name = display_name
        self._save_identity_metadata()
        return self.get_identity()

    def load_identity(self) -> DeviceIdentity:
        return self.get_identity()

    def get_certificate_info(self) -> Optional[Dict[str, Any]]:
        if not self.config.cert_path.exists():
            return None
        try:
            return parse_certificate(self.config.cert_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def create_csr(self) -> str:
        """Generate a Certificate Signing Request with the device UUID."""
        return create_device_csr(self.private_key, self.device_id, self.config.display_name)

    def save_enrolled_certificate(self, cert_pem: str, ca_cert_pem: str) -> None:
        """Store the signed device certificate and CA certificate."""
        self.config.cert_path.write_text(cert_pem, encoding="utf-8")
        set_secure_file_permissions(self.config.cert_path, 0o644)

        self.config.ca_cert_path.write_text(ca_cert_pem, encoding="utf-8")
        set_secure_file_permissions(self.config.ca_cert_path, 0o644)

        self._save_identity_metadata()

    def enroll(self, token: str, capabilities: Optional[List[Any]] = None) -> DeviceIdentity:
        import httpx
        csr_pem = self.create_csr()
        url = self.config.control_plane_url.rstrip("/")
        res = httpx.post(f"{url}/api/v1/fleet/enroll", json={
            "enrollment_token": token,
            "device_id": self.device_id,
            "device_name": self.config.display_name,
            "csr_pem": csr_pem,
            "capabilities": capabilities or [],
        })
        if res.status_code != 200:
            raise RuntimeError(f"Enrollment failed ({res.status_code}): {res.text}")
        data = res.json()
        self.save_enrolled_certificate(data["certificate_pem"], data.get("ca_certificate_pem", ""))
        return self.get_identity()

    def is_enrolled(self) -> bool:
        """Check whether valid device certificate and CA certificate exist."""
        if not self.config.cert_path.exists() or not self.config.ca_cert_path.exists():
            return False
        try:
            cert_info = parse_certificate(self.config.cert_path.read_text(encoding="utf-8"))
            return not cert_info.get("is_expired", True)
        except Exception:
            return False

    def get_identity(self) -> DeviceIdentity:
        """Assemble current DeviceIdentity model."""
        pub_fp = compute_public_key_fingerprint(self.public_key)
        cert_fp = None
        cert_serial = None

        if self.config.cert_path.exists():
            try:
                cert_pem = self.config.cert_path.read_text(encoding="utf-8")
                cert_fp = compute_cert_fingerprint(cert_pem)
                cert_info = parse_certificate(cert_pem)
                cert_serial = cert_info.get("serial_number")
            except Exception:
                pass

        os_name = f"{platform.system()} {platform.release()}"
        if os.path.exists("/etc/os-release"):
            try:
                with open("/etc/os-release") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            os_name = line.strip().split("=", 1)[1].strip('"')
                            break
            except Exception:
                pass

        return DeviceIdentity(
            device_id=self.device_id,
            display_name=self.config.display_name,
            public_key_fingerprint=pub_fp,
            certificate_fingerprint=cert_fp,
            certificate_serial=cert_serial,
            platform=platform.system().lower(),
            architecture=platform.machine(),
            os_name=os_name,
            agent_version="0.7.0",
        )
