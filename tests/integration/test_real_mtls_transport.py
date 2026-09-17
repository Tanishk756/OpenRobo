"""Real Network-Level mTLS Transport Acceptance, Handshake Verification & Concurrency Tests."""

import concurrent.futures
import hashlib
import http.server
import ipaddress
import json
import socket
import ssl
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Tuple

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.x509.oid import NameOID
from openrobo_agent.certificates import (
    compute_cert_fingerprint,
    generate_keypair,
    private_key_to_pem,
)
from openrobo_agent.config import AgentConfig
from openrobo_agent.models import MessageEnvelope
from openrobo_agent.service import AgentDaemon
from openrobo_agent.transport import HttpTransportClient


def create_test_ca(common_name: str = "Test Root CA") -> Tuple[ed25519.Ed25519PrivateKey, x509.Certificate]:
    priv, pub = generate_keypair()
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "OpenRobo Test"),
    ])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(pub)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(priv, None)
    )
    return priv, cert


def create_signed_server_cert(
    ca_key: ed25519.Ed25519PrivateKey,
    ca_cert: x509.Certificate,
    hostname: str = "localhost",
    ip: str = "127.0.0.1",
) -> Tuple[ed25519.Ed25519PrivateKey, x509.Certificate]:
    priv, pub = generate_keypair()
    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "OpenRobo Test Server"),
    ])
    now = datetime.now(timezone.utc)
    san = x509.SubjectAlternativeName([
        x509.DNSName(hostname),
        x509.IPAddress(ipaddress.ip_address(ip)),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(pub)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(san, critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(ca_key, None)
    )
    return priv, cert


def create_signed_client_cert(
    ca_key: ed25519.Ed25519PrivateKey,
    ca_cert: x509.Certificate,
    device_id: str,
) -> Tuple[ed25519.Ed25519PrivateKey, x509.Certificate]:
    priv, pub = generate_keypair()
    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, f"openrobo-device:{device_id}"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "OpenRobo Fleet"),
    ])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(pub)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(ca_key, None)
    )
    return priv, cert


class MTLSRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        peer_der = self.connection.getpeercert(binary_form=True)
        client_fp = hashlib.sha256(peer_der).hexdigest() if peer_der else "none"

        length = int(self.headers.get("Content-Length", 0))
        _ = self.rfile.read(length) if length > 0 else b"{}"

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        response = {
            "status": "ACK",
            "endpoint": self.path,
            "client_fingerprint": client_fp,
            "acknowledged_ids": ["msg-ack-1", "msg-ack-2"],
        }
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Suppress console logging during tests


@pytest.fixture(scope="module")
def mtls_server_fixture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("mtls_fixture")

    # 1. Main CA & Server Cert
    ca_key, ca_cert = create_test_ca("Fleet Main CA")
    ca_file = tmp_path / "ca.crt"
    ca_file.write_text(ca_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8"), encoding="utf-8")

    server_key, server_cert = create_signed_server_cert(ca_key, ca_cert)
    server_key_file = tmp_path / "server.key"
    server_key_file.write_text(private_key_to_pem(server_key), encoding="utf-8")
    server_cert_file = tmp_path / "server.crt"
    server_cert_file.write_text(server_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8"), encoding="utf-8")

    # 2. Rogue CA & Rogue Client
    rogue_ca_key, rogue_ca_cert = create_test_ca("Rogue Untrusted CA")
    rogue_ca_file = tmp_path / "rogue_ca.crt"
    rogue_ca_file.write_text(rogue_ca_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8"), encoding="utf-8")

    rogue_key, rogue_cert = create_signed_client_cert(rogue_ca_key, rogue_ca_cert, "rogue-agent-999")
    rogue_key_file = tmp_path / "rogue.key"
    rogue_key_file.write_text(private_key_to_pem(rogue_key), encoding="utf-8")
    rogue_cert_file = tmp_path / "rogue.crt"
    rogue_cert_file.write_text(rogue_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8"), encoding="utf-8")

    # 3. 3 Valid Client Certs (alpha, beta, gamma)
    clients = {}
    for name, dev_id in [("robot-alpha", "dev-alpha-001"), ("robot-beta", "dev-beta-002"), ("robot-gamma", "dev-gamma-003")]:
        c_key, c_cert = create_signed_client_cert(ca_key, ca_cert, dev_id)
        k_file = tmp_path / f"{name}.key"
        k_file.write_text(private_key_to_pem(c_key), encoding="utf-8")
        c_file = tmp_path / f"{name}.crt"
        c_file.write_text(c_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8"), encoding="utf-8")
        clients[name] = {
            "device_id": dev_id,
            "key_file": str(k_file),
            "cert_file": str(c_file),
            "fingerprint": compute_cert_fingerprint(c_cert.public_bytes(serialization.Encoding.PEM)),
        }

    # 4. Start mTLS HTTP Server
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(("127.0.0.1", 0))
    port = server_sock.getsockname()[1]
    server_sock.close()

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), MTLSRequestHandler)
    ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_ctx.verify_mode = ssl.CERT_REQUIRED
    ssl_ctx.load_verify_locations(cafile=str(ca_file))
    ssl_ctx.load_cert_chain(certfile=str(server_cert_file), keyfile=str(server_key_file))

    server.socket = ssl_ctx.wrap_socket(server.socket, server_side=True)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield {
        "port": port,
        "base_url": f"https://127.0.0.1:{port}",
        "ca_file": str(ca_file),
        "clients": clients,
        "rogue": {
            "key_file": str(rogue_key_file),
            "cert_file": str(rogue_cert_file),
            "ca_file": str(rogue_ca_file),
        },
    }

    server.shutdown()


def test_real_network_mtls_handshake_success(mtls_server_fixture):
    """Test 1: Valid client certificate successfully completes genuine network TLS handshake."""
    alpha = mtls_server_fixture["clients"]["robot-alpha"]
    client = HttpTransportClient(
        base_url=mtls_server_fixture["base_url"],
        cert_path=alpha["cert_file"],
        key_path=alpha["key_file"],
        ca_cert_path=mtls_server_fixture["ca_file"],
    )

    env = MessageEnvelope(
        device_id=alpha["device_id"],
        message_type="HEARTBEAT",
        payload={"status": "ONLINE"},
    )
    res = client.send_heartbeat(env)
    assert res.get("status") == "ACK"
    assert res.get("client_fingerprint") == alpha["fingerprint"]


def test_real_network_mtls_no_client_cert_rejected(mtls_server_fixture, monkeypatch):
    """Test 2: Connecting without client certificate fails network TLS handshake."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    client = HttpTransportClient(
        base_url=mtls_server_fixture["base_url"],
        cert_path=None,
        key_path=None,
        ca_cert_path=mtls_server_fixture["ca_file"],
    )

    env = MessageEnvelope(
        device_id="anon-dev",
        message_type="HEARTBEAT",
        payload={},
    )
    res = client.send_heartbeat(env)
    assert res.get("success") is False
    assert "error" in res


def test_real_network_mtls_wrong_ca_rejected(mtls_server_fixture, monkeypatch):
    """Test 3: Connecting with a certificate signed by an untrusted rogue CA fails TLS handshake."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    rogue = mtls_server_fixture["rogue"]
    client = HttpTransportClient(
        base_url=mtls_server_fixture["base_url"],
        cert_path=rogue["cert_file"],
        key_path=rogue["key_file"],
        ca_cert_path=mtls_server_fixture["ca_file"],
    )

    env = MessageEnvelope(
        device_id="rogue-agent",
        message_type="TELEMETRY",
        payload={},
    )
    res = client.send_envelope(env)
    assert res.get("success") is False
    assert "error" in res


def test_real_network_mtls_three_agent_lifecycle(mtls_server_fixture):
    """Test 4: 3 distinct agents establish isolated mTLS network transport."""
    for name in ["robot-alpha", "robot-beta", "robot-gamma"]:
        info = mtls_server_fixture["clients"][name]
        client = HttpTransportClient(
            base_url=mtls_server_fixture["base_url"],
            cert_path=info["cert_file"],
            key_path=info["key_file"],
            ca_cert_path=mtls_server_fixture["ca_file"],
        )
        env = MessageEnvelope(
            device_id=info["device_id"],
            message_type="HEARTBEAT",
            payload={"status": "ONLINE", "name": name},
        )
        res = client.send_heartbeat(env)
        assert res.get("status") == "ACK"
        assert res.get("client_fingerprint") == info["fingerprint"]


def test_real_mtls_concurrency_25_agents(mtls_server_fixture):
    """Test 5: 25 concurrent mTLS client connections across network sockets."""
    alpha = mtls_server_fixture["clients"]["robot-alpha"]
    latencies = []

    def make_mtls_request(i):
        client = HttpTransportClient(
            base_url=mtls_server_fixture["base_url"],
            cert_path=alpha["cert_file"],
            key_path=alpha["key_file"],
            ca_cert_path=mtls_server_fixture["ca_file"],
        )
        env = MessageEnvelope(
            message_id=f"msg-concurrent-{i}",
            device_id=alpha["device_id"],
            message_type="HEARTBEAT",
            payload={"worker_index": i},
        )
        t0 = time.perf_counter()
        res = client.send_heartbeat(env)
        dt = (time.perf_counter() - t0) * 1000.0
        return res, dt

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_mtls_request, i) for i in range(25)]
        for f in concurrent.futures.as_completed(futures):
            res, dt = f.result()
            assert res.get("status") == "ACK"
            latencies.append(dt)

    assert len(latencies) == 25
    p50 = sorted(latencies)[len(latencies) // 2]
    assert p50 < 2000.0, f"mTLS p50 latency {p50:.2f}ms exceeds threshold"


def test_agent_daemon_typed_heartbeat_routing_e2e(tmp_path, monkeypatch):
    """Test 6: AgentDaemon correctly routes heartbeat events to send_heartbeat and telemetry to send_batch."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    state_dir = tmp_path / "state"
    config_dir = tmp_path / "config"
    cfg = AgentConfig(
        device_id="test-daemon-routing",
        control_plane_url="http://localhost:8000",
        state_dir=state_dir,
        config_dir=config_dir,
    )
    daemon = AgentDaemon(cfg)

    # 1. Step heartbeat and telemetry
    daemon.step_heartbeat()
    daemon.step_telemetry()

    assert daemon.spool.count() >= 1

    # Mock transport send methods
    daemon.transport.send_heartbeat = lambda env: {"status": "ACK", "message_id": env.message_id}
    daemon.transport.send_batch = lambda batch: [e.message_id for e in batch]

    acked = daemon.flush_spool()
    assert acked >= 1
    assert daemon.spool.count() == 0


def test_agent_spool_survives_connection_failure_and_reconnects(tmp_path, monkeypatch):
    """Test 7: Offline spool holds events when transport fails, then drains on recovery."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    state_dir = tmp_path / "state2"
    config_dir = tmp_path / "config2"
    cfg = AgentConfig(
        device_id="test-daemon-spool-failure",
        control_plane_url="http://localhost:8000",
        state_dir=state_dir,
        config_dir=config_dir,
    )
    daemon = AgentDaemon(cfg)

    # Enqueue events
    daemon.step_heartbeat()
    initial_count = daemon.spool.count()
    assert initial_count > 0

    # Transport failure
    daemon.transport.send_heartbeat = lambda env: {"success": False, "error": "Connection refused"}
    acked_failed = daemon.flush_spool()
    assert acked_failed == 0
    assert daemon.spool.count() == initial_count

    # Transport recovered
    daemon.transport.send_heartbeat = lambda env: {"status": "ACK", "message_id": env.message_id}
    acked_recovered = daemon.flush_spool()
    assert acked_recovered == initial_count
    assert daemon.spool.count() == 0


def test_websocket_unauthenticated_fingerprint_rejected(monkeypatch):
    """Test 8: WebSocket rejects unauthenticated connection attempts without verified client certificate."""
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    from apps.api.main import app

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("OPENROBO_ALLOW_DEV_CERT_HEADER", "false")

    client = TestClient(app)
    # Attempt connecting without client certificate / verified proxy header -> immediate 1008 rejection
    try:
        with client.websocket_connect("/api/v1/fleet/agent/ws"):
            pytest.fail("WebSocket handshake should have been closed/rejected")
    except WebSocketDisconnect as e:
        assert e.code == 1008
    except Exception as e:
        assert "1008" in str(e) or "WebSocket" in str(e) or "closed" in str(e)
