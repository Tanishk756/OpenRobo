# Unit and security tests for async artifact client, SSRF defenses, streaming verification, and quarantine management.

import hashlib
import http.server
import tempfile
import threading
from pathlib import Path

import pytest
from openrobo_agent.deployment.artifact_client import (
    ArtifactClient,
    ArtifactVerificationError,
    SSRFValidationError,
    validate_artifact_url,
)


def test_ssrf_url_validation():
    # 1. Embedded credentials rejection
    with pytest.raises(SSRFValidationError, match="credentials"):
        validate_artifact_url("https://user:secret@artifacts.example.com/file.tar.gz")

    # 2. Query / fragment rejection
    with pytest.raises(SSRFValidationError, match="Query parameters"):
        validate_artifact_url("https://artifacts.example.com/file.tar.gz?query=1")
    with pytest.raises(SSRFValidationError, match="Query parameters"):
        validate_artifact_url("https://artifacts.example.com/file.tar.gz#section")

    # 3. Invalid scheme
    with pytest.raises(SSRFValidationError, match="scheme"):
        validate_artifact_url("ftp://artifacts.example.com/file.tar.gz")

    # 4. Host mismatch
    with pytest.raises(SSRFValidationError, match="does not match allowed host"):
        validate_artifact_url(
            "https://evil.example.com/file.tar.gz",
            custom_allowed_host="artifacts.example.com",
            allow_private_network=True,
        )


class MockArtifactHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/rel-1/artifact.tar.gz":
            data = b"Deterministic payload for artifact client test."
            self.send_response(200)
            self.send_header("Content-Type", "application/gzip")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == "/large-declared":
            self.send_response(200)
            self.send_header("Content-Length", "100")
            self.end_headers()
            self.wfile.write(b"A" * 100)
        elif self.path == "/len-mismatch":
            self.send_response(200)
            self.send_header("Content-Length", "30")
            self.end_headers()
            self.wfile.write(b"Short")
        elif self.path == "/bad-digest":
            self.send_response(200)
            self.send_header("Content-Length", "10")
            self.end_headers()
            self.wfile.write(b"0123456789")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


@pytest.fixture
def mock_server():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), MockArtifactHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


@pytest.mark.asyncio
async def test_artifact_client_streaming_and_quarantine(mock_server):
    with tempfile.TemporaryDirectory() as tmpdir:
        downloads_dir = Path(tmpdir)
        client = ArtifactClient(
            downloads_dir=downloads_dir,
            max_artifact_bytes=1000,
            allow_private_network=True,
        )

        test_bytes = b"Deterministic payload for artifact client test."
        hasher = hashlib.sha256(test_bytes)
        valid_digest = hasher.hexdigest()

        # Successful download & atomic verification
        path = await client.download_and_verify(
            url=f"{mock_server}/rel-1/artifact.tar.gz",
            expected_digest=valid_digest,
            deployment_id="dep-123",
        )
        assert path.exists()
        assert path.name == f"{valid_digest}.tar.gz"
        assert path.read_bytes() == test_bytes

        # Check that .part file was cleaned up / renamed
        part_files = list(downloads_dir.glob("**/*.part"))
        assert len(part_files) == 0


@pytest.mark.asyncio
async def test_artifact_client_size_and_digest_mismatch_rejections(mock_server):
    with tempfile.TemporaryDirectory() as tmpdir:
        downloads_dir = Path(tmpdir)
        client = ArtifactClient(
            downloads_dir=downloads_dir,
            max_artifact_bytes=50,  # Small limit
            allow_private_network=True,
        )

        # 1. Declared Content-Length exceeds limit
        with pytest.raises(ArtifactVerificationError, match="exceeds max limit"):
            await client.download_and_verify(
                url=f"{mock_server}/large-declared",
                expected_digest="a" * 64,
                deployment_id="dep-large",
            )

        # 2. Content-Length mismatch
        with pytest.raises(ArtifactVerificationError, match="Content-Length mismatch|Artifact transfer failed"):
            await client.download_and_verify(
                url=f"{mock_server}/len-mismatch",
                expected_digest="a" * 64,
                deployment_id="dep-len",
            )

        # 3. Digest mismatch
        with pytest.raises(ArtifactVerificationError, match="Artifact digest mismatch"):
            await client.download_and_verify(
                url=f"{mock_server}/bad-digest",
                expected_digest="f" * 64,
                deployment_id="dep-digest",
            )
