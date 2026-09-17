"""Real TLS / mTLS Transport, SSLContext Verification & Reverse Proxy Tests."""

import ssl

import pytest
from openrobo_agent.certificates import (
    DevelopmentCA,
    create_device_csr,
    generate_keypair,
    private_key_to_pem,
)
from openrobo_agent.transport import HttpTransportClient


def test_transport_rejects_insecure_http_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("OPENROBO_ALLOW_INSECURE_HTTP", "false")

    with pytest.raises(RuntimeError, match="Plaintext HTTP endpoint .* is rejected in production"):
        HttpTransportClient(base_url="http://fleet.example.com")


def test_transport_allows_insecure_http_in_development(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    client = HttpTransportClient(base_url="http://localhost:8000")
    assert client is not None


def test_transport_builds_real_ssl_context(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROBO_DEV_CA", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")

    ca_dir = tmp_path / "ca"
    ca = DevelopmentCA(ca_dir=str(ca_dir))

    # Generate device key & cert
    priv, _ = generate_keypair()
    csr = create_device_csr(priv, "device-tls-1")
    cert_pem, _, _, _ = ca.sign_csr(csr)

    ca_cert_file = tmp_path / "ca.crt"
    ca_cert_file.write_text(ca.ca_cert_pem, encoding="utf-8")

    client_key_file = tmp_path / "client.key"
    client_key_file.write_text(private_key_to_pem(priv), encoding="utf-8")

    client_cert_file = tmp_path / "client.crt"
    client_cert_file.write_text(cert_pem, encoding="utf-8")

    client = HttpTransportClient(
        base_url="https://fleet.example.com",
        cert_path=str(client_cert_file),
        key_path=str(client_key_file),
        ca_cert_path=str(ca_cert_file),
    )

    assert client._opener is not None
    assert client.ssl_context is not None

    ctx = client.ssl_context
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2


def test_reverse_proxy_mtls_extraction_security(monkeypatch):
    from fastapi import Request

    from apps.api.services.fleet_security import SecurityIdentityExtractor

    monkeypatch.setenv("OPENROBO_PROXY_CERT_AUTH", "true")
    monkeypatch.setenv("OPENROBO_TRUSTED_PROXIES", "10.0.0.1,127.0.0.1")
    monkeypatch.setenv("ENVIRONMENT", "production")

    extractor = SecurityIdentityExtractor()

    # Case 1: Request from trusted proxy (10.0.0.1) with client fingerprint header -> accepted
    trusted_scope = {
        "type": "http",
        "client": ("10.0.0.1", 54321),
        "headers": [(b"x-ssl-client-fingerprint", b"aabbcc1122334455")],
    }
    req_trusted = Request(trusted_scope)
    fp = extractor.extract_device_fingerprint(req_trusted)
    assert fp == "aabbcc1122334455"

    # Case 2: Request from untrusted external client (198.51.100.25) sending spoofed header -> rejected (None)
    untrusted_scope = {
        "type": "http",
        "client": ("198.51.100.25", 54321),
        "headers": [(b"x-ssl-client-fingerprint", b"spoofed_fingerprint_here")],
    }
    req_untrusted = Request(untrusted_scope)
    fp_untrusted = extractor.extract_device_fingerprint(req_untrusted)
    assert fp_untrusted is None
