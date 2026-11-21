"""``abused_tld``: the TLD is on a documented abuse-prone list (never decisive)."""

from __future__ import annotations

from lureradar.detectors.base import Context, abused_tlds
from lureradar.models import Signal
from lureradar.scoring import weights


def detect_abused_tld(ctx: Context) -> list[Signal]:
    t = ctx.target
    if ctx.allow.outlet or ctx.allow.platform or t.is_ip or not t.suffix:
        return []
    tld = t.suffix.rsplit(".", 1)[-1]
    if t.is_private_suffix:
        # foo.example-host.xyz: the user did not choose the TLD
        return []
    if tld in abused_tlds():
        return [
            Signal(
                id="abused_tld",
                weight=weights.ABUSED_TLD,
                category="infrastructure",
                explanation=(
                    f".{tld} appears on public most-abused-TLD rankings "
                    "(src/lureradar/data/abused_tlds.yaml)"
                ),
                evidence=(f".{tld}",),
            )
        ]
    return []
