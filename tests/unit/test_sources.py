from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from lureradar.config import Settings
from lureradar.errors import SourceError
from lureradar.sources import build_sources
from lureradar.sources.base import ReputationLookup, Source
from lureradar.sources.community_reports import CommunityReportsSource, load_reports
from lureradar.sources.ct_certstream import CertStreamSource, parse_message
from lureradar.sources.ct_crtsh import CrtShSource
from lureradar.sources.openphish import OpenPhishSource
from lureradar.sources.safebrowsing import SafeBrowsingSource
from lureradar.sources.urlhaus import UrlhausSource
from lureradar.sources.urlscan import UrlscanSource

FIX = Path(__file__).parents[1] / "fixtures" / "sources"
SINCE = datetime(2026, 11, 1, tzinfo=UTC)


def test_registry_implements_protocols() -> None:
    sources = build_sources(fixtures=FIX)
    assert {s.info.name for s in sources} == {
        "crtsh",
        "openphish",
        "urlhaus",
        "urlscan",
        "safebrowsing",
        "community",
        "certstream",
    }
    for s in sources:
        assert isinstance(s, Source)
        assert s.info.terms_url and s.info.rate_limit and s.info.redistribution
    assert isinstance(OpenPhishSource(fixtures=FIX), ReputationLookup)


def test_crtsh_fixture() -> None:
    cands = list(CrtShSource(fixtures=FIX).fetch(SINCE))
    domains = [c.domain for c in cands]
    assert "rockstar-gta6-pc-download.test" in domains
    assert domains.count("rockstar-gta6-pc-download.test") == 2  # SAN + wildcard
    assert "old-gta6-fan-wiki.test" not in domains  # before `since`
    assert all(c.source == "crtsh" for c in cands)
    assert cands[0].metadata["cert_id"] == 9000000001


def test_crtsh_live_path_with_mock_client() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if "gtavi" in str(req.url):
            return httpx.Response(503)
        return httpx.Response(200, content=(FIX / "crtsh.json").read_bytes())

    src = CrtShSource(
        keywords=["gta6", "gtavi"], client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    src.interval_s = 0
    src.backoff_s = 0
    assert len(list(src.fetch(SINCE))) >= 7


def test_retry_then_source_error() -> None:
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429)

    src = OpenPhishSource(client=httpx.Client(transport=httpx.MockTransport(handler)))
    src.backoff_s = 0
    with pytest.raises(SourceError, match="HTTP 429"):
        src.request("GET", "https://openphish.test/feed.txt")
    assert len(calls) == 3


def test_openphish_fixture_and_lookup() -> None:
    src = OpenPhishSource(fixtures=FIX)
    cands = list(src.fetch(SINCE))
    assert {c.domain for c in cands} >= {"rockstargames-account-verify.test", "bank-login.example"}
    assert all(c.reputation_hit for c in cands)
    assert src.lookup("gta6-pc-early-access.test")[0].source == "openphish"
    assert src.lookup("clean.test") == []


def test_urlhaus() -> None:
    src = UrlhausSource(fixtures=FIX)
    cands = list(src.fetch(SINCE))
    assert [c.domain for c in cands] == ["gta6-crack-download.test", "203.0.113.7"]
    assert "1 online" in src.lookup("gta6-crack-download.test")[0].detail
    assert UrlhausSource(Settings()).health().status == "requires_key"
    assert list(UrlhausSource(Settings()).fetch(SINCE)) == []
    assert UrlhausSource(Settings()).lookup("a.test") == []


def test_urlscan() -> None:
    src = UrlscanSource(fixtures=FIX)
    cands = list(src.fetch(SINCE))
    assert {c.domain: c.reputation_hit for c in cands} == {
        "gta6-keygen-online.test": True,
        "gta6-community-hub.test": False,
    }
    assert src.lookup("gta6-keygen-online.test")
    assert src.lookup("gta6-community-hub.test") == []


def test_safebrowsing() -> None:
    src = SafeBrowsingSource(fixtures=FIX)
    assert list(src.fetch(SINCE)) == []
    assert src.lookup("x.test")[0].detail == "SOCIAL_ENGINEERING"
    assert src.health().status == "degraded"
    assert SafeBrowsingSource(Settings()).health().status == "requires_key"
    assert SafeBrowsingSource(Settings()).lookup("a.test") == []


def test_certstream_parse() -> None:
    cands = list(CertStreamSource(fixtures=FIX).fetch(SINCE))
    assert [c.domain for c in cands] == ["gta6-beta-keys.test", "gta6-beta-keys.test"]
    assert list(parse_message({"message_type": "heartbeat"})) == []
    assert CertStreamSource().health().status == "disabled"


def test_community_reports() -> None:
    reports, errors = load_reports(FIX / "reports")
    assert len(reports) == 1 and errors and "defanged" in errors[0]
    src = CommunityReportsSource(fixtures=FIX)
    (cand,) = list(src.fetch(SINCE))
    assert cand.domain == "gta6-pc-beta-invite.test" and cand.source == "community"
    assert src.health().status == "degraded"
    missing = CommunityReportsSource(reports_dir=Path("/nonexistent"))
    assert missing.health().status == "disabled"


def test_fixture_health_and_missing_fixture(tmp_path: Path) -> None:
    assert CrtShSource(fixtures=FIX).health().status == "degraded"
    with pytest.raises(SourceError, match="missing"):
        list(CrtShSource(fixtures=tmp_path).fetch(SINCE))
    with pytest.raises(SourceError, match="no fixtures"):
        CrtShSource().fixture_bytes()


def test_live_health_with_mock_client() -> None:
    ok = CrtShSource(
        client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    )
    assert ok.health().status == "ok"
    down = CrtShSource(
        client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(502)))
    )
    assert down.health().status == "down"

    def boom(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("blocked")

    err = OpenPhishSource(client=httpx.Client(transport=httpx.MockTransport(boom)))
    assert err.health().status == "down"
    err.close()
