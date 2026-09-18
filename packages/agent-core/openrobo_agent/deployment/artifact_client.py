# SSRF-hardened, streaming async artifact client for OpenRobo Agent.

import hashlib
import ipaddress
import os
import shutil
import socket
import ssl
import urllib.parse
from pathlib import Path
from typing import Optional

import httpx
from openrobo_release.manifest import canonical_manifest_bytes
from openrobo_release.models import ReleaseManifest


class ArtifactDownloadError(Exception):
    pass


class SSRFValidationError(ArtifactDownloadError):
    pass


class ArtifactVerificationError(ArtifactDownloadError):
    pass


BLOCKED_IPS = {
    ipaddress.ip_address("169.254.169.254"),  # AWS / GCP / Azure metadata
    ipaddress.ip_address("100.100.100.200"),  # Alibaba metadata
}


def validate_artifact_url(
    url: str,
    allow_private_network: bool = False,
    custom_allowed_host: Optional[str] = None,
    allow_http_dev: bool = False,
) -> str:
    """Validates URL against strict SSRF rules, host policies, and scheme requirements."""
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception as e:
        raise SSRFValidationError(f"Malformed artifact URL '{url}': {e}")

    # Scheme policy: HTTPS mandatory in production. HTTP permitted only when
    # dev environment + flag are set or in local/private tests with allow_private_network.
    if parsed.scheme.lower() == "http":
        env_mode = os.environ.get("ENVIRONMENT", "").lower()
        dev_flag = os.environ.get("OPENROBO_ALLOW_DEV_ARTIFACT_HTTP", "").lower() in ("true", "1", "yes")
        is_loopback = parsed.hostname in ("127.0.0.1", "localhost", "::1") and allow_private_network
        if not (allow_http_dev or is_loopback or (env_mode in ("development", "test") and dev_flag)):
            raise SSRFValidationError(
                f"Insecure HTTP artifact URL '{url}' is prohibited in production. "
                "HTTPS is required unless ENVIRONMENT=development and OPENROBO_ALLOW_DEV_ARTIFACT_HTTP=true."
            )
    elif parsed.scheme.lower() != "https":
        raise SSRFValidationError(f"Invalid artifact URL scheme '{parsed.scheme}'. Only HTTPS is permitted.")

    if parsed.username or parsed.password:
        raise SSRFValidationError("Embedded credentials in artifact URLs are prohibited.")

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
        allow_http_dev: bool = False,
        ssl_context: Optional[ssl.SSLContext] = None,
        timeout_seconds: float = 30.0,
    ):
        self.downloads_dir = Path(downloads_dir)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.max_artifact_bytes = max_artifact_bytes
        self.allow_private_network = allow_private_network
        self.allow_http_dev = allow_http_dev
        self.ssl_context = ssl_context
        self.timeout = httpx.Timeout(timeout_seconds, connect=10.0)

    def check_disk_space(self, target_dir: Path, required_bytes: int, safety_margin_bytes: int = 52428800) -> None:
        """Inspects available free disk space before starting a transfer/staging operation."""
        target_dir.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(target_dir)
        total_needed = required_bytes + safety_margin_bytes
        if usage.free < total_needed:
            raise ArtifactDownloadError(
                f"Insufficient disk space on {target_dir}: available {usage.free} bytes, "
                f"required {total_needed} bytes (artifact {required_bytes} + safety margin {safety_margin_bytes})"
            )

    async def download_and_verify(
        self,
        url: str,
        expected_digest: str,
        deployment_id: str,
        allowed_host: Optional[str] = None,
        allow_private_network: Optional[bool] = None,
        max_bytes: Optional[int] = None,
    ) -> Path:
        effective_max = max_bytes or self.max_artifact_bytes

        # 1. SSRF and URL validation
        allow_priv = self.allow_private_network if allow_private_network is None else allow_private_network
        validated_url = validate_artifact_url(
            url=url,
            allow_private_network=allow_priv,
            custom_allowed_host=allowed_host,
            allow_http_dev=self.allow_http_dev,
        )

        dep_download_dir = self.downloads_dir / deployment_id
        dep_download_dir.mkdir(parents=True, exist_ok=True)

        final_artifact_path = dep_download_dir / f"{expected_digest}.tar.gz"
        part_path = dep_download_dir / f"{expected_digest}.part"

        # Check existing cached artifact
        if final_artifact_path.exists():
            hasher = hashlib.sha256()
            with open(final_artifact_path, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            if hasher.hexdigest().lower() == expected_digest.lower():
                return final_artifact_path

        # 2. Check disk space (estimated from max allowed or Content-Length)
        self.check_disk_space(dep_download_dir, effective_max)

        hasher = hashlib.sha256()
        total_bytes = 0

        async with httpx.AsyncClient(
            verify=self.ssl_context if self.ssl_context else True,
            timeout=self.timeout,
            follow_redirects=False,
        ) as client:
            async with client.stream("GET", validated_url) as response:
                if response.status_code != 200:
                    raise ArtifactVerificationError(f"Artifact download failed with HTTP status {response.status_code}")

                content_length_header = response.headers.get("content-length")
                declared_len: Optional[int] = None
                if content_length_header:
                    try:
                        declared_len = int(content_length_header)
                    except (ValueError, TypeError):
                        declared_len = None

                    if declared_len is not None and declared_len > effective_max:
                        raise ArtifactVerificationError(f"Declared Content-Length {declared_len} exceeds max limit {effective_max}")

                try:
                    with open(part_path, "wb") as part_file:
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            total_bytes += len(chunk)
                            if total_bytes > effective_max:
                                raise ArtifactVerificationError(f"Received bytes {total_bytes} exceeded maximum allowed {effective_max}")
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
            raise ArtifactVerificationError(f"Content-Length mismatch: expected {declared_len} bytes, received {total_bytes} bytes")

        computed_digest = hasher.hexdigest().lower()
        if computed_digest != expected_digest.lower():
            if part_path.exists():
                part_path.unlink()
            raise ArtifactVerificationError(f"Artifact digest mismatch: expected {expected_digest.lower()}, got {computed_digest}")

        # Atomic rename .part -> final artifact
        os.replace(part_path, final_artifact_path)
        return final_artifact_path

    async def fetch_manifest(
        self,
        url: str,
        expected_manifest_digest: str,
        allowed_host: Optional[str] = None,
        allow_private_network: Optional[bool] = None,
        max_bytes: int = 1048576,  # 1 MiB max
    ) -> tuple[bytes, ReleaseManifest]:
        """Streams manifest with bounded size limit, parses it, and validates canonical manifest digest."""
        allow_priv = self.allow_private_network if allow_private_network is None else allow_private_network
        validated_url = validate_artifact_url(
            url=url,
            allow_private_network=allow_priv,
            custom_allowed_host=allowed_host,
            allow_http_dev=self.allow_http_dev,
        )

        buffer = bytearray()
        async with httpx.AsyncClient(
            verify=self.ssl_context if self.ssl_context else True,
            timeout=self.timeout,
            follow_redirects=False,
        ) as client:
            async with client.stream("GET", validated_url) as response:
                if response.status_code != 200:
                    raise ArtifactVerificationError(f"Manifest download failed with HTTP status {response.status_code}")

                async for chunk in response.aiter_bytes(chunk_size=8192):
                    buffer.extend(chunk)
                    if len(buffer) > max_bytes:
                        raise ArtifactVerificationError(f"Manifest size exceeds maximum limit of {max_bytes} bytes")

        raw_manifest_bytes = bytes(buffer)
        try:
            manifest = ReleaseManifest.model_validate_json(raw_manifest_bytes)
        except Exception as e:
            raise ArtifactVerificationError(f"Malformed release manifest: {e}") from e

        # Validate canonical manifest digest
        canonical_digest = hashlib.sha256(canonical_manifest_bytes(manifest)).hexdigest().lower()
        if canonical_digest != expected_manifest_digest.lower():
            raise ArtifactVerificationError(
                f"Manifest canonical digest mismatch: expected {expected_manifest_digest.lower()}, got {canonical_digest}"
            )

        return raw_manifest_bytes, manifest

    async def fetch_signature_text(
        self,
        url: str,
        allowed_host: Optional[str] = None,
        allow_private_network: Optional[bool] = None,
        max_bytes: int = 8192,  # 8 KiB max
    ) -> str:
        """Streams detached signature with bounded size limit."""
        allow_priv = self.allow_private_network if allow_private_network is None else allow_private_network
        validated_url = validate_artifact_url(
            url=url,
            allow_private_network=allow_priv,
            custom_allowed_host=allowed_host,
            allow_http_dev=self.allow_http_dev,
        )

        buffer = bytearray()
        async with httpx.AsyncClient(
            verify=self.ssl_context if self.ssl_context else True,
            timeout=self.timeout,
            follow_redirects=False,
        ) as client:
            async with client.stream("GET", validated_url) as response:
                if response.status_code != 200:
                    raise ArtifactVerificationError(f"Signature download failed with HTTP status {response.status_code}")

                async for chunk in response.aiter_bytes(chunk_size=1024):
                    buffer.extend(chunk)
                    if len(buffer) > max_bytes:
                        raise ArtifactVerificationError(f"Signature size exceeds maximum limit of {max_bytes} bytes")

        sig_text = bytes(buffer).decode("utf-8").strip()
        return sig_text
