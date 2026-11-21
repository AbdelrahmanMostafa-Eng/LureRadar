"""Reputation signals.

``external_reputation`` (+40): the indicator is flagged by an external source
(Safe Browsing, URLhaus, OpenPhish, urlscan). Corroborated hits floor the tier
at CONFIRMED (see scoring/tiers.py).

``feed_listed`` (informational): the indicator is already in the local feed
snapshot (``lureradar feed pull``); the verdict is floored at that tier.
"""

from __future__ import annotations

from lureradar.detectors.base import Context
from lureradar.models import Signal
from lureradar.scoring import weights
from lureradar.util.defang import defang


def detect_external_reputation(ctx: Context) -> list[Signal]:
    e = ctx.enrichment
    if e is None or not e.reputation:
        return []
    sources = sorted({h.source for h in e.reputation})
    return [
        Signal(
            id="external_reputation",
            weight=weights.EXTERNAL_REPUTATION,
            category="reputation",
            live=True,
            explanation=f"Flagged by {len(sources)} external source(s): {', '.join(sources)}",
            evidence=tuple(f"{h.source}: {h.detail}"[:100] for h in e.reputation[:4]),
        )
    ]


def detect_feed_listed(ctx: Context) -> list[Signal]:
    snap = ctx.snapshot
    if snap is None or ctx.allow.outlet:
        return []
    entry = snap.lookup(ctx.target.host) or snap.lookup(ctx.target.registrable_domain)
    if entry is None:
        return []
    return [
        Signal(
            id="feed_listed",
            weight=0,
            category="reputation",
            explanation=(
                f"Listed in the local LureRadar feed snapshot as {entry.tier.value.upper()} "
                f"(score {entry.score}, last seen {entry.last_seen.date().isoformat()})"
            ),
            evidence=(defang(entry.domain), f"snapshot {snap.generated_at.date().isoformat()}"),
        )
    ]
