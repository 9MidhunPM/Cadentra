"""Resolve one client address across an explicit production proxy trust boundary.

Uvicorn proxy-header rewriting must be disabled so request.client is the original
socket peer. The trusted web proxy overwrites the private client-IP header after
validating its own upstream chain. Public forwarding headers are never read here.
"""

from ipaddress import ip_address

from starlette.requests import Request

from app.core.config import Settings
from app.core.errors import DomainError


def resolve_client_ip(request: Request, settings: Settings) -> str:
    peer = request.client.host if request.client else "unknown"
    if settings.app_env != "production":
        return peer
    try:
        socket_ip = ip_address(peer)
    except ValueError:
        raise _untrusted_proxy() from None
    if (
        socket_ip.is_loopback
        and request.method in {"GET", "HEAD"}
        and request.url.path == "/api/v1/health"
    ):
        return str(socket_ip)
    if str(socket_ip) not in settings.trusted_web_proxy_ips:
        raise _untrusted_proxy()
    values = [
        value
        for name, value in request.scope["headers"]
        if name.lower() == b"x-cadentra-client-ip"
    ]
    if len(values) != 1:
        raise _untrusted_proxy()
    try:
        value = values[0].decode("ascii")
        if "%" in value:
            raise ValueError("Scoped addresses are not client identities")
        client_ip = ip_address(value)
        if str(client_ip) != value:
            raise ValueError("Expected one canonical address")
    except (ValueError, UnicodeDecodeError):
        raise _untrusted_proxy() from None
    return str(client_ip)


def _untrusted_proxy() -> DomainError:
    return DomainError("UNTRUSTED_PROXY", "Request proxy verification failed.", 403)
