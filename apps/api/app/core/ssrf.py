"""SSRF protection for configurable provider base URLs (spec §52).

Provider base URLs are a classic SSRF vector (cloud metadata, internal
networks). This module validates URLs before any provider call.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.errors import ValidationFailure

ALLOWED_SCHEMES = {"http", "https"}
# RFC 1918 + loopback + link-local + cloud metadata (169.254.169.254).
_PRIVATE_BLOCKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def validate_base_url(url: str, *, allow_local: bool = False) -> str:
    """Validate a provider base URL for SSRF safety.

    - Must be http/https.
    - Host must be a resolvable public address unless ``allow_local`` (dev only).
    - Cloud-metadata / private / loopback addresses are rejected by default.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValidationFailure("Provider base URL must use http or https.")
    if not parsed.hostname:
        raise ValidationFailure("Provider base URL must include a host.")

    host = parsed.hostname
    if allow_local:
        return url

    # Reject literal private IPs immediately.
    try:
        addr = ipaddress.ip_address(host)
        if any(addr in block for block in _PRIVATE_BLOCKS):
            raise ValidationFailure(
                "Provider base URL must not point to a private/internal address."
            )
    except ValueError:
        # Hostname: resolve and check.
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror:
            raise ValidationFailure("Provider base URL host could not be resolved.")
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if any(ip in block for block in _PRIVATE_BLOCKS):
                raise ValidationFailure("Provider base URL resolves to a private/internal address.")
    return url
