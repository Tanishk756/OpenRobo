import hashlib
import logging
import os
import secrets
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple

from fastapi import HTTPException, Request, WebSocket, status

from apps.api.models.fleet import FleetDeviceModel

logger = logging.getLogger("openrobo.fleet.security")


class ReplayProtectionManager:
    """
    Sliding-window replay protection with bounded deduplication store.
    Rejects duplicate message_ids and timestamps outside the allowable clock skew window.
    Single-process in-memory store.
    """

    def __init__(self, max_clock_skew_seconds: int = 60, max_cache_entries: int = 50000):
        self.max_clock_skew = timedelta(seconds=max_clock_skew_seconds)
        self.max_cache_entries = max_cache_entries
        self._seen_messages: OrderedDict[Tuple[str, str], datetime] = OrderedDict()

    def validate_and_record(self, device_id: str, message_id: str, timestamp_str: str) -> None:
        try:
            msg_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            if msg_time.tzinfo is None:
                msg_time = msg_time.replace(tzinfo=timezone.utc)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid timestamp format: {e}",
            )

        now = datetime.now(timezone.utc)

        # Check clock skew (future or stale)
        if msg_time > now + self.max_clock_skew:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Timestamp is too far in the future (clock skew violation).",
            )
        if msg_time < now - self.max_clock_skew:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Timestamp is too stale (expired message window).",
            )

        # Check replay deduplication
        key = (device_id, message_id)
        if key in self._seen_messages:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Replay detected: duplicate message_id '{message_id}' for device '{device_id}'.",
            )

        # Record in bounded cache
        self._seen_messages[key] = msg_time
        if len(self._seen_messages) > self.max_cache_entries:
            self._seen_messages.popitem(last=False)

    def clear(self) -> None:
        self._seen_messages.clear()


class SecurityIdentityExtractor:
    """
    Extracts authenticated device identity adhering to strict mTLS and reverse-proxy trust boundary.
    Normal HTTP clients cannot spoof headers.
    """

    def __init__(self):
        self.proxy_mode_enabled = os.getenv("OPENROBO_PROXY_CERT_AUTH", "false").lower() in ("true", "1", "yes")
        trusted_proxies_str = os.getenv("OPENROBO_TRUSTED_PROXIES", "127.0.0.1,::1,localhost,testclient")
        self.trusted_proxies = {p.strip() for p in trusted_proxies_str.split(",") if p.strip()}

    def extract_device_fingerprint(self, request: Request) -> Optional[str]:
        client_host = request.client.host if request.client else None

        # 1. Trusted Reverse Proxy Mode
        if self.proxy_mode_enabled:
            if client_host in self.trusted_proxies:
                proxy_fingerprint = request.headers.get("X-SSL-Client-Fingerprint") or request.headers.get("X-Client-Cert-Fingerprint")
                if proxy_fingerprint:
                    return proxy_fingerprint.strip().lower()
            # If not from trusted proxy, proxy headers MUST be ignored

        # 2. Development / Test Header fallback (STRICTLY requires BOTH dev environment AND dev header flag)
        env_mode = os.getenv("ENVIRONMENT", "production").lower()
        allow_dev_headers = os.getenv("OPENROBO_ALLOW_DEV_CERT_HEADER", "false").lower() in ("true", "1", "yes")

        if env_mode == "development" and allow_dev_headers:
            dev_fp = request.headers.get("X-OpenRobo-Cert-Fingerprint")
            if dev_fp:
                return dev_fp.strip().lower()

        return None


class RateLimiter:
    """In-memory sliding window rate limiter."""

    def __init__(self):
        self._records: Dict[str, List[float]] = {}

    def check(self, key: str, max_requests: int, window_seconds: int = 60) -> None:
        if os.getenv("OPENROBO_DISABLE_RATE_LIMIT", "false").lower() in ("true", "1", "yes"):
            return

        now = time.time()
        cutoff = now - window_seconds
        records = self._records.get(key, [])
        valid_records = [t for t in records if t > cutoff]

        if len(valid_records) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for action '{key}'. Maximum {max_requests} requests per {window_seconds}s.",
            )

        valid_records.append(now)
        self._records[key] = valid_records

    def clear(self) -> None:
        self._records.clear()


class ActiveWebSocketRegistry:
    """Tracks active agent WebSocket connections and closes them upon device revocation."""

    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}

    def register(self, device_id: str, ws: WebSocket) -> None:
        if device_id not in self._connections:
            self._connections[device_id] = set()
        self._connections[device_id].add(ws)

    def unregister(self, device_id: str, ws: WebSocket) -> None:
        if device_id in self._connections:
            self._connections[device_id].discard(ws)
            if not self._connections[device_id]:
                del self._connections[device_id]

    async def close_device_connections(self, device_id: str, code: int = 1008, reason: str = "Device Revoked") -> None:
        if device_id in self._connections:
            sockets = list(self._connections[device_id])
            for ws in sockets:
                try:
                    await ws.close(code=code, reason=reason)
                except Exception:
                    pass
            self._connections.pop(device_id, None)


def verify_admin_authorization(request: Request) -> None:
    """
    Verify administrative authorization for control-plane fleet operations.
    In production, requires X-OpenRobo-Admin-Key matching OPENROBO_ADMIN_KEY.
    """
    env_mode = os.getenv("ENVIRONMENT", "production").lower()
    admin_key = os.getenv("OPENROBO_ADMIN_KEY")

    if env_mode == "production":
        if not admin_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server configuration error: OPENROBO_ADMIN_KEY is not configured in production environment.",
            )
        provided_key = request.headers.get("X-OpenRobo-Admin-Key")
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            provided_key = auth_header[7:].strip()

        if not provided_key or not secrets.compare_digest(provided_key, admin_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: Valid X-OpenRobo-Admin-Key or Bearer token required for administrative fleet operations.",
            )
    else:
        # Development mode
        if admin_key:
            provided_key = request.headers.get("X-OpenRobo-Admin-Key")
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                provided_key = auth_header[7:].strip()
            if not provided_key or not secrets.compare_digest(provided_key, admin_key):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Unauthorized: Invalid admin key in development.",
                )


def hash_enrollment_token(token: str) -> str:
    """Cryptographically hash an enrollment token with SHA-256 for secure DB storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_enrollment_token() -> Tuple[str, str]:
    """Generate a cryptographically secure random token and its SHA-256 hash."""
    raw_token = f"orb_tok_{secrets.token_urlsafe(32)}"
    token_hash = hash_enrollment_token(raw_token)
    return raw_token, token_hash


def derive_fleet_device_status(device: FleetDeviceModel, now: Optional[datetime] = None) -> str:
    """
    Centrally derive fleet device status.
    - REVOKED if revoked_at is set.
    - ONLINE if heartbeat received within last 30s.
    - DEGRADED if heartbeat received within last 90s.
    - OFFLINE otherwise.
    """
    if device.revoked_at is not None or device.status == "REVOKED":
        return "REVOKED"

    if device.last_heartbeat_at is None:
        return "OFFLINE"

    if now is None:
        now = datetime.now(timezone.utc)

    hb_time = device.last_heartbeat_at
    if hb_time.tzinfo is None:
        hb_time = hb_time.replace(tzinfo=timezone.utc)

    diff = (now - hb_time).total_seconds()
    if diff <= 30:
        return "ONLINE"
    elif diff <= 90:
        return "DEGRADED"
    else:
        return "OFFLINE"


def verify_device_authorization(authenticated_device_id: str, target_device_id: str) -> None:
    """Cross-device authorization check: device A cannot write to device B."""
    if authenticated_device_id != target_device_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Cross-device access forbidden: device '{authenticated_device_id}' "
                f"cannot access resources of device '{target_device_id}'."
            ),
        )


_replay_manager = ReplayProtectionManager()
_identity_extractor = SecurityIdentityExtractor()
_rate_limiter = RateLimiter()
_websocket_registry = ActiveWebSocketRegistry()


def get_replay_manager() -> ReplayProtectionManager:
    return _replay_manager


def get_identity_extractor() -> SecurityIdentityExtractor:
    return _identity_extractor


def get_rate_limiter() -> RateLimiter:
    return _rate_limiter


def get_websocket_registry() -> ActiveWebSocketRegistry:
    return _websocket_registry
