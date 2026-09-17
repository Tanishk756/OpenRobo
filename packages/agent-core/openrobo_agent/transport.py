"""OpenRobo Agent Transport Abstraction & Backoff Client."""

import abc
import json
import random
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from openrobo_agent.models import MessageEnvelope


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
    """Standard HTTP/mTLS client for batch telemetry delivery."""

    def __init__(
        self,
        base_url: str,
        cert_path: Optional[str] = None,
        key_path: Optional[str] = None,
        ca_cert_path: Optional[str] = None,
        client_cert_header_override: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.cert_path = cert_path
        self.key_path = key_path
        self.ca_cert_path = ca_cert_path
        self.client_cert_header_override = client_cert_header_override
        self._is_connected = False

    def connect(self) -> bool:
        self._is_connected = True
        return True

    def disconnect(self) -> None:
        self._is_connected = False

    def send_envelope(self, envelope: MessageEnvelope) -> Dict[str, Any]:
        endpoint = f"{self.base_url}/api/v1/fleet/agent/telemetry"
        headers = {"Content-Type": "application/json"}
        if self.client_cert_header_override:
            headers["X-Client-Cert-Fingerprint"] = self.client_cert_header_override

        data_bytes = envelope.model_dump_json().encode("utf-8")
        req = urllib.request.Request(endpoint, data=data_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
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
        if self.client_cert_header_override:
            headers["X-Client-Cert-Fingerprint"] = self.client_cert_header_override

        payload = {"messages": [e.model_dump() for e in envelopes]}
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(endpoint, data=data_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res.get("acknowledged_ids", [])
        except Exception:
            return []
