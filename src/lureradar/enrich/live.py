"""Live enrichment orchestration for ``check --live`` and the pipeline.

Order: SSRF guard -> DNS -> (RDAP, TLS, hardened HTTP fetch) in parallel ->
configured reputation lookups. Every failure is recorded in
``Enrichment.errors`` and never aborts the verdict. ``Enrichment.contacted``
lists every host/service contacted, for transparency (docs/PRIVACY.md).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from lureradar.config import Settings
from lureradar.detectors.base import CampaignIndex, build_indexes
from lureradar.detectors.content import extract_features
from lureradar.enrich.dns import DnsResolver
from lureradar.enrich.http_fetch import HardenedFetcher, Resolver
from lureradar.enrich.rdap import RdapClient
from lureradar.enrich.tls import inspect_tls
from lureradar.enrich.types import DnsInfo, Enrichment, HttpInfo
from lureradar.errors import FetchBlockedError, LureRadarError
from lureradar.models import ParsedTarget
from lureradar.packs.loader import load_packs
from lureradar.sources.base import ReputationLookup
from lureradar.util.ssrf import is_public_ip, validate_url


def _short(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:160]}"


class LiveEnricher:
    """Callable ``(ParsedTarget) -> Enrichment`` used by the engine."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        fetcher: HardenedFetcher | None = None,
        resolver: Resolver | None = None,
        dns: DnsResolver | None = None,
        rdap: RdapClient | None = None,
        reputation: list[ReputationLookup] | None = None,
        indexes: tuple[CampaignIndex, ...] | None = None,
        tls: bool = True,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.dns = dns or DnsResolver()
        self.resolver: Resolver = resolver or self.dns
        self.fetcher = fetcher or HardenedFetcher(self.settings.limits, resolver=self.resolver)
        self.rdap = rdap or RdapClient()
        self.reputation = reputation if reputation is not None else []
        self._indexes = indexes
        self.tls = tls

    @classmethod
    def from_env(cls) -> LiveEnricher:
        """Reputation lookups are enabled only for sources with a configured key."""
        from lureradar.sources.safebrowsing import SafeBrowsingSource
        from lureradar.sources.urlhaus import UrlhausSource
        from lureradar.sources.urlscan import UrlscanSource

        s = Settings.from_env()
        rep: list[ReputationLookup] = []
        if s.safebrowsing_key:
            rep.append(SafeBrowsingSource(s))
        if s.urlhaus_key:
            rep.append(UrlhausSource(s))
        if s.urlscan_key:
            rep.append(UrlscanSource(s))
        return cls(settings=s, reputation=rep)

    @property
    def indexes(self) -> tuple[CampaignIndex, ...]:
        if self._indexes is None:
            self._indexes = build_indexes(load_packs())
        return self._indexes

    async def _dns(self, host: str, e: Enrichment) -> list[str]:
        try:
            e.dns = await self.dns.lookup(host)
        except Exception as exc:
            e.errors.append(f"dns: {_short(exc)}")
            e.dns = DnsInfo()
        e.contacted.append("dns resolver")
        return (e.dns.a + e.dns.aaaa) if e.dns else []

    async def _rdap(self, target: ParsedTarget, e: Enrichment) -> None:
        try:
            e.rdap = await self.rdap.lookup(target.registrable_domain)
            e.contacted.append(f"rdap ({e.rdap.server or 'bootstrap'})")
        except (LureRadarError, ValueError) as exc:
            e.errors.append(f"rdap: {_short(exc)}")

    async def _tls(self, target: ParsedTarget, ip: str, e: Enrichment) -> None:
        try:
            e.tls, _verified = await inspect_tls(ip, target.host)
            e.contacted.append(f"{target.host}:443 (tls)")
        except (OSError, TimeoutError, ValueError) as exc:
            e.errors.append(f"tls: {_short(exc)}")

    async def _http(self, target: ParsedTarget, e: Enrichment) -> None:
        url = target.url or f"https://{target.host}/"
        try:
            res = await self.fetcher.fetch(url)
        except FetchBlockedError as exc:
            e.http = HttpInfo(final_url=url, status=0, blocked_reason=str(exc)[:200])
            e.errors.append(f"http: {exc}")
            return
        e.contacted.append(f"{target.host} (http)")
        features = None
        if res.content_type in ("text/html", "application/xhtml+xml", "text/plain") and res.body:
            features = extract_features(res.text(), res.final_url, self.indexes)
        e.http = HttpInfo(
            final_url=res.final_url,
            status=res.status,
            hops=res.hops,
            content_type=res.content_type,
            body_sha256=res.sha256,
            bytes_read=len(res.body),
            truncated=res.truncated,
            features=features,
        )

    async def _reputation(self, target: ParsedTarget, e: Enrichment) -> None:
        async def one(src: ReputationLookup) -> None:
            try:
                hits = await asyncio.to_thread(src.lookup, target.host, target.url)
                e.reputation.extend(hits)
                e.contacted.append(src.info.name)
            except Exception as exc:
                e.errors.append(f"{src.info.name}: {_short(exc)}")

        await asyncio.gather(*(one(s) for s in self.reputation))

    async def enrich_async(self, target: ParsedTarget) -> Enrichment:
        e = Enrichment()
        if target.is_ip:
            if not is_public_ip(target.host):
                e.errors.append("target address is not public: not contacted")
                return e
            addresses = [target.host]
        else:
            try:
                validate_url(target.url or f"https://{target.host}/")
            except FetchBlockedError as exc:
                e.errors.append(f"blocked: {exc}")
                return e
            addresses = await self._dns(target.host, e)
        public = [a for a in addresses if is_public_ip(a)]
        jobs: list[Any] = [self._rdap(target, e), self._reputation(target, e)]
        if addresses and len(public) == len(addresses):
            jobs.append(self._http(target, e))
            if self.tls:
                jobs.append(self._tls(target, public[0], e))
        elif addresses:
            e.errors.append("target resolves to a non-public address: page not fetched")
        await asyncio.gather(*jobs)
        return e

    def __call__(self, target: ParsedTarget) -> Enrichment:
        return asyncio.run(self.enrich_async(target))


class FixtureEnricher:
    """Serve recorded Enrichment JSON (``<host>.json``) for offline pipeline runs."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def __call__(self, target: ParsedTarget) -> Enrichment:
        path = self.directory / f"{target.host}.json"
        if not path.is_file():
            return Enrichment(errors=["fixture: no recorded enrichment"])
        return Enrichment.model_validate_json(path.read_text(encoding="utf-8"))
