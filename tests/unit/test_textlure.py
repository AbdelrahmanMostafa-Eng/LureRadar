"""Text-lure analyzer against the synthetic corpus in tests/fixtures/text."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lureradar.models import TargetKind, Tier
from lureradar.scoring.engine import Engine
from lureradar.textlure.patterns import find_warnings

CORPUS = yaml.safe_load(
    (Path(__file__).parents[1] / "fixtures" / "text" / "messages.yaml").read_text(encoding="utf-8")
)
ENGINE = Engine(pack_ids=["gta6"])


def test_corpus_is_large_enough() -> None:
    assert len(CORPUS["lure"]) + len(CORPUS["benign"]) >= 40


@pytest.mark.parametrize("case", CORPUS["lure"], ids=lambda c: c["text"][:40])
def test_lure_messages(case: dict[str, str]) -> None:
    v = ENGINE.check(case["text"])
    assert v.kind is TargetKind.TEXT
    assert v.tier >= Tier(case["min_tier"]), [(s.id, s.weight) for s in v.signals]


@pytest.mark.parametrize("case", CORPUS["benign"], ids=lambda c: c["text"][:40])
def test_benign_messages(case: dict[str, str]) -> None:
    v = ENGINE.check(case["text"])
    assert v.tier <= Tier(case["max_tier"]), [(s.id, s.weight) for s in v.signals]


def test_urls_in_text_are_scored_and_defanged() -> None:
    v = ENGINE.check("Grab it at gta6-pc-download.test now, free keys")
    assert v.urls and v.urls[0].host == "gta6-pc-download[.]test"
    assert "gta6-pc-download[.]test" in v.target
    assert any(s.id == "text_risky_link" for s in v.signals)


def test_reassurance_is_not_a_warning() -> None:
    assert find_warnings("100% legit, no virus, not a scam") == []
    assert find_warnings("this is a scam") != []


def test_warning_needs_a_positive_signal() -> None:
    v = ENGINE.check("beware of scams everyone")
    assert v.signals == [] and v.score == 0


def test_text_without_campaign_still_flags_generic_red_flags() -> None:
    v = ENGINE.check("Disable your antivirus and run setup.exe as administrator, pay in bitcoin")
    got = {s.id for s in v.signals}
    assert {"text_disable_security", "text_executable_lure", "text_payment_red_flag"} <= got
    assert "text_free_key_offer" not in got


def test_cheap_price_only_with_campaign_context() -> None:
    assert any(
        s.id == "text_too_good_to_be_true" for s in ENGINE.check("GTA 6 key only $3").signals
    )
    assert not ENGINE.check("coffee for $3").signals
