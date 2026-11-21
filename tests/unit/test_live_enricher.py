"""LiveEnricher end to end with a mocked network (no sockets)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from lureradar.config import FetchLimits
from lureradar.enrich.http_fetch import HardenedFetcher, StaticResolver
from lureradar.enrich.live import FixtureEnricher, LiveEnricher
from lureradar.enrich.types import DnsInfo, Enrichment, RdapInfo
from lureradar.errors import FetchBlockedError
from lureradar.models import Tier
from lureradar.scoring.engine import Engine
from lureradar.sources.openphish import OpenPhishSource
from lureradar.util.domains import parse_target

NOW = datetime(2026, 11, 21, 12, tzinfo=UTC)
FIX = Path(__file__).parents[1] / "fixtures"
LURE = """<html><title>GTA 6 PC Download</title><body>
<h1>Download now</h1><p>Only 12 keys left</p><p>Complete a short survey to unlock the download</p>
<a href="/GTA6_Setup.exe">Get it</a></body></html>"""


class FakeDns:
    def __init__(self, table: dict[str, list[str]]) -> None:
        self.table = table

    async def lookup(self, host: str) -> DnsInfo:
        ips = self.table.get(host, [])
        return DnsInfo(resolved=bool(ips), a=ips)

    async def resolve(self, host: str) -> list[str]:
        return self.table[host]


class FakeRdap:
    def __init__(self, registered: datetime | None) -> None:
        self.registered = registered

    async def lookup(self, registrable: str) -> RdapInfo:
        if self.registered is None:
            raise FetchBlockedError("rdap down")
        return RdapInfo(registered=self.registered, server="https://rdap.test")


def enricher(table: dict[str, list[str]], registered: datetime | None, handler, reputation=None):  # type: ignore[no-untyped-def]
    fetcher = HardenedFetcher(
        FetchLimits(per_host_interval_s=0), resolver=StaticResolver(table),
        transport=httpx.MockTransport(handler),
    )  # fmt: skip
    return LiveEnricher(
        fetcher=fetcher, dns=FakeDns(table), rdap=FakeRdap(registered),  # type: ignore[arg-type]
        reputation=reputation or [], tls=False,
    )  # fmt: skip


def test_full_live_path_raises_tier() -> None:
    table = {"gta6-pc-download.test": ["93.184.215.14"]}

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, text=LURE)

    rep = [OpenPhishSource(fixtures=FIX / "sources")]
    live = enricher(table, NOW - timedelta(days=1), handler, rep)
    e = live(parse_target("gta6-pc-download.test"))
    assert e.dns and e.dns.resolved and e.rdap and e.http and e.http.features
    assert e.http.body_sha256 and e.http.features.survey_gate
    assert "dns resolver" in e.contacted and any("http" in c for c in e.contacted)
    v = Engine(pack_ids=["gta6"], now=NOW).check("gta6-pc-download.test", enricher=live)
    ids = {s.id for s in v.signals}
    assert {"domain_age", "content_lure_patterns"} <= ids
    assert v.tier >= Tier.LIKELY and v.mode == "live"


def test_external_hit_corroborated_to_confirmed() -> None:
    table = {"gta6-pc-early-access.test": ["93.184.215.14"]}
    rep = [OpenPhishSource(fixtures=FIX / "sources")]
    live = enricher(
        table, None, lambda r: httpx.Response(404, headers={"content-type": "text/html"}), rep
    )
    v = Engine(pack_ids=["gta6"], now=NOW).check("gta6-pc-early-access.test", enricher=live)
    assert v.tier is Tier.CONFIRMED and v.corroborated


def test_private_resolution_is_never_fetched() -> None:
    called = []

    def handler(req: httpx.Request) -> httpx.Response:
        called.append(req)
        return httpx.Response(200)

    live = enricher({"evil.test": ["10.0.0.7"]}, None, handler)
    e = live(parse_target("evil.test"))
    assert called == [] and e.http is None
    assert any("non-public" in err for err in e.errors)
    e = live(parse_target("http://127.0.0.1/"))
    assert any("not public" in err for err in e.errors)
    e = live(parse_target("http://db.internal/"))
    assert any("blocked" in err for err in e.errors)


def test_failures_are_recorded_not_fatal() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/zip"}, content=b"PK")

    live = enricher({"zip.test": ["93.184.215.14"]}, None, handler)
    e = live(parse_target("https://zip.test/GTA6.zip"))
    assert e.http and e.http.blocked_reason and "never binaries" in e.http.blocked_reason
    assert any(err.startswith("rdap") for err in e.errors)


def test_fixture_enricher(tmp_path: Path) -> None:
    (tmp_path / "a.test.json").write_text(
        Enrichment(rdap=RdapInfo(registered=NOW)).model_dump_json(), encoding="utf-8"
    )
    fx = FixtureEnricher(tmp_path)
    assert fx(parse_target("a.test")).rdap is not None
    assert fx(parse_target("b.test")).errors


def test_from_env_only_enables_keyed_sources(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    assert LiveEnricher.from_env().reputation == []
    monkeypatch.setenv("LURERADAR_URLHAUS_KEY", "k")
    assert [s.info.name for s in LiveEnricher.from_env().reputation] == ["urlhaus"]
    assert asyncio.iscoroutinefunction(LiveEnricher.enrich_async)
