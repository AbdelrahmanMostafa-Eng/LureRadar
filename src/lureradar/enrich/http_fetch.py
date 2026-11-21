"""Hardened HTTP fetcher for untrusted URLs.

Guarantees (each covered by tests in tests/unit/test_http_fetch.py):

* SSRF guard on every hop: scheme/port allowlist, no credentials, every DNS
  answer must be public; the connection is pinned to a vetted IP (TLS SNI and
  certificate checks still use the hostname), which defeats DNS rebinding.
* at most ``max_redirects`` redirects, each re-validated and re-resolved;
* one overall deadline for the whole fetch (default 10 s);
* body capped at ``max_body_bytes`` (default 1 MB) *after* decompression;
* only text content types; binaries and attachments are refused before any
  body byte is read; JavaScript is never executed (we only parse HTML text);
* no cookies, no proxy environment, honest User-Agent;
* per-host politeness interval and a global concurrency cap.

Only hashes and extracted features leave this module, never page copies.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import socket
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urljoin

import httpx

from lureradar.config import FetchLimits, user_agent
from lureradar.enrich.types import RedirectHop
from lureradar.errors import FetchBlockedError
from lureradar.util.ratelimit import HostRateLimiter
from lureradar.util.ssrf import SafeURL, validate_url, vet_addresses

TEXT_TYPES: frozenset[str] = frozenset({"text/html", "application/xhtml+xml", "text/plain"})
JSON_TYPES: frozenset[str] = frozenset(
    {"application/json", "application/rdap+json", "application/feed+json"}
)
FEED_TYPES: frozenset[str] = frozenset(
    {"application/atom+xml", "application/rss+xml", "application/xml", "text/xml"}
)
REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})


class Resolver(Protocol):
    async def resolve(self, host: str) -> list[str]: ...


class SystemResolver:
    """Resolve with the OS resolver (A + AAAA), without caching."""

    async def resolve(self, host: str) -> list[str]:
        loop = asyncio.get_running_loop()
        try:
            infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise FetchBlockedError(f"{host}: DNS resolution failed ({exc.strerror})") from exc
        return list(dict.fromkeys(str(info[4][0]) for info in infos))


class StaticResolver:
    """Deterministic resolver for tests and fixtures."""

    def __init__(self, table: dict[str, list[str]]) -> None:
        self.table = {k.lower(): v for k, v in table.items()}

    async def resolve(self, host: str) -> list[str]:
        if host.lower() not in self.table:
            raise FetchBlockedError(f"{host}: DNS resolution failed (static table)")
        return list(self.table[host.lower()])


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int
    hops: list[RedirectHop] = field(default_factory=list)
    content_type: str | None = None
    body: bytes = b""
    truncated: bool = False
    peer_ip: str | None = None

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.body).hexdigest()

    def text(self, max_chars: int = 2_000_000) -> str:
        return self.body.decode("utf-8", errors="replace")[:max_chars]


def _media_type(header: str | None) -> str:
    return (header or "").split(";", 1)[0].strip().lower()


def _url_host(ip: str) -> str:
    return f"[{ip}]" if ":" in ip else ip


class HardenedFetcher:
    """Fetch untrusted URLs safely. One instance can serve many fetches."""

    def __init__(
        self,
        limits: FetchLimits | None = None,
        *,
        resolver: Resolver | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        rate_limiter: HostRateLimiter | None = None,
        allowed_types: Iterable[str] = TEXT_TYPES,
        agent: str | None = None,
        _allow_private_for_tests: bool = False,
    ) -> None:
        self.limits = limits or FetchLimits()
        self.resolver: Resolver = resolver or SystemResolver()
        self.transport = transport
        self.rate = rate_limiter or HostRateLimiter(
            self.limits.per_host_interval_s, self.limits.global_concurrency
        )
        self.allowed_types = frozenset(allowed_types)
        self.agent = agent or user_agent()
        # Private-address escape hatch exists only for the local integration test
        # server; it is not reachable from the CLI or environment.
        self._allow_private = _allow_private_for_tests

    async def _vet(self, safe: SafeURL) -> list[str]:
        try:
            literal = ipaddress.ip_address(safe.host)
        except ValueError:
            literal = None
        addresses = [str(literal)] if literal else await self.resolver.resolve(safe.host)
        if self._allow_private:
            if not addresses:
                raise FetchBlockedError(f"{safe.host}: no addresses")
            return addresses
        return vet_addresses(safe.host, addresses)

    def _check(self, url: str) -> SafeURL:
        if self._allow_private:
            # still enforce scheme/port/credentials, skip the address checks
            from urllib.parse import urlsplit

            parts = urlsplit(url)
            if parts.scheme not in ("http", "https") or parts.username or not parts.hostname:
                raise FetchBlockedError("blocked URL")
            port = parts.port or (443 if parts.scheme == "https" else 80)
            path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
            return SafeURL(parts.scheme, parts.hostname.lower(), port, path)
        return validate_url(url)

    async def fetch(self, url: str) -> FetchResult:
        """Fetch ``url`` within the overall deadline. Raises FetchBlockedError."""
        try:
            async with asyncio.timeout(self.limits.timeout_s):
                return await self._fetch(url)
        except TimeoutError as exc:
            raise FetchBlockedError(f"timed out after {self.limits.timeout_s:g}s") from exc
        except httpx.HTTPError as exc:
            raise FetchBlockedError(f"HTTP error: {type(exc).__name__}: {exc}") from exc

    async def _fetch(self, url: str) -> FetchResult:
        hops: list[RedirectHop] = []
        current = url
        timeout = httpx.Timeout(self.limits.timeout_s)
        async with httpx.AsyncClient(
            follow_redirects=False,
            trust_env=False,
            timeout=timeout,
            transport=self.transport,
            headers={"User-Agent": self.agent},
        ) as client:
            for _ in range(self.limits.max_redirects + 1):
                safe = self._check(current)
                addresses = await self._vet(safe)
                ip = addresses[0]
                host_header = safe.host if safe.default_port else f"{safe.host}:{safe.port}"
                pinned = f"{safe.scheme}://{_url_host(ip)}:{safe.port}{safe.path}"
                await self.rate.acquire(safe.host)
                try:
                    request = client.build_request(
                        "GET",
                        pinned,
                        headers={
                            "Host": host_header,
                            "Accept": ", ".join(sorted(self.allowed_types)) + ";q=0.9",
                            "Accept-Language": "en",
                        },
                        extensions={"sni_hostname": safe.host},
                    )
                    response = await client.send(request, stream=True)
                    try:
                        client.cookies.clear()
                        location = response.headers.get("location")
                        if response.status_code in REDIRECT_CODES and location:
                            hops.append(RedirectHop(url=current, status=response.status_code))
                            current = urljoin(current, location)
                            continue
                        return await self._read(response, url, current, hops, ip)
                    finally:
                        await response.aclose()
                finally:
                    self.rate.release()
        raise FetchBlockedError(f"more than {self.limits.max_redirects} redirects")

    async def _read(
        self,
        response: httpx.Response,
        url: str,
        final: str,
        hops: list[RedirectHop],
        ip: str,
    ) -> FetchResult:
        ctype = _media_type(response.headers.get("content-type"))
        disposition = response.headers.get("content-disposition", "").lower()
        result = FetchResult(
            url=url, final_url=final, status=response.status_code, hops=hops,
            content_type=ctype or None, peer_ip=ip,
        )  # fmt: skip
        if "attachment" in disposition:
            raise FetchBlockedError("attachment refused: LureRadar never downloads files")
        if ctype not in self.allowed_types:
            raise FetchBlockedError(
                f"content type {ctype or 'unknown'!r} refused: only text is fetched, never binaries"
            )
        declared = response.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > self.limits.max_body_bytes * 20:
            raise FetchBlockedError(f"declared size {declared} bytes is far above the cap")
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            remaining = self.limits.max_body_bytes - size
            if len(chunk) >= remaining:
                chunks.append(chunk[:remaining])
                size += remaining
                result.truncated = True
                break
            chunks.append(chunk)
            size += len(chunk)
        result.body = b"".join(chunks)
        return result


FetchFn = Callable[[str], Awaitable[FetchResult]]
