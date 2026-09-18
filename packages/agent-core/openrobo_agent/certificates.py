"""X.509 Certificate, CSR, and Development CA Utilities using cryptography."""

import abc
import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.x509.oid import NameOID

from openrobo_agent.security import set_secure_file_permissions


def generate_keypair() -> Tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
    """Generate an Ed25519 private/public keypair."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


def private_key_to_pem(private_key: ed25519.Ed25519PrivateKey) -> str:
    """Serialize private key to PEM format."""
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def private_key_from_pem(pem_str: str) -> ed25519.Ed25519PrivateKey:
    """Load an Ed25519 private key from PEM format."""
    key = serialization.load_pem_private_key(
        pem_str.encode("utf-8"),
        password=None,
    )
    if not isinstance(key, ed25519.Ed25519PrivateKey):
        raise ValueError("Loaded key is not an Ed25519 private key")
    return key


def public_key_to_pem(public_key: ed25519.Ed25519PublicKey) -> str:
    """Serialize public key to PEM format."""
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def compute_public_key_fingerprint(public_key: ed25519.Ed25519PublicKey) -> str:
    """Compute SHA-256 fingerprint over DER SubjectPublicKeyInfo."""
    der_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der_bytes).hexdigest()


def create_device_csr(
    private_key: ed25519.Ed25519PrivateKey,
    device_id: str,
    display_name: str = "robot-node",
) -> str:
    """Create a PEM-encoded X.509 Certificate Signing Request (CSR) for a device."""
    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, f"openrobo-device:{device_id}"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "OpenRobo Fleet"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, display_name),
    ])

    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(subject)
        .sign(private_key, None)
    )

    return csr.public_bytes(serialization.Encoding.PEM).decode("utf-8")


def generate_agent_key_and_csr(device_id: str, display_name: str = "robot-node") -> Tuple[str, str]:
    """Convenience helper to generate keypair and CSR returning (private_key_pem, csr_pem)."""
    priv, _ = generate_keypair()
    priv_pem = private_key_to_pem(priv)
    csr_pem = create_device_csr(priv, device_id, display_name)
    return priv_pem, csr_pem


def compute_cert_fingerprint(cert_pem_or_bytes: str | bytes) -> str:
    """Compute SHA-256 fingerprint of an X.509 certificate."""
    if isinstance(cert_pem_or_bytes, str):
        data = cert_pem_or_bytes.encode("utf-8")
    else:
        data = cert_pem_or_bytes

    if b"-----BEGIN CERTIFICATE-----" in data:
        cert = x509.load_pem_x509_certificate(data)
    else:
        cert = x509.load_der_x509_certificate(data)
    return cert.fingerprint(hashes.SHA256()).hex()


compute_certificate_fingerprint = compute_cert_fingerprint


def parse_certificate(cert_pem: str) -> Dict[str, Any]:
    """Parse X.509 certificate into a structured dictionary."""
    cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
    common_names = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    common_name = common_names[0].value if common_names else ""
    device_id = common_name.replace("openrobo-device:", "") if "openrobo-device:" in common_name else common_name

    return {
        "subject_cn": common_name,
        "device_id": device_id,
        "serial_number": format(cert.serial_number, "x"),
        "not_before": cert.not_valid_before_utc.isoformat(),
        "not_after": cert.not_valid_after_utc.isoformat(),
        "fingerprint": cert.fingerprint(hashes.SHA256()).hex(),
        "is_expired": datetime.now(timezone.utc) > cert.not_valid_after_utc,
    }


parse_certificate_info = parse_certificate


def validate_csr_identity(csr_pem: str, expected_device_id: str) -> Tuple[bool, str]:
    """
    Validate CSR signature, algorithm support (Ed25519 / ECDSA), and Common Name device identity binding.
    """
    try:
        csr = x509.load_pem_x509_csr(csr_pem.encode("utf-8"))
    except Exception as e:
        return False, f"Malformed PEM CSR: {e}"

    if not csr.is_signature_valid:
        return False, "CSR cryptographic signature verification failed."

    pub_key = csr.public_key()
    if not isinstance(pub_key, (ed25519.Ed25519PublicKey, ec.EllipticCurvePublicKey)):
        return False, f"Unsupported public key algorithm '{type(pub_key).__name__}'. Only Ed25519 and ECDSA are permitted."

    cns = csr.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    if not cns:
        return False, "CSR Subject must contain a Common Name (CN)."

    cn_val = str(cns[0].value)
    expected_cn = f"openrobo-device:{expected_device_id}"
    if cn_val != expected_cn and cn_val != expected_device_id:
        return False, f"CSR Common Name '{cn_val}' does not match requested device_id '{expected_device_id}'."

    return True, ""


class CertificateAuthority(abc.ABC):
    """Abstract Certificate Authority interface for OpenRobo PKI implementations."""

    @abc.abstractmethod
    def sign_csr(self, csr_pem: str, validity_days: int = 90) -> Tuple[str, str, str, str]:
        """Sign a client CSR and return (cert_pem, serial_hex, fingerprint_hex, expires_at_iso)."""
        pass

    @abc.abstractmethod
    def verify_device_cert(self, cert_pem: str) -> bool:
        """Verify device certificate signature against CA public key."""
        pass

    @property
    @abc.abstractmethod
    def ca_cert_pem(self) -> str:
        """Return root CA certificate in PEM format."""
        pass

    @property
    def ca_certificate_pem(self) -> str:
        return self.ca_cert_pem


class DevelopmentCA(CertificateAuthority):
    """Local Development Certificate Authority for testing and development only.

    NEVER active in production unless OPENROBO_DEV_CA=true is explicitly set.
    Persists CA key and certificate across restarts if ca_dir is configured.
    """

    def __init__(self, ca_dir: Optional[str] = None, allow_test_override: bool = False):
        dev_ca_env = os.environ.get("OPENROBO_DEV_CA", "false").lower() in ("true", "1", "yes")
        env_mode = os.environ.get("ENVIRONMENT", "production").lower()

        if not allow_test_override:
            if env_mode == "production":
                raise RuntimeError("CRITICAL SECURITY: DevelopmentCA cannot be instantiated in production environment.")
            if not dev_ca_env:
                raise PermissionError("Development CA is disabled. Set OPENROBO_DEV_CA=true to initialize development PKI.")

        self.ca_dir = ca_dir
        self.dev_mode_allowed = True

        if self.ca_dir:
            ca_path = Path(self.ca_dir)
            ca_path.mkdir(parents=True, exist_ok=True)
            key_file = ca_path / "ca.key"
            cert_file = ca_path / "ca.crt"

            if key_file.exists() and cert_file.exists():
                # Load persistent CA
                key_pem = key_file.read_text(encoding="utf-8")
                cert_pem = cert_file.read_text(encoding="utf-8")
                self.ca_key = private_key_from_pem(key_pem)
                self.ca_cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
            else:
                self._generate_and_persist(key_file, cert_file)
        else:
            self._generate_ephemeral()

    def _generate_and_persist(self, key_file: Path, cert_file: Path) -> None:
        self.ca_key, public_key = generate_keypair()
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "OpenRobo Development Root CA"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "OpenRobo Dev PKI"),
        ])
        now = datetime.now(timezone.utc)
        self.ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(public_key)
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=365))
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            )
            .sign(self.ca_key, None)
        )

        key_pem = private_key_to_pem(self.ca_key)
        cert_pem = self.ca_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")

        key_file.write_text(key_pem, encoding="utf-8")
        set_secure_file_permissions(key_file)
        cert_file.write_text(cert_pem, encoding="utf-8")

    def _generate_ephemeral(self) -> None:
        self.ca_key, public_key = generate_keypair()
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "OpenRobo Development Root CA"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "OpenRobo Dev PKI"),
        ])
        now = datetime.now(timezone.utc)
        self.ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(public_key)
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=365))
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            )
            .sign(self.ca_key, None)
        )

    @property
    def ca_cert_pem(self) -> str:
        return self.ca_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")

    def sign_csr(self, csr_pem: str, validity_days: int = 90) -> Tuple[str, str, str, str]:
        """Sign a client CSR and return (cert_pem, serial_hex, fingerprint_hex, expires_at_iso)."""
        csr = x509.load_pem_x509_csr(csr_pem.encode("utf-8"))
        if not csr.is_signature_valid:
            raise ValueError("CSR signature verification failed")

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=validity_days)
        serial_num = x509.random_serial_number()

        cert = (
            x509.CertificateBuilder()
            .subject_name(csr.subject)
            .issuer_name(self.ca_cert.subject)
            .public_key(csr.public_key())
            .serial_number(serial_num)
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(expires_at)
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .sign(self.ca_key, None)
        )

        cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
        serial_hex = format(serial_num, "x")
        fingerprint = cert.fingerprint(hashes.SHA256()).hex()

        return cert_pem, serial_hex, fingerprint, expires_at.isoformat()

    def verify_device_cert(self, cert_pem: str) -> bool:
        """Verify device certificate signature against CA public key."""
        try:
            cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
            if datetime.now(timezone.utc) > cert.not_valid_after_utc:
                return False
            self.ca_cert.public_key().verify(
                cert.signature,
                cert.tbs_certificate_bytes,
            )
            return True
        except Exception:
            return False
