"""``hosting_reputation``: hosted on an ASN from a *sourced* reputation list.

The list (src/lureradar/data/hosting_reputation.yaml) ships empty in v0.1.0:
every entry must cite a public source and date, and we could not verify one.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

import yaml

from lureradar.detectors.base import Context
from lureradar.models import Signal
from lureradar.scoring import weights


@lru_cache(maxsize=1)
def reputation_list() -> dict[int, dict[str, str]]:
    text = resources.files("lureradar.data").joinpath("hosting_reputation.yaml").read_text("utf-8")
    data = yaml.safe_load(text) or {}
    out: dict[int, dict[str, str]] = {}
    for entry in data.get("entries") or []:
        if not entry.get("source") or not entry.get("as_of"):
            continue  # unsourced entries are ignored by design
        out[int(entry["asn"])] = {k: str(v) for k, v in entry.items()}
    return out


def detect_hosting_reputation(ctx: Context) -> list[Signal]:
    e = ctx.enrichment
    if e is None or e.asn is None or ctx.allow.outlet or ctx.allow.platform:
        return []
    entry = reputation_list().get(e.asn)
    if not entry:
        return []
    return [
        Signal(
            id="hosting_reputation",
            weight=weights.HOSTING_REPUTATION,
            category="infrastructure",
            live=True,
            explanation=(
                f"Hosted on AS{e.asn} ({entry.get('name', '?')}): {entry.get('reason', '')}"
            ),
            evidence=(f"AS{e.asn}", entry.get("source", "")),
        )
    ]
