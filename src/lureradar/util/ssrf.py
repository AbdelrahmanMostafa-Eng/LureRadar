"""SSRF guard: decide whether an address or URL may be contacted.

Rules (see docs/THREAT_MODEL.md):

* only ``http``/``https``; only ports 80, 443, 8080, 8443;
* no credentials in URLs;
* every resolved address must be globally routable: loopback, private,
  link-local (incl. cloud metadata 169.254.169.254), CGNAT, multicast,
  reserved, documentation and unspecified ranges are refused, including
  IPv4-mapped/compatible IPv6 forms and NAT64/6to4 embeddings;
* if *any* resolved address is refused, the host is refused (defeats
  round-robin DNS rebinding); the caller then connects to a vetted IP only.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from lureradar.errors import FetchBlockedError

ALLOWED_SCHEMES = frozenset({"http", "https"})
ALLOWED_PORTS = frozenset({80, 443, 8080, 8443})
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_6TO4 = ipaddress.ip_network("2002::/16")
_EXTRA_BLOCKED = tuple(
    ipaddress.ip_network(n)
    for n in (
        "0.0.0.0/8",
        "100.64.0.0/10",  # CGNAT (also Alibaba metadata 100.100.100.200)
        "192.0.0.0/24",
        "198.18.0.0/15",
        "240.0.0.0/4",
        "fc00::/7",
        "fe80::/10",
        "fd00:ec2::/32",  # AWS IMDS IPv6
    )
)

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


def _embedded_v4(ip: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if ip in _NAT64:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    # deprecated IPv4-compatible ::a.b.c.d
    if int(ip) >> 32 == 0 and int(ip) > 0xFFFF:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return None


def is_public_ip(value: str | IPAddress) -> bool:
    """True only for globally routable unicast addresses."""
    try:
        ip = ipaddress.ip_address(value) if isinstance(value, str) else value
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        # transition mechanisms (6to4, Teredo) are refused outright
        if ip.scope_id or ip in _6TO4 or ip.teredo is not None:
            return False
        embedded = _embedded_v4(ip)
        if embedded is not None:
            return is_public_ip(embedded)
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or not ip.is_global
    ):
        return False
    return not any(ip in net for net in _EXTRA_BLOCKED if net.version == ip.version)


@dataclass(frozen=True)
class SafeURL:
    scheme: str
    host: str
    port: int
    path: str  # path + query, never empty

    @property
    def default_port(self) -> bool:
        return (self.scheme, self.port) in (("http", 80), ("https", 443))


def validate_url(url: str) -> SafeURL:
    """Syntactic checks before any DNS lookup. Raises FetchBlockedError."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise FetchBlockedError(f"malformed URL: {exc}") from exc
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise FetchBlockedError(f"scheme {scheme!r} not allowed")
    if parts.username or parts.password:
        raise FetchBlockedError("credentials in URL not allowed")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise FetchBlockedError("missing host")
    if port is None:
        port = 443 if scheme == "https" else 80
    if port not in ALLOWED_PORTS:
        raise FetchBlockedError(f"port {port} not allowed")
    if host in ("localhost",) or host.endswith((".localhost", ".local", ".internal", ".home.arpa")):
        raise FetchBlockedError(f"internal hostname {host!r} not allowed")
    labels = host.split(".")
    if all(re.fullmatch(r"0x[0-9a-f]*|[0-9]+", label) for label in labels):
        # inet_aton() accepts hex/octal/short forms such as 0x7f000001 or 127.1
        try:
            literal_ok = is_public_ip(ipaddress.ip_address(host))
        except ValueError:
            literal_ok = False
        if not literal_ok:
            raise FetchBlockedError(f"numeric host {host!r} not allowed")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not is_public_ip(literal):
        raise FetchBlockedError(f"address {host} is not public")
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    return SafeURL(scheme=scheme, host=host, port=port, path=path)


def vet_addresses(host: str, addresses: list[str]) -> list[str]:
    """Return the vetted addresses, or raise if any is non-public / none exist."""
    if not addresses:
        raise FetchBlockedError(f"{host}: no addresses")
    bad = [a for a in addresses if not is_public_ip(a)]
    if bad:
        raise FetchBlockedError(f"{host} resolves to non-public address(es): {', '.join(bad)}")
    return addresses
