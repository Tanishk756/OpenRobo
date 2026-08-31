import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # AWS metadata & Link-Local
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

def validate_external_url(url: str) -> bool:
    """
    SSRF Protection: Validates external repository URLs, preventing requests
    to internal private networks, localhost, or cloud metadata endpoints.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL scheme must be http or https.")

        hostname = parsed.hostname
        if not hostname:
            raise ValueError("Invalid URL hostname.")

        # Resolve hostname to IP
        ip_addr_str = socket.gethostbyname(hostname)
        ip_addr = ipaddress.ip_address(ip_addr_str)

        for blocked_net in BLOCKED_IP_NETWORKS:
            if ip_addr in blocked_net:
                raise ValueError(f"URL resolves to restricted IP range: {ip_addr}")

        return True
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SSRF Security Violation: Invalid or forbidden external URL. Reason: {e}"
        )

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response
