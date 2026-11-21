"""DNS enrichment with dnspython (system resolver configuration, short timeouts)."""

from __future__ import annotations

import asyncio

import dns.asyncresolver
import dns.exception
import dns.resolver

from lureradar.enrich.types import DnsInfo
from lureradar.errors import FetchBlockedError

LIFETIME_S = 3.0


class DnsResolver:
    """A/AAAA/NS/MX lookups; also usable as the fetcher's address resolver."""

    def __init__(self, nameservers: list[str] | None = None, lifetime: float = LIFETIME_S) -> None:
        self._resolver = dns.asyncresolver.Resolver(configure=nameservers is None)
        if nameservers:
            self._resolver.nameservers = nameservers
        self._resolver.lifetime = lifetime

    async def _query(self, name: str, rtype: str) -> list[str]:
        try:
            answer = await self._resolver.resolve(name, rtype, raise_on_no_answer=False)
        except (dns.exception.DNSException, OSError):
            return []
        return [r.to_text().rstrip(".") for r in answer]

    async def lookup(self, host: str) -> DnsInfo:
        a, aaaa, ns, mx = await asyncio.gather(
            self._query(host, "A"),
            self._query(host, "AAAA"),
            self._query(host, "NS"),
            self._query(host, "MX"),
        )
        return DnsInfo(resolved=bool(a or aaaa), a=a, aaaa=aaaa, ns=ns, mx=mx)

    async def resolve(self, host: str) -> list[str]:
        info = await self.lookup(host)
        addresses = info.a + info.aaaa
        if not addresses:
            raise FetchBlockedError(f"{host}: DNS resolution failed")
        return addresses
