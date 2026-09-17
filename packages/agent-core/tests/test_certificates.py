"""Unit tests for X.509 certificates, CA gates, persistence, and CSR validation."""

import pytest
from openrobo_agent.certificates import (
    DevelopmentCA,
    compute_public_key_fingerprint,
    create_device_csr,
    generate_keypair,
    parse_certificate,
    private_key_from_pem,
    private_key_to_pem,
    public_key_to_pem,
    validate_csr_identity,
)


def test_keypair_generation_and_pem_serialization():
    priv, pub = generate_keypair()
    priv_pem = private_key_to_pem(priv)
    pub_pem = public_key_to_pem(pub)

    assert "-----BEGIN PRIVATE KEY-----" in priv_pem
    assert "-----BEGIN PUBLIC KEY-----" in pub_pem

    reloaded_priv = private_key_from_pem(priv_pem)
    assert reloaded_priv is not None

    pub_fp = compute_public_key_fingerprint(pub)
    assert len(pub_fp) == 64


def test_development_ca_gate_enforcement(monkeypatch):
    # Case 1: Flag absent
    monkeypatch.delenv("OPENROBO_DEV_CA", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    with pytest.raises(PermissionError, match="Development CA is disabled"):
        DevelopmentCA()

    # Case 2: Flag false
    monkeypatch.setenv("OPENROBO_DEV_CA", "false")
    monkeypatch.setenv("ENVIRONMENT", "development")
    with pytest.raises(PermissionError, match="Development CA is disabled"):
        DevelopmentCA()

    # Case 3: Flag true in production
    monkeypatch.setenv("OPENROBO_DEV_CA", "true")
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(RuntimeError, match="CRITICAL SECURITY: DevelopmentCA cannot be instantiated in production"):
        DevelopmentCA()

    # Case 4: Flag true in development -> Success
    monkeypatch.setenv("OPENROBO_DEV_CA", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    ca = DevelopmentCA()
    assert ca.ca_cert_pem is not None


def test_development_ca_persistence(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROBO_DEV_CA", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")

    ca_dir = tmp_path / "dev_ca"
    ca1 = DevelopmentCA(ca_dir=str(ca_dir))
    ca1_cert = ca1.ca_cert_pem

    priv, _ = generate_keypair()
    csr = create_device_csr(priv, "device-persisted-1")
    cert_pem, _, _, _ = ca1.sign_csr(csr)

    # Re-instantiate CA from same directory -> should reload identical CA key & cert
    ca2 = DevelopmentCA(ca_dir=str(ca_dir))
    assert ca2.ca_cert_pem == ca1_cert

    # Certificate issued by ca1 should verify successfully against reloaded ca2
    assert ca2.verify_device_cert(cert_pem) is True


def test_csr_creation_signing_and_validation(monkeypatch):
    monkeypatch.setenv("OPENROBO_DEV_CA", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    ca = DevelopmentCA()

    priv, _ = generate_keypair()
    device_id = "test-device-uuid-1234"
    csr_pem = create_device_csr(priv, device_id=device_id, display_name="robot-test")

    assert "-----BEGIN CERTIFICATE REQUEST-----" in csr_pem

    # Validate valid CSR identity
    is_valid, err = validate_csr_identity(csr_pem, device_id)
    assert is_valid is True
    assert err == ""

    # Validate CSR mismatch
    is_valid_mismatch, err_mismatch = validate_csr_identity(csr_pem, "other-device-5678")
    assert is_valid_mismatch is False
    assert "does not match" in err_mismatch

    # Sign CSR
    cert_pem, serial_hex, fingerprint_hex, expires_at = ca.sign_csr(csr_pem, validity_days=30)
    assert "-----BEGIN CERTIFICATE-----" in cert_pem
    assert len(fingerprint_hex) == 64
    assert len(serial_hex) > 0

    parsed = parse_certificate(cert_pem)
    assert parsed["device_id"] == device_id
    assert parsed["fingerprint"] == fingerprint_hex
    assert not parsed["is_expired"]

    assert ca.verify_device_cert(cert_pem) is True
