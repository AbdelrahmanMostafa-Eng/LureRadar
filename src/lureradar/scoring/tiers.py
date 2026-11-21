"""Tier thresholds and the rules that can move a verdict across them.

CLEAR < 40 <= SUSPICIOUS < 70 <= LIKELY < 90 <= CONFIRMED.

Overrides (all documented in docs/SIGNALS.md):
* allowlisted outlet: always CLEAR (hard clear);
* corroborated external reputation: floor at CONFIRMED;
* local feed snapshot listing: floor at the listed tier;
* user-content platform: capped at SUSPICIOUS unless corroborated.
"""

from __future__ import annotations

from collections.abc import Iterable

from lureradar.models import Signal, Tier
from lureradar.scoring import weights

SUSPICIOUS_AT = 40
LIKELY_AT = 70
CONFIRMED_AT = 90

#: Categories that count as independent evidence of campaign relevance.
_INDEPENDENT = frozenset({"lexical", "platform", "brand", "content", "text"})


def clamp(value: int) -> int:
    return max(0, min(100, value))


def total(signals: Iterable[Signal]) -> int:
    return clamp(sum(s.weight for s in signals))


def tier_for_score(score: int) -> Tier:
    if score >= CONFIRMED_AT:
        return Tier.CONFIRMED
    if score >= LIKELY_AT:
        return Tier.LIKELY
    if score >= SUSPICIOUS_AT:
        return Tier.SUSPICIOUS
    return Tier.CLEAR


def external_sources(signals: Iterable[Signal]) -> set[str]:
    out: set[str] = set()
    for s in signals:
        if s.id == "external_reputation":
            out.update(e.split(":", 1)[0].strip() for e in s.evidence if e)
    return out


def is_corroborated(signals: list[Signal]) -> bool:
    """External hit backed by a second external source or strong own evidence."""
    sources = external_sources(signals)
    if not sources:
        return False
    if len(sources) >= 2:
        return True
    return any(
        s.weight >= weights.STRONG_SIGNAL and s.category in _INDEPENDENT
        for s in signals
        if s.id != "external_reputation"
    )


def decide(
    score: int,
    signals: list[Signal],
    *,
    outlet: bool = False,
    platform: bool = False,
    floor: Tier | None = None,
) -> tuple[Tier, bool]:
    """Return ``(tier, corroborated)`` for a scored target."""
    if outlet:
        return Tier.CLEAR, False
    tier = tier_for_score(score)
    corroborated = is_corroborated(signals)
    if corroborated:
        tier = Tier.CONFIRMED
    if floor is not None and floor > tier:
        tier = floor
    if platform and not corroborated and tier > Tier.SUSPICIOUS:
        tier = Tier.SUSPICIOUS
    return tier, corroborated
