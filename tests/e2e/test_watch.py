from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from lureradar.cli import app
from lureradar.pipeline.state import State

REPLAY = Path(__file__).parents[1] / "fixtures" / "sources" / "certstream-replay.jsonl"


def test_watch_replay_alerts_and_publishes(tmp_path: Path) -> None:
    runner = CliRunner()
    res = runner.invoke(
        app,
        ["watch", "--replay", str(REPLAY), "--state", str(tmp_path / "w.db"),
         "--feeds-out", str(tmp_path / "feeds"), "--alert-tier", "suspicious"],
    )  # fmt: skip
    assert res.exit_code == 0, res.output
    alerts = [json.loads(line) for line in res.stdout.splitlines() if line.startswith("{")]
    hosts = {a["indicator"] for a in alerts}
    assert "rockstar-gta6-pc-download[.]test" in hosts
    assert "gtavi-android-apk-download[.]test" in hosts
    assert not any("example" in h for h in hosts)
    st = State(tmp_path / "w.db")
    assert st.get("rockstar-gta6-pc-download.test") is not None
    st.close()
    assert (tmp_path / "feeds" / "latest.json").is_file()


def test_watch_bad_tier() -> None:
    assert CliRunner().invoke(app, ["watch", "--alert-tier", "nope"]).exit_code == 1
