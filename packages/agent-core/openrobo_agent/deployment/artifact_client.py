"""Secure asynchronous artifact client with SSRF protection, streaming verification, and quarantine management."""

import asyncio
import hashlib
import ipaddress
import logging
import os
import socket
import ssl
from pathlib import Path
from typing import Optional, Set
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("openrobo.agent.artifact_client")

# Blocked cloud metadata and sensitive addresses
BLOCKED_IPS = {
    ipaddress.ip_address("169.254.169.254"),  # AWS/GCP/Azure metadata
    ipaddress.ip_address("100.100.100.200"),  # Alibaba Cloud metadata
}


class SSRFValidationError(ValueError):
    pass


class ArtifactVerificationError(ValueError):
    pass


def validate_artifact_url(url: str, allow_private_network: bool = False, custom_allowed_host: Optional[str] = None) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SSRFValidationError(f"Invalid URL scheme '{parsed.scheme}'. Only http/https supported.")

    if parsed.username or parsed.password:
        raise SSRFValidationError("Embedded credentials in artifact URLs are strictly prohibited.")

    if parsed.query or parsed.fragment:
        raise SSRFValidationError("Query parameters and fragments in artifact URLs are prohibited.")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFValidationError("Artifact URL missing hostname.")

    if custom_allowed_host and hostname.lower() != custom_allowed_host.lower():
        raise SSRFValidationError(f"Artifact hostname '{hostname}' does not match allowed host '{custom_allowed_host}'")

    # Resolve all DNS addresses
    try:
        addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except Exception as e:
        raise SSRFValidationError(f"Failed to resolve artifact hostname '{hostname}': {e}")

    for item in addr_info:
        ip_str = item[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        if ip in BLOCKED_IPS:
            raise SSRFValidationError(f"Access to cloud metadata IP '{ip}' is blocked.")

        if not allow_private_network:
            if ip.is_loopback:
                raise SSRFValidationError(f"Access to loopback IP '{ip}' is blocked.")
            if ip.is_link_local:
                raise SSRFValidationError(f"Access to link-local IP '{ip}' is blocked.")
            if ip.is_private:
                raise SSRFValidationError(f"Access to private network IP '{ip}' is blocked.")
            if ip.is_multicast or ip.is_unspecified or ip.is_reserved:
                raise SSRFValidationError(f"Access to reserved/multicast IP '{ip}' is blocked.")

    return url


class ArtifactClient:
    def __init__(
        self,
        downloads_dir: Path,
        max_artifact_bytes: int = 104857600,  # 100 MB default
        allow_private_network: bool = False,
        ssl_context: Optional[ssl.SSLContext] = None,
        timeout_seconds: float = 30.0,
    ):
        self.downloads_dir = Path(downloads_dir)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.max_artifact_bytes = max_artifact_bytes
        self.allow_private_network = allow_private_network
        self.ssl_context = ssl_context
        self.timeout = httpx.Timeout(timeout_seconds, connect=10.0)

    async def download_and_verify(
        self,
        url: str,
        expected_digest: str,
        deployment_id: str,
        allowed_host: Optional[str] = None,
    ) -> Path:
        # 1. SSRF and URL validation
        validated_url = validate_artifact_url(
            url=url,
            allow_private_network=self.allow_private_network,
            custom_allowed_host=allowed_host,
        )

        dep_download_dir = self.downloads_dir / deployment_id
        dep_download_dir.mkdir(parents=True, exist_ok=True)

        final_artifact_path = dep_download_dir / f"{expected_digest}.tar.gz"
        part_path = dep_download_dir / f"{expected_digest}.part"

        # If final verified artifact already exists and matches digest, reuse it
        if final_artifact_path.exists():
            hasher = hashlib.sha256()
            with open(final_artifact_path, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            if hasher.hexdigest().lower() == expected_digest.lower():
                return final_artifact_path

        hasher = hashlib.sha256()
        total_bytes = 0

        async with httpx.AsyncClient(
            verify=self.ssl_context if self.ssl_context else True,
            timeout=self.timeout,
            follow_redirects=False,
        ) as client:
            async with client.stream("GET", validated_url) as response:
                if response.status_code != 200:
                    raise ArtifactVerificationError(
                        f"Artifact download failed with HTTP status {response.status_code}"
                    )

                content_length_header = response.headers.get("content-length")
                declared_len: Optional[int] = None
                if content_length_header:
                    try:
                        declared_len = int(content_length_header)
                    except (ValueError, TypeError):
                        declared_len = None

                    if declared_len is not None and declared_len > self.max_artifact_bytes:
                        raise ArtifactVerificationError(
                            f"Declared Content-Length {declared_len} exceeds max limit {self.max_artifact_bytes}"
                        )

                try:
                    with open(part_path, "wb") as part_file:
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            total_bytes += len(chunk)
                            if total_bytes > self.max_artifact_bytes:
                                raise ArtifactVerificationError(
                                    f"Received bytes {total_bytes} exceeded maximum allowed {self.max_artifact_bytes}"
                                )
                            hasher.update(chunk)
                            part_file.write(chunk)
                        part_file.flush()
                        os.fsync(part_file.fileno())
                except (httpx.HTTPError, httpx.RemoteProtocolError) as e:
                    if part_path.exists():
                        try:
                            part_path.unlink()
                        except Exception:
                            pass
                    raise ArtifactVerificationError(f"Artifact transfer failed: {e}") from e
                except Exception:
                    if part_path.exists():
                        try:
                            part_path.unlink()
                        except Exception:
                            pass
                    raise

        if declared_len is not None and total_bytes != declared_len:
            if part_path.exists():
                part_path.unlink()
            raise ArtifactVerificationError(
                f"Content-Length mismatch: expected {declared_len} bytes, received {total_bytes} bytes"
            )

        computed_digest = hasher.hexdigest().lower()
        if computed_digest != expected_digest.lower():
            if part_path.exists():
                part_path.unlink()
            raise ArtifactVerificationError(
                f"Artifact digest mismatch: expected {expected_digest.lower()}, got {computed_digest}"
            )

        # Atomic rename .part -> final artifact
        os.replace(part_path, final_artifact_path)
        return final_artifact_path

    async def fetch_manifest_bytes(
        self,
        url: str,
        expected_manifest_digest: str,
        allowed_host: Optional[str] = None,
    ) -> bytes:
        validated_url = validate_artifact_url(
            url=url,
            allow_private_network=self.allow_private_network,
            custom_allowed_host=allowed_host,
        )

        async with httpx.AsyncClient(
            verify=self.ssl_context if self.ssl_context else True,
            timeout=self.timeout,
            follow_redirects=False,
        ) as client:
            response = await client.get(validated_url)
            if response.status_code != 200:
                raise ArtifactVerificationError(
                    f"Manifest download failed with HTTP status {response.status_code}"
                )

            manifest_bytes = response.content
            if len(manifest_bytes) > 1048576:  # 1 MB max manifest
                raise ArtifactVerificationError("Manifest size exceeds 1 MB limit")

            computed_digest = hashlib.sha256(manifest_bytes).hexdigest().lower()
            if computed_digest != expected_manifest_digest.lower():
                raise ArtifactVerificationError(
                    f"Manifest digest mismatch: expected {expected_manifest_digest.lower()}, got {computed_digest}"
                )

            return manifest_bytes

    async def fetch_signature_text(
        self,
        url: str,
        allowed_host: Optional[str] = None,
    ) -> str:
        validated_url = validate_artifact_url(
            url=url,
            allow_private_network=self.allow_private_network,
            custom_allowed_host=allowed_host,
        )

        async with httpx.AsyncClient(
            verify=self.ssl_context if self.ssl_context else True,
            timeout=self.timeout,
            follow_redirects=False,
        ) as client:
            response = await client.get(validated_url)
            if response.status_code != 200:
                raise ArtifactVerificationError(
                    f"Signature download failed with HTTP status {response.status_code}"
                )

            sig_text = response.text.strip()
            if len(sig_text) > 8192:
                raise ArtifactVerificationError("Signature size exceeds 8 KB limit")

            return sig_text
