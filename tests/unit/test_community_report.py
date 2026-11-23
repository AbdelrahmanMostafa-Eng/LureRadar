from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]
BODY = """### Indicator (defanged URL or domain)

hxxps://gta6-pc-beta[.]test/claim

### Campaign pack

gta6

### Where did you see it?

Video comment

### What did it promise?

_No response_

### Before you submit

- [X] The link is defanged
"""


def run(body: str, tmp: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/community_report.py", "--issue", "7", "--out", str(tmp / "r"),
         "--summary", str(tmp / "s.md")],
        cwd=ROOT, env={"ISSUE_BODY": body, "PATH": ""}, capture_output=True, text=True, check=False,
    )  # fmt: skip


def test_valid_report_is_written(tmp_path: Path) -> None:
    res = run(BODY, tmp_path)
    assert res.returncode == 0, res.stderr
    (path,) = list((tmp_path / "r").glob("*.yaml"))
    data = yaml.safe_load(path.read_text())
    assert data["indicator"] == "hxxps://gta6-pc-beta[.]test/claim" and data["notes"] == ""
    assert "Offline LureRadar verdict" in (tmp_path / "s.md").read_text()


def test_undefanged_input_is_defanged_and_junk_rejected(tmp_path: Path) -> None:
    res = run(
        BODY.replace("hxxps://gta6-pc-beta[.]test/claim", "https://gta6-pc-beta.test/claim"),
        tmp_path,
    )
    assert res.returncode == 0
    bad = run(
        BODY.replace("hxxps://gta6-pc-beta[.]test/claim", "$(rm -rf /) not a url"), tmp_path / "b"
    )
    assert bad.returncode == 1 and "Could not accept" in (tmp_path / "b" / "s.md").read_text()
