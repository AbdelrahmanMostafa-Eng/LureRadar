"""PC Watch: every status transition, staleness, official-only rule, coupling."""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from pathlib import Path

import orjson
import pytest
from typer.testing import CliRunner

from lureradar.cli import app
from lureradar.detectors.base import allow_state, build_indexes
from lureradar.errors import PackError
from lureradar.models import Tier
from lureradar.packs import load_packs
from lureradar.packs.schema import Pack
from lureradar.pcwatch.config import PcWatchConfig, load_config
from lureradar.pcwatch.evaluate import Statement, evaluate
from lureradar.pcwatch.feed import badge, load_state, to_atom, to_json, write_outputs
from lureradar.pcwatch.notify import ISSUE_TITLE, issue_body, webhook_payload
from lureradar.pcwatch.sources import PcWatchChecker, parse_atom
from lureradar.pcwatch.status import CheckResult, SourceCheck, Status, honest_sentence, resolve
from lureradar.scoring.engine import Engine
from lureradar.util.domains import parse_target

FIX = Path(__file__).parents[1] / "fixtures" / "pcwatch"
NOW = datetime(2026, 11, 21, 12, tzinfo=UTC)
(PACK,) = load_packs(["gta6"])
CONFIG = load_config(PACK)


def check(scenario: str) -> CheckResult:
    result = PcWatchChecker(CONFIG, fixtures=FIX / scenario).run()
    return result.model_copy(update={"checked_at": NOW})


def with_pc_fact(status: str, value: str | None = None) -> Pack:
    assert PACK.facts is not None
    facts = PACK.facts.model_copy(deep=True)
    facts.facts = [
        f.model_copy(update={"status": status, "value": value}) if f.id == "pc_release" else f
        for f in facts.facts
    ]
    return PACK.model_copy(update={"facts": facts})


# ---------------------------------------------------------------- config
def test_config_and_timeline_are_verified() -> None:
    assert CONFIG.stale_after_hours == 36
    assert {s.id for s in CONFIG.sources if s.required} == {"rockstar-newswire", "take-two-ir"}
    assert CONFIG.timeline, "timeline must be seeded with verified entries"
    for e in CONFIG.timeline:
        assert e.kind == "official" and e.url and e.date and e.verified_on
        host = e.url.host or ""
        assert host.endswith(("rockstargames.com", "take2games.com"))
        assert len(e.paraphrase.split()) <= 40


def test_config_rejects_unofficial_timeline_entry() -> None:
    raw = dict(PACK.pc_watch or {})
    raw["timeline"] = [
        {**raw["timeline"][0], "url": "https://news.example.test/leak"}  # type: ignore[index]
    ]
    with pytest.raises(ValueError, match="not on an official domain"):
        PcWatchConfig.model_validate(raw)
    long_quote = {**(PACK.pc_watch or {})["timeline"][0], "quote": " ".join(["w"] * 16)}  # type: ignore[index]
    with pytest.raises(ValueError, match="15 words"):
        PcWatchConfig.model_validate({**raw, "timeline": [long_quote]})


def test_missing_config() -> None:
    with pytest.raises(PackError, match="no pc_watch"):
        load_config(PACK.model_copy(update={"pc_watch": None}))


# ---------------------------------------------------------------- rules
SRC = CONFIG.source("rockstar-newswire")


@pytest.mark.parametrize(
    ("title", "url", "expected"),
    [
        ("Grand Theft Auto VI Coming to PC on May 4, 2027", "https://www.rockstargames.com/n/1", Status.ANNOUNCED_DATED),
        ("Grand Theft Auto VI is coming to PC", "https://www.rockstargames.com/n/2", Status.ANNOUNCED_UNDATED),
        ("Grand Theft Auto VI Out Now on PC via Steam", "https://www.rockstargames.com/n/3", Status.RELEASED),
        ("Grand Theft Auto VI coming to PC in early 2027", "https://www.rockstargames.com/n/4", Status.ANNOUNCED_DATED),
        ("Grand Theft Auto VI Now Available", "https://www.rockstargames.com/n/5", None),
        ("GTA VI PC version leaked!", "https://news.example.test/leak", None),  # not official
        ("GTA Online PC update", "https://www.rockstargames.com/n/6", None),  # not the game
    ],
)  # fmt: skip
def test_evaluate_rules(title: str, url: str, expected: Status | None) -> None:
    finding = evaluate(Statement(source="x", title=title, url=url), SRC, CONFIG)
    assert (finding.status if finding else None) == expected
    if finding:
        assert len(finding.snippet.split()) <= 15


def test_proximity_and_negation() -> None:
    far = "Grand Theft Auto VI. " + ("filler " * 60) + "Our PC tools team is hiring."
    assert (
        evaluate(Statement("x", "News", "https://www.rockstargames.com/a", far), SRC, CONFIG)
        is None
    )
    neg = evaluate(
        Statement("x", "Grand Theft Auto VI update", "https://www.rockstargames.com/b",
                  "There are no plans for a PC version of Grand Theft Auto VI at this time."),
        SRC, CONFIG,
    )  # fmt: skip
    assert neg is not None and neg.negated


def test_atom_parser_refuses_entities() -> None:
    with pytest.raises(ValueError, match="DTD"):
        parse_atom(
            b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><feed/>', "https://sec.gov/"
        )


# ------------------------------------------------------------ transitions
def test_all_sources_ok_no_findings_is_not_announced() -> None:
    state = resolve(PACK, CONFIG, check("not_announced"), None, NOW)
    assert state.status is Status.NOT_ANNOUNCED and not state.stale and not state.review_pending
    assert state.last_success == NOW
    assert "No official PC release" in honest_sentence(state)
    assert "as of 2026-11-21 12:00 UTC" in honest_sentence(state)


def test_failures_never_produce_not_announced() -> None:
    state = resolve(PACK, CONFIG, check("broken"), None, NOW)
    assert state.status is Status.UNKNOWN and state.stale
    assert state.note.startswith("UNKNOWN (last confirmed NOT_ANNOUNCED")
    failed = {s.id: s.status for s in state.sources}
    assert failed["rockstar-newswire"] == "failed" and failed["take-two-ir"] == "failed"


def test_no_check_at_all_is_unknown() -> None:
    assert resolve(PACK, CONFIG, None, None, NOW).status is Status.UNKNOWN


def test_staleness_guard_36h() -> None:
    good = resolve(PACK, CONFIG, check("not_announced"), None, NOW)
    later = NOW + timedelta(hours=10)
    broken = check("broken").model_copy(update={"checked_at": later})
    still = resolve(PACK, CONFIG, broken, good, later)
    assert still.status is Status.NOT_ANNOUNCED and still.last_success == NOW
    much_later = NOW + timedelta(hours=37)
    broken2 = broken.model_copy(update={"checked_at": much_later})
    stale = resolve(PACK, CONFIG, broken2, still, much_later)
    assert stale.status is Status.UNKNOWN
    assert stale.note == "UNKNOWN (last confirmed NOT_ANNOUNCED on 2026-11-21)"


def test_announcement_needs_maintainer_review() -> None:
    result = check("announced")
    assert result.suggested is Status.ANNOUNCED_DATED
    state = resolve(PACK, CONFIG, result, None, NOW)
    assert state.status is Status.NOT_ANNOUNCED  # unchanged until facts.yaml is edited
    assert state.review_pending and state.suggested_status is Status.ANNOUNCED_DATED
    body = issue_body(state, result)
    assert "maintainer" in body and "facts.yaml" in body and "rockstargames.com" in body
    assert ISSUE_TITLE.startswith("PC Watch")


def test_store_listing_suggests_released() -> None:
    result = check("released")
    assert result.suggested is Status.RELEASED
    steam = next(s for s in result.sources if s.id == "steam-store")
    assert [f.title for f in steam.findings] == ["Grand Theft Auto VI"]  # GTA V not matched


def test_maintainer_flip_changes_status_and_last_changed() -> None:
    first = resolve(PACK, CONFIG, check("not_announced"), None, NOW)
    flipped = with_pc_fact("announced_dated", "2027-05-04")
    later = NOW + timedelta(hours=4)
    second = resolve(
        flipped, CONFIG, check("announced").model_copy(update={"checked_at": later}), first, later
    )
    assert second.status is Status.ANNOUNCED_DATED and not second.review_pending
    assert second.last_changed == later
    assert (
        resolve(with_pc_fact("released"), CONFIG, check("released"), None, NOW).status
        is Status.RELEASED
    )


def test_negated_findings_do_not_suggest_change() -> None:
    src = SourceCheck(id="a", name="a", kind="publisher", status="ok", required=True)
    result = CheckResult(checked_at=NOW, sources=[src])
    assert result.suggested is Status.NOT_ANNOUNCED
    assert not CheckResult(checked_at=NOW, sources=[]).full_success


# ----------------------------------------------------------- coupling
def test_coupling_claims_signal_drops_for_pc_when_announced() -> None:
    url = "gta6-pc-download.test"
    before = Engine([PACK]).check(url)
    assert any(s.id == "claims_unreleased_platform" for s in before.signals)
    for status in ("announced_undated", "announced_dated", "released"):
        after = Engine([with_pc_fact(status)]).check(url)
        assert not any(s.id == "claims_unreleased_platform" for s in after.signals), status
        # other unreleased platforms still fire
        apk = Engine([with_pc_fact(status)]).check("gta6-apk-download.test")
        assert any(s.id == "claims_unreleased_platform" for s in apk.signals)


def test_coupling_storefronts_allowlisted_only_after_announcement() -> None:
    assert PACK.release_storefronts == []
    pack = with_pc_fact("released")
    assert "steampowered.com" in pack.release_storefronts
    idx = build_indexes([pack])
    assert allow_state(parse_target("store.steampowered.com"), idx).outlet
    assert Engine([pack]).check("https://store.steampowered.com/app/1/").tier is Tier.CLEAR


# --------------------------------------------------------------- outputs
def test_outputs_validate(tmp_path: Path) -> None:
    state = resolve(PACK, CONFIG, check("not_announced"), None, NOW)
    paths = write_outputs(state, tmp_path)
    assert {p.name for p in paths} == {"pc-watch.json", "pc-watch.atom", "shields-pc-watch.json"}
    data = orjson.loads((tmp_path / "pc-watch.json").read_bytes())
    assert data["status"] == "NOT_ANNOUNCED" and data["schema_version"] == "1.0"
    assert data["count"] == len(CONFIG.timeline) and data["answer"].startswith("No official PC")
    assert data["generated_at"] and data["disclaimer"]
    root = ET.fromstring(to_atom(state))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    assert root.tag == "{http://www.w3.org/2005/Atom}feed"
    for el in (root, *root.findall("a:entry", ns)):
        assert el.find("a:id", ns) is not None and el.find("a:title", ns) is not None
        assert el.find("a:updated", ns) is not None
    assert len(root.findall("a:entry", ns)) == 1 + len(CONFIG.timeline)
    b = orjson.loads(badge(state))
    assert b["label"] == "PC version" and b["message"].startswith("not announced · checked")
    again = load_state(tmp_path / "pc-watch.json")
    assert again is not None and again.status is Status.NOT_ANNOUNCED
    assert load_state(tmp_path / "missing.json") is None
    assert to_json(state)


def test_unknown_badge_and_webhooks() -> None:
    state = resolve(PACK, CONFIG, None, None, NOW)
    assert orjson.loads(badge(state))["message"].startswith("unknown")
    assert "content" in webhook_payload(state) and "text" in webhook_payload(state, "slack")
    assert webhook_payload(state)["allowed_mentions"] == {"parse": []}


def test_checker_uses_hardened_fetcher_for_live_sources() -> None:
    class Boom:
        async def fetch(self, url: str):  # type: ignore[no-untyped-def]
            from lureradar.errors import FetchBlockedError

            raise FetchBlockedError("blocked by proxy")

    result = asyncio.run(PcWatchChecker(CONFIG, fetcher=Boom()).run_async())  # type: ignore[arg-type]
    assert not result.full_success
    assert resolve(PACK, CONFIG, result, None, NOW).status is Status.UNKNOWN


# ------------------------------------------------------------------- CLI
runner = CliRunner()


def test_cli_check_status_history(tmp_path: Path) -> None:
    out = tmp_path / "feeds"
    issue = tmp_path / "issue.md"
    res = runner.invoke(
        app,
        [
            "pcwatch",
            "check",
            "--fixtures",
            str(FIX / "announced"),
            "--out",
            str(out),
            "--issue-body",
            str(issue),
        ],
    )
    assert res.exit_code == 0, res.output
    assert issue.is_file() and (out / "pc-watch.atom").is_file()
    res = runner.invoke(
        app,
        [
            "pcwatch",
            "check",
            "--fixtures",
            str(FIX / "not_announced"),
            "--issue-body",
            str(issue),
            "--json",
        ],
    )
    assert not issue.exists() and orjson.loads(res.output)["status"] == "NOT_ANNOUNCED"
    status = runner.invoke(app, ["pcwatch", "status", "--state", str(out / "pc-watch.json")])
    assert status.exit_code == 0 and "PC Watch" in status.output
    hist = orjson.loads(runner.invoke(app, ["pcwatch", "history", "--json"]).output)
    assert hist[0]["date"] >= hist[-1]["date"]
    assert "Grand Theft Auto VI" in runner.invoke(app, ["pcwatch", "history"]).output
