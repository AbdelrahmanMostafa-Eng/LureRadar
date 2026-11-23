"""vercel.json must stay consistent with the services-mode rules and the repo layout."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
CONFIG = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
# Build/runtime keys are only valid inside a service in services mode.
SERVICE_ONLY = {"functions", "installCommand", "buildCommand", "devCommand", "ignoreCommand",
                "outputDirectory", "framework"}  # fmt: skip


def test_no_build_keys_at_top_level() -> None:
    assert not SERVICE_ONLY & set(CONFIG)


def test_rewrites_target_declared_services_and_catch_all_is_last() -> None:
    services = CONFIG["services"]
    rewrites = CONFIG["rewrites"]
    for rw in rewrites:
        assert rw["destination"]["service"] in services
    catch_all = [i for i, rw in enumerate(rewrites) if rw["source"] == "/(.*)"]
    assert catch_all == [len(rewrites) - 1]


def test_services_exist_and_bindings_are_well_formed() -> None:
    for name, svc in CONFIG["services"].items():
        root = ROOT / svc["root"]
        assert root.is_dir(), name
        for binding in svc.get("bindings", []):
            assert binding["type"] == "service" and binding["format"] == "url"
            assert binding["service"] in CONFIG["services"] and binding["env"]


def test_web_build_script_exists() -> None:
    web = CONFIG["services"]["web"]
    script = ROOT / web["root"] / web["buildCommand"].split()[-1]
    assert script.is_file()
    if os.name != "nt":
        assert os.access(script, os.X_OK)
    text = script.read_text(encoding="utf-8")
    assert "LURERADAR_BASE_URL" in text
    code = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    assert not any(re.search(r"(curl|wget)\b.*\|\s*(ba|z)?sh\b", ln) for ln in code)
