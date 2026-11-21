"""Domain age and certificate freshness (``--live`` only).

Signals: ``domain_age`` (+20/+15/+8 for <3/<14/<30 days since RDAP
registration), ``fresh_cert`` (first CT sighting or cert notBefore < 48h) and
``established_domain`` (-15 for >1 year old with no strong signal).
"""

from __future__ import annotations

from datetime import timedelta

from lureradar.detectors.base import Context
from lureradar.models import Signal
from lureradar.scoring import weights
from lureradar.util.time import isoformat


def detect_domain_age(ctx: Context) -> list[Signal]:
    e = ctx.enrichment
    if e is None or e.rdap is None or e.rdap.registered is None or ctx.allow.platform:
        return []
    age = ctx.now - e.rdap.registered
    for days, weight in (
        (3, weights.DOMAIN_AGE_3D),
        (14, weights.DOMAIN_AGE_14D),
        (30, weights.DOMAIN_AGE_30D),
    ):
        if age < timedelta(days=days):
            return [
                Signal(
                    id="domain_age",
                    weight=weight,
                    category="infrastructure",
                    live=True,
                    explanation=(
                        f"Registered {max(age.days, 0)} day(s) ago (< {days} days, RDAP "
                        f"registration {isoformat(e.rdap.registered)})"
                    ),
                    evidence=(isoformat(e.rdap.registered),),
                )
            ]
    return []


def detect_fresh_cert(ctx: Context) -> list[Signal]:
    e = ctx.enrichment
    if e is None or ctx.allow.platform:
        return []
    seen = e.first_ct_seen or (e.tls.not_before if e.tls else None)
    if seen is None:
        return []
    if ctx.now - seen < timedelta(hours=48):
        return [
            Signal(
                id="fresh_cert",
                weight=weights.FRESH_CERT,
                category="infrastructure",
                live=True,
                explanation=f"TLS certificate first seen {isoformat(seen)} (< 48 hours ago)",
                evidence=(isoformat(seen),),
            )
        ]
    return []


def detect_established_domain(ctx: Context, signals: list[Signal]) -> list[Signal]:
    """Runs after the other detectors: needs to know whether any strong signal fired."""
    e = ctx.enrichment
    if e is None or e.rdap is None or e.rdap.registered is None:
        return []
    if ctx.allow.outlet or ctx.allow.platform:
        return []
    if any(s.weight >= weights.STRONG_SIGNAL for s in signals):
        return []
    age = ctx.now - e.rdap.registered
    if age > timedelta(days=365):
        return [
            Signal(
                id="established_domain",
                weight=weights.ESTABLISHED_DOMAIN,
                category="trust",
                live=True,
                explanation=f"Registered {age.days // 365} year(s) ago with no strong lure signal",
                evidence=(isoformat(e.rdap.registered),),
            )
        ]
    return []
