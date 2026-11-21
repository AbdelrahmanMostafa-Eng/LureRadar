"""Normalise and merge candidates by registrable domain."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from lureradar.errors import InvalidTargetError
from lureradar.models import Candidate, TargetKind
from lureradar.util.domains import parse_target


@dataclass
class Merged:
    """All sightings of one registrable domain in this run."""

    domain: str
    url: str | None
    first_seen: datetime
    sources: set[str] = field(default_factory=set)
    reputation_sources: set[str] = field(default_factory=set)
    hosts: set[str] = field(default_factory=set)


def merge(
    candidates: Iterable[Candidate], now: datetime | None = None
) -> tuple[dict[str, Merged], int]:
    """Return ``({registrable: Merged}, invalid_count)``.

    ``now`` clamps sighting times: feeds without timestamps (OpenPhish) are
    stamped by the adapter's clock, and a pinned run clock keeps runs reproducible.
    """
    out: dict[str, Merged] = {}
    invalid = 0
    for cand in candidates:
        try:
            target = parse_target(cand.url or cand.domain)
        except InvalidTargetError:
            invalid += 1
            continue
        if target.kind is TargetKind.TEXT or not target.registrable_domain:
            invalid += 1
            continue
        key = target.registrable_domain
        url = target.url if target.kind is TargetKind.URL else None
        seen = min(cand.first_seen, now) if now is not None else cand.first_seen
        m = out.get(key)
        if m is None:
            m = out[key] = Merged(domain=key, url=url, first_seen=seen)
        m.first_seen = min(m.first_seen, seen)
        m.url = m.url or url
        m.sources.add(cand.source)
        m.hosts.add(target.host)
        if cand.reputation_hit:
            m.reputation_sources.add(cand.source)
    return out, invalid
