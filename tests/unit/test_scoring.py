from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from lureradar.enrich.types import Enrichment, RdapInfo, ReputationHit
from lureradar.export.jsonfeed import FeedDocument
from lureradar.models import Indicator, Signal, TargetKind, Tier
from lureradar.pipeline.snapshot import FeedSnapshot
from lureradar.scoring import tiers
from lureradar.scoring.engine import Engine, quick_check
from lureradar.scoring.explain import SIGNAL_DOCS, headline

NOW = datetime(2026, 11, 21, 12, tzinfo=UTC)
ENGINE = Engine(pack_ids=["gta6"], now=NOW)


def sig(sid: str, w: int, cat: str = "lexical", evidence: tuple[str, ...] = ()) -> Signal:
    return Signal(id=sid, weight=w, explanation=sid, category=cat, evidence=evidence)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("score", "tier"),
    [
        (0, Tier.CLEAR),
        (39, Tier.CLEAR),
        (40, Tier.SUSPICIOUS),
        (69, Tier.SUSPICIOUS),
        (70, Tier.LIKELY),
        (89, Tier.LIKELY),
        (90, Tier.CONFIRMED),
        (100, Tier.CONFIRMED),
    ],
)
def test_tier_thresholds(score: int, tier: Tier) -> None:
    assert tiers.tier_for_score(score) is tier


def test_clamp_and_total() -> None:
    assert tiers.total([sig("a", 80), sig("b", 80)]) == 100
    assert tiers.total([sig("a", -50)]) == 0


def test_corroboration_rules() -> None:
    ext1 = sig("external_reputation", 40, "reputation", ("urlhaus: x",))
    assert not tiers.is_corroborated([ext1])
    assert tiers.is_corroborated([ext1, sig("keyword_intent_combo", 20)])
    ext2 = sig("external_reputation", 40, "reputation", ("urlhaus: x", "openphish: y"))
    assert tiers.is_corroborated([ext2])
    assert not tiers.is_corroborated([sig("abused_tld", 8, "infrastructure")])


def test_decide_overrides() -> None:
    assert tiers.decide(95, [], outlet=True) == (Tier.CLEAR, False)
    assert tiers.decide(75, [], platform=True)[0] is Tier.SUSPICIOUS
    assert tiers.decide(10, [], floor=Tier.LIKELY)[0] is Tier.LIKELY
    ext2 = sig("external_reputation", 40, "reputation", ("a: x", "b: y"))
    assert tiers.decide(40, [ext2], platform=True) == (Tier.CONFIRMED, True)


def test_tier_ordering_and_exit_codes() -> None:
    assert Tier.CLEAR < Tier.SUSPICIOUS < Tier.LIKELY < Tier.CONFIRMED
    assert Tier.LIKELY >= Tier.LIKELY and Tier.CLEAR <= Tier.CLEAR
    assert [t.exit_code for t in Tier] == [0, 10, 20, 30]
    assert Tier.parse(" Likely ") is Tier.LIKELY
    with pytest.raises(ValueError, match="unknown tier"):
        Tier.parse("bad")
    assert Tier.CLEAR.__lt__(1) is NotImplemented


def test_demo_command_verdict() -> None:
    v = ENGINE.check("https://rockstar-gta6-pc-download[.]test/free-key")
    assert v.tier is Tier.LIKELY and v.score == 75
    assert {s.id for s in v.signals} == {
        "claims_unreleased_platform",
        "brand_impersonation",
        "keyword_intent_combo",
    }
    assert v.target == "hxxps://rockstar-gta6-pc-download[.]test/free-key"
    assert v.host == "rockstar-gta6-pc-download[.]test"
    assert v.mode == "offline" and v.packs == ["gta6"]
    assert any("facts.yaml" in s for s in v.next_steps)
    assert headline(v).startswith("Looks like a launch lure")


@pytest.mark.parametrize(
    "raw",
    [
        "https://www.ign.com/articles/gta-6-pc-download",
        "store.steampowered.com",
        "en.wikipedia.org",
    ],
)
def test_allowlisted_is_hard_clear(raw: str) -> None:
    v = ENGINE.check(raw)
    assert v.tier is Tier.CLEAR and v.score == 0 and v.allowlisted
    assert headline(v) == "Allowlisted legitimate outlet"


def test_platform_url_is_capped() -> None:
    v = ENGINE.check("https://www.mediafire.com/file/x/gta6-pc-download-free-crack-keygen-setup")
    assert v.tier <= Tier.SUSPICIOUS
    assert any(s.id == "user_content_platform" for s in v.signals)


def test_live_signals_push_lure_to_likely() -> None:
    target = "gta6-pc-download-free.xyz"
    assert ENGINE.check(target).tier is Tier.SUSPICIOUS
    e = Enrichment(rdap=RdapInfo(registered=NOW - timedelta(days=1)))
    v = ENGINE.check(target, enricher=lambda _t: e)
    assert v.tier is Tier.LIKELY and v.mode == "live"


def test_corroborated_external_hit_is_confirmed() -> None:
    e = Enrichment(reputation=[ReputationHit(source="openphish", detail="phishing")])
    v = ENGINE.check("gta6-free-download.test", enricher=lambda _t: e)
    assert v.tier is Tier.CONFIRMED and v.corroborated
    assert any("--abuse" in s for s in v.next_steps)


def test_established_domain_lowers_score() -> None:
    e = Enrichment(rdap=RdapInfo(registered=NOW - timedelta(days=900)))
    v = ENGINE.check("steamy-recipes.test", enricher=lambda _t: e)
    assert any(s.id == "established_domain" for s in v.signals)


def test_snapshot_floor() -> None:
    ind = Indicator(
        domain="quiet-domain.test", tier=Tier.LIKELY, score=80, first_seen=NOW, last_seen=NOW
    )
    snap = FeedSnapshot.from_document(FeedDocument(generated_at=NOW, indicators=[ind]))
    v = Engine(pack_ids=["gta6"], snapshot=snap, now=NOW).check("quiet-domain.test")
    assert v.tier is Tier.LIKELY
    assert any(s.id == "feed_listed" for s in v.signals)
    assert len(snap) == 1 and snap.lookup("") is None


def test_text_verdict_combines_urls() -> None:
    v = ENGINE.check("free gta 6 pc key at gta6-pc-download.test")
    assert v.kind is TargetKind.TEXT and v.urls
    assert v.tier >= Tier.SUSPICIOUS


def test_assess_rejects_text() -> None:
    from lureradar.util.domains import parse_target

    with pytest.raises(ValueError, match="text"):
        ENGINE.assess(parse_target("some words here"))


def test_quick_check() -> None:
    assert quick_check("gta6-pc-download.test").tier >= Tier.SUSPICIOUS


def test_every_emitted_signal_is_documented() -> None:
    from pathlib import Path

    doc = Path(__file__).parents[2] / "docs" / "SIGNALS.md"
    for sid in SIGNAL_DOCS:
        assert sid in SIGNAL_DOCS
    if doc.exists():
        text = doc.read_text(encoding="utf-8")
        missing = [sid for sid in SIGNAL_DOCS if f"`{sid}`" not in text]
        assert not missing, f"undocumented in docs/SIGNALS.md: {missing}"
