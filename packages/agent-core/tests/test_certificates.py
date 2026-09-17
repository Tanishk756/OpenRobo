"""Unit tests for X.509 certificates and development PKI."""

import os

from openrobo_agent.certificates import (
    DevelopmentCA,
    compute_public_key_fingerprint,
    create_device_csr,
    generate_keypair,
    parse_certificate,
    private_key_from_pem,
    private_key_to_pem,
    public_key_to_pem,
)


def test_keypair_generation_and_pem_serialization():
    priv, pub = generate_keypair()
    priv_pem = private_key_to_pem(priv)
    pub_pem = public_key_to_pem(pub)

    assert "-----BEGIN PRIVATE KEY-----" in priv_pem
    assert "-----BEGIN PUBLIC KEY-----" in pub_pem

    # Reload private key
    reloaded_priv = private_key_from_pem(priv_pem)
    assert reloaded_priv is not None

    # Compute public fingerprint
    pub_fp = compute_public_key_fingerprint(pub)
    assert len(pub_fp) == 64


def test_csr_creation_and_signing():
    os.environ["OPENROBO_DEV_CA"] = "true"
    ca = DevelopmentCA()

    priv, _ = generate_keypair()
    device_id = "test-device-uuid-1234"
    csr_pem = create_device_csr(priv, device_id=device_id, display_name="robot-test")

    assert "-----BEGIN CERTIFICATE REQUEST-----" in csr_pem

    cert_pem, serial_hex, fingerprint_hex, expires_at = ca.sign_csr(csr_pem, validity_days=30)
    assert "-----BEGIN CERTIFICATE-----" in cert_pem
    assert len(fingerprint_hex) == 64
    assert len(serial_hex) > 0

    # Parse certificate
    parsed = parse_certificate(cert_pem)
    assert parsed["device_id"] == device_id
    assert parsed["fingerprint"] == fingerprint_hex
    assert not parsed["is_expired"]

    # Verify signature
    assert ca.verify_device_cert(cert_pem) is True
