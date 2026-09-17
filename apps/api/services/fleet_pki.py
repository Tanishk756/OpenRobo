import os
from datetime import datetime, timezone
from typing import Optional, Tuple

from cryptography import x509
from openrobo_agent.certificates import DevelopmentCA, compute_certificate_fingerprint


class FleetPKIService:
    """
    Fleet PKI Service managing certificate issuance, verification, and revocation.
    Uses the mature third-party cryptography package.
    Gated behind explicit OPENROBO_DEV_CA=true configuration.
    """

    def __init__(self, dev_ca_dir: Optional[str] = None):
        self.is_dev_ca_enabled = os.getenv("OPENROBO_DEV_CA", "false").lower() in ("true", "1", "yes")
        env_mode = os.getenv("ENVIRONMENT", "development").lower()

        if env_mode == "production" and self.is_dev_ca_enabled:
            # Production safeguard
            raise RuntimeError("CRITICAL SECURITY: OPENROBO_DEV_CA cannot be enabled in production environment.")

        self.dev_ca_dir = dev_ca_dir or os.path.join(os.getcwd(), ".openrobo", "ca")
        self._ca: Optional[DevelopmentCA] = None

    def _get_ca(self) -> DevelopmentCA:
        if not self.is_dev_ca_enabled:
            raise PermissionError(
                "Development CA is disabled. Set OPENROBO_DEV_CA=true or configure production mTLS PKI."
            )
        if self._ca is None:
            self._ca = DevelopmentCA(ca_dir=self.dev_ca_dir)
        return self._ca

    def sign_csr(self, csr_pem: str, validity_days: int = 365) -> Tuple[str, str, str]:
        """
        Sign an agent CSR using the CA.
        Returns: (cert_pem, fingerprint, serial_number)
        """
        ca = self._get_ca()
        res = ca.sign_csr(csr_pem, validity_days=validity_days)
        if len(res) == 4:
            cert_pem, serial_hex, fingerprint_hex, expires_at_iso = res
            return cert_pem, fingerprint_hex, serial_hex
        elif len(res) == 3:
            return res[0], res[1], res[2]
        else:
            cert_pem = res[0]
            cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
            fingerprint = compute_certificate_fingerprint(cert_pem)
            serial_number = str(cert.serial_number)
            return cert_pem, fingerprint, serial_number

    def verify_cert_validity(self, cert_pem: str) -> bool:
        """
        Check whether the certificate is within its valid date range.
        """
        try:
            cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
            now = datetime.now(timezone.utc)
            if now < cert.not_valid_before_utc or now > cert.not_valid_after_utc:
                return False
            return True
        except Exception:
            return False


_global_pki_service: Optional[FleetPKIService] = None


def get_fleet_pki_service() -> FleetPKIService:
    global _global_pki_service
    if _global_pki_service is None:
        _global_pki_service = FleetPKIService()
    return _global_pki_service
