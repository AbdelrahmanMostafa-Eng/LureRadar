"""``redirect_chain``: long or cross-domain redirect chains through shorteners
or affiliate/CPA hops."""

from __future__ import annotations

from lureradar.detectors.base import Context, shorteners
from lureradar.errors import LureRadarError
from lureradar.models import Signal
from lureradar.scoring import weights
from lureradar.util.defang import defang
from lureradar.util.domains import parse_target

MAX_BENIGN_HOPS = 2


def detect_redirect_chain(ctx: Context) -> list[Signal]:
    e = ctx.enrichment
    if e is None or e.http is None or not e.http.hops:
        return []
    hops = e.http.hops
    domains: list[str] = []
    for hop in [*hops, type(hops[0])(url=e.http.final_url, status=e.http.status)]:
        try:
            domains.append(parse_target(hop.url).registrable_domain)
        except LureRadarError:
            continue
    distinct = list(dict.fromkeys(domains))
    via_shortener = [d for d in distinct if d in shorteners()]
    cross = len(distinct) > 1
    if len(hops) > MAX_BENIGN_HOPS or (cross and via_shortener):
        reason = []
        if len(hops) > MAX_BENIGN_HOPS:
            reason.append(f"{len(hops)} redirects")
        if via_shortener:
            reason.append("via shortener " + ", ".join(defang(d) for d in via_shortener))
        return [
            Signal(
                id="redirect_chain",
                weight=weights.REDIRECT_CHAIN,
                category="infrastructure",
                live=True,
                explanation="Redirect chain: " + "; ".join(reason),
                evidence=tuple(defang(d) for d in distinct[:6]),
            )
        ]
    return []
