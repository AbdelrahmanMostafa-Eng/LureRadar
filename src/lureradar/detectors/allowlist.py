"""Allowlist and user-content platform handling.

Signals: ``allowlisted`` (hard clear for established outlets) and
``user_content_platform`` (informational, weight 0: the platform domain is
never blocklisted, but the URL on it is still assessed and capped at
SUSPICIOUS).
"""

from __future__ import annotations

from lureradar.detectors.base import Context
from lureradar.models import Signal
from lureradar.scoring import weights
from lureradar.util.defang import defang


def detect_allowlist(ctx: Context) -> list[Signal]:
    allow = ctx.allow
    if allow.outlet:
        return [
            Signal(
                id="allowlisted",
                weight=weights.ALLOWLISTED,
                category="trust",
                explanation=f"{defang(allow.matched)} is allowlisted ({allow.reason}): hard clear",
                evidence=(defang(allow.matched),),
            )
        ]
    if allow.platform:
        return [
            Signal(
                id="user_content_platform",
                weight=0,
                category="trust",
                explanation=(
                    f"{defang(allow.matched)} is a {allow.reason}: the domain itself is never "
                    "blocklisted; only this specific URL is assessed (capped at SUSPICIOUS)"
                ),
                evidence=(defang(allow.matched),),
            )
        ]
    return []
