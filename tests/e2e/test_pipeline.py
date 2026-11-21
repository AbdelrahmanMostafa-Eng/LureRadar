"""End-to-end pipeline on recorded fixtures: scan -> state -> feeds -> verify."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lureradar.cli import app
from lureradar.export import jsonfeed
from lureradar.export.signing import generate
from lureradar.export.verify import verify_feed_dir
from lureradar.models import Signal, Tier
from lureradar.pipeline.orchestrator import ScanConfig, run_scan
from lureradar.pipeline.state import State

FIX = Path(__file__).parents[1] / "fixtures"
NOW = datetime(2026, 11, 21, 12, tzinfo=UTC)
runner = CliRunner()


def scan(tmp: Path, **kw: object) -> dict:  # type: ignore[type-arg]
    cfg = ScanConfig(
        state_path=tmp / "state.db", out_dir=tmp / "feeds", fixtures=FIX, now=NOW, **kw
    )  # type: ignore[arg-type]
    return run_scan(cfg)


def test_scan_end_to_end(tmp_path: Path) -> None:
    report = scan(tmp_path)
    assert report["sources"]["crtsh"]["status"] == "ok"
    assert report["prefilter_dropped"] >= 4  # non-campaign phishing and benign names
    doc = jsonfeed.load(tmp_path / "feeds" / "latest.json")
    domains = {i.domain for i in doc.indicators}
    assert "rockstar-gta6-pc-download.test" in domains
    assert "bank-login.example" not in domains  # unrelated phishing is not our feed
    assert "gta6-photo-mode-fans.test" not in domains  # keyword-only, old domain
    assert all(i.tier >= Tier.LIKELY for i in doc.indicators)
    everything = jsonfeed.load(tmp_path / "feeds" / "all.json")
    assert any(i.tier is Tier.SUSPICIOUS for i in everything.indicators)
    stats = json.loads((tmp_path / "feeds" / "stats.json").read_text())
    assert stats["count"] == doc.count and stats["new_24h"] >= 1
    assert all(ok for _, ok, _ in verify_feed_dir(tmp_path / "feeds", None))
    badge = json.loads((tmp_path / "feeds" / "shields-active.json").read_text())
    assert badge["schemaVersion"] == 1 and badge["message"] == str(doc.count)


def test_scan_is_idempotent(tmp_path: Path) -> None:
    scan(tmp_path)
    first = (tmp_path / "feeds" / "latest.json").read_bytes()
    scan(tmp_path)
    assert (tmp_path / "feeds" / "latest.json").read_bytes() == first


def test_signed_feeds_verify_and_detect_tampering(tmp_path: Path) -> None:
    key = generate()
    scan(tmp_path, signer=key)
    pub = tmp_path / "k.pub"
    pub.write_text(key.public_file())
    results = verify_feed_dir(tmp_path / "feeds", pub, require_signature=True)
    assert all(ok for _, ok, _ in results), results
    assert any(name == "latest.json.minisig" for name, _, _ in results)
    hosts = tmp_path / "feeds" / "hosts.txt"
    hosts.write_text(hosts.read_text() + "0.0.0.0 injected.test\n")
    bad = {name: ok for name, ok, _ in verify_feed_dir(tmp_path / "feeds", pub, True)}
    assert not bad["hosts.txt.minisig"] and not bad["SHA256SUMS"] and not bad["hosts.txt"]


def test_retention_and_allowlist_removal(tmp_path: Path) -> None:
    state = State(tmp_path / "s.db")
    old = NOW - timedelta(days=40)
    sig = [Signal(id="keyword_intent_combo", weight=20, explanation="x"),
           Signal(id="claims_unreleased_platform", weight=30, explanation="x"),
           Signal(id="domain_age", weight=20, explanation="x", live=True, category="infrastructure")]  # fmt: skip
    state.upsert(domain="gta6-pc-download-old.test", url=None, seen=old, now=old, score=70,
                 tier=Tier.LIKELY, sources=["crtsh"], packs=["gta6"], signals=sig)  # fmt: skip
    state.upsert(domain="ign.com", url=None, seen=NOW, now=NOW, score=70, tier=Tier.LIKELY,
                 sources=["crtsh"], packs=["gta6"], signals=sig)  # fmt: skip
    state.close()
    cfg = ScanConfig(state_path=tmp_path / "s.db", out_dir=tmp_path / "f", fixtures=FIX, now=NOW)
    run_scan(cfg)
    st = State(tmp_path / "s.db")
    assert st.get("ign.com") is None  # allowlisted -> removed within one run
    old_ind = st.get("gta6-pc-download-old.test")
    assert old_ind is not None and old_ind.status == "stale"
    _stale, purged = st.apply_retention(NOW + timedelta(days=200))
    assert purged >= 1 and st.get("gta6-pc-download-old.test") is None
    st.close()


def test_cli_scan_feed_export(tmp_path: Path) -> None:
    out = tmp_path / "feeds"
    res = runner.invoke(
        app, ["scan", "--fixtures", "--out", str(out), "--state", str(tmp_path / "s.db")]
    )
    assert res.exit_code == 0, res.output
    assert "scan complete" in res.output
    assert runner.invoke(app, ["feed", "verify", str(out)]).exit_code == 0
    assert runner.invoke(app, ["feed", "verify", str(out), "--require-signature"]).exit_code == 1
    rebuilt = tmp_path / "rebuilt"
    assert (
        runner.invoke(
            app, ["feed", "build", "--out", str(rebuilt), "--state", str(tmp_path / "s.db")]
        ).exit_code
        == 0
    )
    diff = json.loads(
        runner.invoke(
            app, ["feed", "diff", str(out / "latest.json"), str(out / "latest.json"), "--json"]
        ).output
    )
    assert diff == {"added": [], "removed": [], "retiered": []}
    for fmt in ("hosts", "domains", "abp", "rpz", "json", "csv", "stix"):
        r = runner.invoke(
            app,
            [
                "export",
                "--format",
                fmt,
                "--input",
                str(out / "all.json"),
                "--min-tier",
                "suspicious",
            ],
        )
        assert r.exit_code == 0 and r.output, fmt
    assert (
        runner.invoke(
            app, ["export", "--format", "nope", "--input", str(out / "all.json")]
        ).exit_code
        == 1
    )
    assert (
        runner.invoke(app, ["feed", "build", "--state", str(tmp_path / "missing.db")]).exit_code
        == 1
    )
    report = json.loads(
        runner.invoke(
            app, ["scan", "--fixtures", "--json", "--state", str(tmp_path / "s2.db")]
        ).output
    )
    assert report["unique_domains"] > 0


def test_keygen_never_writes_secret(tmp_path: Path) -> None:
    pub = tmp_path / "keys" / "feed.pub"
    res = runner.invoke(app, ["feed", "keygen", "--out", str(pub)])
    assert res.exit_code == 0
    assert "minisign public key" in pub.read_text()
    assert list((tmp_path / "keys").iterdir()) == [pub]
    assert runner.invoke(app, ["feed", "keygen", "--out", str(pub)]).exit_code == 1


@pytest.mark.network
def test_live_doctor_runs() -> None:  # pragma: no cover - needs egress
    assert runner.invoke(app, ["doctor"]).exit_code == 0
