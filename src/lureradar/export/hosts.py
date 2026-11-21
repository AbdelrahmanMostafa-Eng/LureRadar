"""hosts-file and plain domain-list exporters (Pi-hole accepts both)."""

from __future__ import annotations

from lureradar.export.common import header_lines, hosts_of, select
from lureradar.export.jsonfeed import FeedDocument
from lureradar.models import Tier

SINK = "0.0.0.0"  # noqa: S104 - hosts-file sink address, not a socket bind


def to_hosts(doc: FeedDocument, min_tier: Tier = Tier.LIKELY) -> str:
    hosts = hosts_of(select(doc, min_tier))
    lines = [f"# {h}" for h in header_lines(doc, "hosts", len(hosts), min_tier)]
    lines.append("#")
    lines += [f"{SINK} {h}" for h in hosts]
    return "\n".join(lines) + "\n"


def to_domains(doc: FeedDocument, min_tier: Tier = Tier.LIKELY) -> str:
    hosts = hosts_of(select(doc, min_tier))
    lines = [f"# {h}" for h in header_lines(doc, "domains", len(hosts), min_tier)]
    lines += hosts
    return "\n".join(lines) + "\n"


def parse_hosts(text: str) -> list[str]:
    """Parse a hosts file back into hostnames (used by tests and `feed verify`)."""
    out = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2 or parts[0] not in (SINK, "127.0.0.1", "::"):
            raise ValueError(f"invalid hosts line: {line!r}")
        out.append(parts[1])
    return out


def parse_domains(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
