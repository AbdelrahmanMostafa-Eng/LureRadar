"""Detector-level tests: each signal fires when it should and stays quiet otherwise."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from lureradar.detectors.base import Context, allow_state, build_indexes, compact
from lureradar.detectors.brand import detect_brand_impersonation
from lureradar.detectors.homoglyph import detect_homoglyph_idn, scripts, skeleton
from lureradar.detectors.intent import detect_claims_unreleased_platform
from lureradar.detectors.lexical import analyse, detect_keyword_intent_combo, find_keywords, segment
from lureradar.detectors.tld import detect_abused_tld
from lureradar.detectors.typosquat import deconfuse_ascii, max_distance, typo_match
from lureradar.packs import load_packs
from lureradar.util.domains import parse_target, to_ascii_host

NOW = datetime(2026, 11, 21, 12, tzinfo=UTC)
INDEXES = build_indexes(load_packs(["gta6"]))
IDX = INDEXES[0]


def ctx(raw: str) -> Context:
    t = parse_target(raw)
    return Context(target=t, indexes=INDEXES, now=NOW, allow=allow_state(t, INDEXES))


def ids(signals: list) -> set[str]:  # type: ignore[type-arg]
    return {s.id for s in signals}


# ----------------------------------------------------------------- lexical
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("gta6-free", ["gta6"]),
        ("GTA_6 download", ["gta 6"]),
        ("grand-theft-auto-vi-keys", ["grand theft auto vi"]),
        ("gtavipc", ["gtavi"]),
        ("gtavideos", []),
        ("gta60fps", []),
        ("vicecity2026", ["vice city 2026"]),
    ],
)
def test_find_keywords(text: str, expected: list[str]) -> None:
    found = [k.replace(" ", "").replace("-", "") for k, _, _ in find_keywords(text, IDX)]
    assert found == [e.replace(" ", "").replace("-", "") for e in expected]


def test_segment_minimises_unknown_chars() -> None:
    words, unknown = segment("pcdownload", IDX.vocabulary, IDX.max_word)
    assert words == ["pc", "download"] and unknown == 0
    words, unknown = segment("npc", IDX.vocabulary, IDX.max_word)
    assert unknown >= 1
    assert segment("", IDX.vocabulary, IDX.max_word) == ([], 0)


@pytest.mark.parametrize(
    ("text", "intents"),
    [
        ("freegta6pckeys", {"free", "pc", "keys"}),
        ("gta6-npc-guide", set()),
        ("gta6-studios", set()),
        ("gta6-monkey", set()),
        ("gta6-early-access", {"earlyaccess"}),
    ],
)
def test_short_intents_need_full_segmentation(text: str, intents: set[str]) -> None:
    assert set(analyse(text, IDX).intents) == intents


def test_keyword_intent_combo_host_vs_path() -> None:
    host = detect_keyword_intent_combo(ctx("gta6-free-download.test"))
    assert host and host[0].weight == 20
    path = detect_keyword_intent_combo(ctx("https://blog.test/gta-6-free-download"))
    assert path and path[0].weight == 10
    assert detect_keyword_intent_combo(ctx("gta6-news.test")) == []
    assert detect_keyword_intent_combo(ctx("free-download.test")) == []


def test_keywords_alone_never_score() -> None:
    assert detect_keyword_intent_combo(ctx("gta6.test")) == []
    assert detect_claims_unreleased_platform(ctx("gta6.test")) == []


# ------------------------------------------------------------------ intent
@pytest.mark.parametrize(
    ("raw", "weight"),
    [
        ("gta6-pc-download.test", 30),
        ("gta6-apk.test", 30),
        ("gta6-ps4-free.test", 30),
        ("https://x.test/gta-6-pc-download", 15),
        ("gta6-pc-news.test", 0),
        ("gta6-ps5-free.test", 0),
        ("pc-download.test", 0),
    ],
)
def test_claims_unreleased_platform(raw: str, weight: int) -> None:
    sigs = detect_claims_unreleased_platform(ctx(raw))
    assert (sigs[0].weight if sigs else 0) == weight
    if sigs:
        assert "as of 2026-11-21" in sigs[0].explanation


def test_released_platform_disables_rule() -> None:
    (pack,) = load_packs(["gta6"])
    assert pack.facts is not None
    facts = pack.facts.model_copy(deep=True)
    facts.platforms["pc"] = facts.platforms["pc"].model_copy(update={"status": "released"})
    released = pack.model_copy(update={"facts": facts})
    idx = build_indexes([released])
    t = parse_target("gta6-pc-download.test")
    c = Context(target=t, indexes=idx, now=NOW, allow=allow_state(t, idx))
    assert detect_claims_unreleased_platform(c) == []


# ---------------------------------------------------------------- typosquat
def test_typo_thresholds() -> None:
    assert max_distance("rockstargames") == 2
    assert max_distance("rockstar") == 1
    assert max_distance("steam") == 0
    assert deconfuse_ascii("r0ckstarg4mes") == "rockstargames"
    assert deconfuse_ascii("stearn") == "steam"


@pytest.mark.parametrize(
    ("cand", "target", "hit"),
    [
        ("rockstarqames", "rockstargames", True),
        ("rockstargamse", "rockstargames", True),
        ("r0ckstargames", "rockstargames", True),
        ("5team", "steam", True),
        ("stearn", "steam", True),
        ("stream", "steam", False),
        ("steak", "steam", False),
        ("steam", "steam", False),
        ("xockstargames", "rockstargames", False),
        ("rockstargamesxyz", "rockstargames", False),
        ("epicgamer", "epicgames", True),
    ],
)
def test_typo_match(cand: str, target: str, hit: bool) -> None:
    assert (typo_match(cand, target) is not None) is hit


# ------------------------------------------------------------------- brand
@pytest.mark.parametrize(
    ("raw", "kind"),
    [
        ("rockstarqames.com", "Typosquat"),
        ("steampowered.xyz", "Exact"),
        ("steam-powered.test", "Exact"),
        ("steamcommunity.com-gift.test", "Combosquat"),
        ("rockstargamessupport.test", "Combosquat"),
        ("freesteamkeys.test", "Combosquat"),
    ],
)
def test_brand_impersonation(raw: str, kind: str) -> None:
    sigs = detect_brand_impersonation(ctx(raw))
    assert sigs, raw
    assert sigs[0].explanation.startswith(kind)
    assert sigs[0].weight == 25


@pytest.mark.parametrize(
    "raw",
    [
        "store.steampowered.com",
        "www.rockstargames.com",
        "steamboat.test",
        "mainstream.test",
        "xboxachievements.com",
        "playstationlifestyle.net",
        "youtube.com",
    ],
)
def test_no_brand_impersonation(raw: str) -> None:
    assert detect_brand_impersonation(ctx(raw)) == []


# ---------------------------------------------------------------- homoglyph
def test_skeleton_and_scripts() -> None:
    assert skeleton("rоckstаr") == "rockstar"
    assert skeleton("ｒｏｃｋ") == "rock"
    assert skeleton("ło") == "lo"
    assert skeleton("café") == "cafe"
    assert scripts("rоck") == {"LATIN", "CYRILLIC"}


def test_homoglyph_idn_brand_and_keyword() -> None:
    brand = detect_homoglyph_idn(ctx(to_ascii_host("rоckstargames.com")))
    assert brand and "Cyrillic" in brand[0].explanation
    kw = detect_homoglyph_idn(ctx(to_ascii_host("gtа6-free.test")))
    assert kw and "campaign keyword" in kw[0].explanation
    assert detect_homoglyph_idn(ctx(to_ascii_host("café-paris.test"))) == []
    assert detect_homoglyph_idn(ctx("rockstargames.test")) == []


# ---------------------------------------------------------------------- tld
def test_abused_tld() -> None:
    assert ids(detect_abused_tld(ctx("gta6-free.xyz"))) == {"abused_tld"}
    assert detect_abused_tld(ctx("gta6-free.test")) == []
    assert detect_abused_tld(ctx("youtube.com")) == []
    assert detect_abused_tld(ctx("192.0.2.1")) == []


# ---------------------------------------------------------------- allowlist
def test_allow_state() -> None:
    assert allow_state(parse_target("www.ign.com"), INDEXES).outlet
    assert allow_state(parse_target("store.steampowered.com"), INDEXES).outlet  # official
    assert allow_state(parse_target("www.youtube.com"), INDEXES).platform
    assert not allow_state(parse_target("foo.github.io"), INDEXES).platform
    assert not allow_state(parse_target("192.0.2.1"), INDEXES).outlet


def test_compact() -> None:
    assert compact("Early-Access 2026") == "earlyaccess2026"
