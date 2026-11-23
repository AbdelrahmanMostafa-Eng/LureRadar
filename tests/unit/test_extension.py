"""The extension's generated config and manifest must match the Python config."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from lureradar import __version__

ROOT = Path(__file__).parents[2]


def test_extension_is_in_sync() -> None:
    res = subprocess.run(
        [sys.executable, "scripts/sync_extension.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stdout


def test_manifest_is_minimal_and_local_only() -> None:
    manifest = json.loads((ROOT / "extension" / "manifest.json").read_text())
    assert manifest["manifest_version"] == 3 and manifest["version"] == __version__
    assert set(manifest["permissions"]) == {"storage", "alarms", "webNavigation"}
    assert len(manifest["host_permissions"]) == 1
    for size in ("16", "32", "48", "128"):
        assert (ROOT / "extension" / manifest["icons"][size]).is_file()
    background = (ROOT / "extension" / "src" / "background.js").read_text()
    assert background.count("fetch(") == 1  # the feed download is the only request
