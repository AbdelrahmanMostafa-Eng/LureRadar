from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
import stix2

from lureradar.export import abp, csvfeed, hosts, rpz, stix
from lureradar.export.common import safe_host
from lureradar.export.jsonfeed import FeedDocument
from lureradar.models import Indicator, Signal, Tier

NOW = datetime(2026, 11, 21, 12, tzinfo=UTC)


def ind(domain: str, tier: Tier = Tier.LIKELY, status: str = "active") -> Indicator:
    return Indicator(
        domain=domain, url=f"https://{domain}/free-key", tier=tier, score=80,
        first_seen=NOW, last_seen=NOW, status=status,  # type: ignore[arg-type]
        sources=["crtsh"], packs=["gta6"],
        signals=[Signal(id="keyword_intent_combo", weight=20, explanation="x")],
        dispute_url="https://github.com/x/y/issues/new",
    )  # fmt: skip


DOC = FeedDocument(
    generated_at=NOW,
    indicators=[
        ind("b-gta6-free.test"),
        ind("a-gta6-key.test", Tier.CONFIRMED),
        ind("sus.test", Tier.SUSPICIOUS),
        ind("old.test", status="stale"),
        ind("bad domain;rm -rf"),  # must never reach any output
        ind("evil.test\n0.0.0.0 google.com"),
    ],
)
EXPECTED = ["a-gta6-key.test", "b-gta6-free.test"]


def test_hosts_roundtrip() -> None:
    text = hosts.to_hosts(DOC)
    assert hosts.parse_hosts(text) == EXPECTED
    assert "# generated_at: 2026-11-21T12:00:00Z" in text and "# count: 2" in text
    assert "google.com" not in text and "rm -rf" not in text


def test_domains_and_min_tier() -> None:
    assert hosts.parse_domains(hosts.to_domains(DOC)) == EXPECTED
    assert "sus.test" in hosts.parse_domains(hosts.to_domains(DOC, Tier.SUSPICIOUS))


def test_abp_roundtrip() -> None:
    text = abp.to_abp(DOC)
    assert text.startswith("[Adblock Plus 2.0]\n! Title: LureRadar")
    assert abp.parse_abp(text) == EXPECTED
    with pytest.raises(ValueError):
        abp.parse_abp("||ok.test^\n/regex/")


def test_rpz_roundtrip() -> None:
    text = rpz.to_rpz(DOC)
    assert "$ORIGIN rpz.lureradar.invalid." in text and "2026112112" in text
    assert "*.a-gta6-key.test CNAME ." in text
    assert rpz.parse_rpz(text) == EXPECTED
    with pytest.raises(ValueError):
        rpz.parse_rpz("evil.test A 1.2.3.4")


def test_csv_roundtrip() -> None:
    rows = csvfeed.parse_csv(csvfeed.to_csv(DOC))
    assert [r["domain"] for r in rows] == EXPECTED
    assert rows[0]["url_defanged"] == "hxxps://a-gta6-key[.]test/free-key"
    assert rows[0]["signals"] == "keyword_intent_combo:+20"


def test_stix_bundle_is_valid_stix21() -> None:
    text = stix.to_stix(DOC)
    bundle = stix2.parse(text, allow_custom=False)
    indicators = [o for o in bundle.objects if o.type == "indicator"]
    assert sorted(i.pattern for i in indicators) == [
        f"[domain-name:value = '{d}']" for d in EXPECTED
    ]
    assert {i.confidence for i in indicators} == {75, 95}
    again = json.loads(stix.to_stix(DOC))
    assert again["id"] == json.loads(text)["id"]  # deterministic ids


@pytest.mark.parametrize(
    ("raw", "ok"),
    [("a.test", True), ("A.Test.", True), ("1.2.3.4", False), ("a b.test", False),
     ("-a.test", False), ("x" * 64 + ".test", False), ("a.test\nb.test", False)],
)  # fmt: skip
def test_safe_host(raw: str, ok: bool) -> None:
    assert (safe_host(raw) is not None) is ok
