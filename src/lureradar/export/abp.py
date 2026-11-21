"""AdGuard / uBlock Origin filter list (Adblock Plus syntax: ``||domain^``)."""

from __future__ import annotations

import re

from lureradar.export.common import header_lines, hosts_of, select
from lureradar.export.jsonfeed import FeedDocument
from lureradar.models import Tier

_RULE = re.compile(r"^\|\|([a-z0-9.-]+)\^$")


def to_abp(doc: FeedDocument, min_tier: Tier = Tier.LIKELY) -> str:
    hosts = hosts_of(select(doc, min_tier))
    lines = ["[Adblock Plus 2.0]"]
    lines += [
        f"! {h}"
        for h in header_lines(doc, "lure filter (AdGuard / uBlock Origin)", len(hosts), min_tier)
    ]
    lines += [f"||{h}^" for h in hosts]
    return "\n".join(lines) + "\n"


def parse_abp(text: str) -> list[str]:
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("!", "[")):
            continue
        m = _RULE.match(line)
        if not m:
            raise ValueError(f"invalid filter rule: {line!r}")
        out.append(m.group(1))
    return out
