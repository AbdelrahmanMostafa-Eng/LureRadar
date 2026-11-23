from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from lureradar.cli import app
from lureradar.enrich.types import RdapInfo
from lureradar.report.abuse import build_abuse_report
from lureradar.report.card import headline, render_svg, share_text, write_report
from lureradar.scoring.engine import Engine

STATS = {"new_24h": 37, "new_7d": 120, "active_listed": 300, "generated_at": "2026-11-21T12:00:00Z",
         "top_signals": [{"id": "claims_unreleased_platform", "count": 30}]}  # fmt: skip


def test_headline_and_share() -> None:
    assert headline(STATS) == "37 new fake GTA 6 download sites detected in the last 24 hours"
    assert headline({"new_24h": 1}).startswith("1 new fake GTA 6 download site ")
    assert headline({}).startswith("No new fake")
    assert "(demo data)" in share_text(STATS, demo=True)


def test_card_outputs(tmp_path: Path) -> None:
    svg = render_svg(STATS, demo=True)
    assert "DEMO DATA" in svg and "37 new fake" in svg
    paths = write_report(STATS, tmp_path)
    names = {p.name for p in paths}
    assert {"lure-report.svg", "lure-report.html"} <= names
    if "lure-report.png" in names:
        assert (tmp_path / "lure-report.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_abuse_report() -> None:
    v = Engine(pack_ids=["gta6"]).check("hxxps://rockstar-gta6-pc-download[.]test/free-key")
    rdap = RdapInfo(registered=datetime(2026, 11, 20, tzinfo=UTC), registrar="Example Registrar",
                    abuse_email="abuse@registrar.example")  # fmt: skip
    draft = build_abuse_report(v, rdap)
    assert draft.to == ["abuse@registrar.example"]
    assert "rockstar-gta6-pc-download[.]test" in draft.subject and "Example Registrar" in draft.body
    assert "https://rockstar" not in draft.body  # defanged
    assert build_abuse_report(v).to == []


def test_report_cli(tmp_path: Path) -> None:
    runner = CliRunner()
    res = runner.invoke(app, ["report", "--out", str(tmp_path)])
    assert res.exit_code == 0 and (tmp_path / "lure-report.svg").is_file()
    res = runner.invoke(app, ["report", "--abuse", "www.ign.com"])
    assert res.exit_code == 0 and "does not consider" in res.output
