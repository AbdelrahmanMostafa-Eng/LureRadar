"""DNS Response Policy Zone (RPZ) for BIND / Unbound / Knot / PowerDNS.

Each indicator gets ``name CNAME .`` (NXDOMAIN) for itself and its subdomains.
"""

from __future__ import annotations

import re

from lureradar.export.common import header_lines, hosts_of, select
from lureradar.export.jsonfeed import FeedDocument
from lureradar.models import Tier

ZONE = "rpz.lureradar.invalid."
_RECORD = re.compile(r"^(\*\.)?([a-z0-9.-]+)\s+CNAME\s+\.$")


def to_rpz(doc: FeedDocument, min_tier: Tier = Tier.LIKELY, zone: str = ZONE) -> str:
    hosts = hosts_of(select(doc, min_tier))
    serial = int(doc.generated_at.strftime("%Y%m%d%H"))
    lines = [f"; {h}" for h in header_lines(doc, "RPZ", len(hosts), min_tier)]
    lines += [
        f"$ORIGIN {zone}",
        "$TTL 3600",
        f"@ IN SOA localhost. hostmaster.localhost. ( {serial} 3600 600 604800 3600 )",
        "@ IN NS localhost.",
    ]
    for h in hosts:
        lines.append(f"{h} CNAME .")
        lines.append(f"*.{h} CNAME .")
    return "\n".join(lines) + "\n"


def parse_rpz(text: str) -> list[str]:
    """Return the protected names (without wildcard duplicates)."""
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line or line.startswith("$") or line.startswith("@"):
            continue
        m = _RECORD.match(line)
        if not m:
            raise ValueError(f"invalid RPZ record: {raw!r}")
        if not m.group(1):
            out.append(m.group(2))
    return out
