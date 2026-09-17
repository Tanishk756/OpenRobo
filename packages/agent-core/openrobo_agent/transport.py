"""OpenRobo Agent Transport Abstraction & mTLS Client."""

import abc
import json
import logging
import os
import random
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from openrobo_agent.models import MessageEnvelope

logger = logging.getLogger("openrobo.agent.transport")


class TransportClient(abc.ABC):
    """Abstract base class for OpenRobo agent transport implementations."""

    @abc.abstractmethod
    def connect(self) -> bool:
        """Establish transport connection."""
        pass

    @abc.abstractmethod
    def disconnect(self) -> None:
        """Close transport connection."""
        pass

    @abc.abstractmethod
    def send_envelope(self, envelope: MessageEnvelope) -> Dict[str, Any]:
        """Send a single message envelope."""
        pass

    @abc.abstractmethod
    def send_batch(self, envelopes: List[MessageEnvelope]) -> List[str]:
        """Send a batch of message envelopes and return list of acknowledged message IDs."""
        pass


def calculate_backoff_delay(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0, jitter_factor: float = 0.2) -> float:
    """Compute exponential backoff delay with jitter to prevent reconnect storms."""
    delay = min(max_delay, base_delay * (2 ** attempt))
    jitter = delay * jitter_factor * (random.random() * 2 - 1)
    return max(0.1, delay + jitter)


class HttpTransportClient(TransportClient):
    """Standard HTTP/mTLS client for telemetry and heartbeat delivery.

    Constructs an authentic Python ssl.SSLContext presenting client certificates
    and validating server CA certificates.
    """

    def __init__(
        self,
        base_url: str,
        cert_path: Optional[str] = None,
        key_path: Optional[str] = None,
        ca_cert_path: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.cert_path = cert_path
        self.key_path = key_path
        self.ca_cert_path = ca_cert_path
        self.ssl_context: Optional[ssl.SSLContext] = None
        self._is_connected = False
        self._opener: Optional[urllib.request.OpenerDirector] = None

        self._validate_and_build_transport()

    def _validate_and_build_transport(self) -> None:
        is_https = self.base_url.lower().startswith("https://")
        is_dev = os.getenv("ENVIRONMENT", "production").lower() == "development"
        allow_insecure = os.getenv("OPENROBO_ALLOW_INSECURE_HTTP", "false").lower() in ("true", "1", "yes")

        if not is_https:
            if not is_dev and not allow_insecure:
                raise RuntimeError(
                    f"CRITICAL SECURITY: Plaintext HTTP endpoint '{self.base_url}' is rejected in production. "
                    "Use https:// with mTLS certificate authentication."
                )
            logger.warning("Agent transport initialized with plaintext HTTP in development/testing mode.")
            self._opener = urllib.request.build_opener()
            return

        # Build genuine mTLS SSLContext
        ssl_ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ssl_ctx.verify_mode = ssl.CERT_REQUIRED
        ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2

        if self.ca_cert_path and os.path.exists(self.ca_cert_path):
            ssl_ctx.load_verify_locations(cafile=self.ca_cert_path)

        if self.cert_path and self.key_path and os.path.exists(self.cert_path) and os.path.exists(self.key_path):
            ssl_ctx.load_cert_chain(certfile=self.cert_path, keyfile=self.key_path)

        self.ssl_context = ssl_ctx
        https_handler = urllib.request.HTTPSHandler(context=ssl_ctx)
        self._opener = urllib.request.build_opener(https_handler)

    def connect(self) -> bool:
        self._is_connected = True
        return True

    def disconnect(self) -> None:
        self._is_connected = False

    def send_envelope(self, envelope: MessageEnvelope) -> Dict[str, Any]:
        endpoint = f"{self.base_url}/api/v1/fleet/agent/telemetry"
        headers = {"Content-Type": "application/json"}

        data_bytes = envelope.model_dump_json().encode("utf-8")
        req = urllib.request.Request(endpoint, data=data_bytes, headers=headers, method="POST")

        opener = self._opener or urllib.request.build_opener()
        try:
            with opener.open(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            return {"success": False, "error": f"HTTP {e.code}: {err}", "status_code": e.code}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_batch(self, envelopes: List[MessageEnvelope]) -> List[str]:
        if not envelopes:
            return []
        endpoint = f"{self.base_url}/api/v1/fleet/agent/telemetry-batch"
        headers = {"Content-Type": "application/json"}

        payload = {"messages": [e.model_dump() for e in envelopes]}
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(endpoint, data=data_bytes, headers=headers, method="POST")

        opener = self._opener or urllib.request.build_opener()
        try:
            with opener.open(req, timeout=15) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res.get("acknowledged_ids", [])
        except Exception:
            return []
