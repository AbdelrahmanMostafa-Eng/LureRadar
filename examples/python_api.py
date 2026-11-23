"""Use LureRadar as a library (offline, no network).

uv run python examples/python_api.py
"""

from __future__ import annotations

from lureradar.models import Tier
from lureradar.scoring.engine import Engine

engine = Engine(pack_ids=["gta6"])  # load packs once, reuse for many checks

for target in (
    "https://rockstar-gta6-pc-download[.]test/free-key",
    "www.ign.com",
    "Free GTA 6 PC beta key, DM me on Telegram",
):
    verdict = engine.check(target)
    print(f"{verdict.tier.value:10} {verdict.score:3}  {verdict.target}")
    for signal in verdict.signals:
        if signal.weight:
            print(f"    {signal.weight:+3}  {signal.id}: {signal.explanation}")
    if verdict.tier >= Tier.LIKELY:
        print("    -> block it")

# Machine-readable, versioned output (docs/SCHEMA.md):
print(engine.check("gta6-pc-download.test").model_dump_json(indent=2)[:200], "...")
