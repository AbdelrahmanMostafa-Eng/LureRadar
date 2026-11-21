"""Helpers shared by the exporters: selection, metadata header, safe names."""

from __future__ import annotations

import re
from collections.abc import Iterable

from lureradar import __version__
from lureradar.config import REPO_URL, base_url
from lureradar.export.jsonfeed import FeedDocument
from lureradar.models import Indicator, Tier
from lureradar.util.time import isoformat

# Strict hostname check: anything else is dropped so a malformed indicator can
# never inject syntax into a hosts file, filter list or zone file.
_HOST_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9-]{2,63}$")


def safe_host(domain: str) -> str | None:
    host = domain.strip().lower().rstrip(".")
    if not _HOST_RE.match(host) or host.replace(".", "").isdigit():
        return None
    return host


def select(doc: FeedDocument, min_tier: Tier = Tier.LIKELY) -> list[Indicator]:
    """Active indicators at or above ``min_tier``, sorted for stable diffs."""
    chosen = [i for i in doc.indicators if i.status == "active" and i.tier >= min_tier]
    return sorted(chosen, key=lambda i: i.domain)


def hosts_of(indicators: Iterable[Indicator]) -> list[str]:
    out = []
    for ind in indicators:
        host = safe_host(ind.domain)
        if host:
            out.append(host)
    return sorted(dict.fromkeys(out))


def header_lines(doc: FeedDocument, title: str, count: int, min_tier: Tier) -> list[str]:
    return [
        f"Title: LureRadar {title}",
        f"Description: hyped-launch lure domains (tier >= {min_tier.value.upper()})",
        f"Homepage: {base_url()}",
        f"Generated: {isoformat(doc.generated_at)}",
        f"generated_at: {isoformat(doc.generated_at)}",
        f"schema_version: {doc.schema_version}",
        f"count: {count}",
        "License: CC0-1.0 (data), see DATA_LICENSE",
        f"Generator: LureRadar/{__version__}",
        "Expires: 1 day",
        "Detections are automated and may contain false positives. No warranty.",
        f"Dispute a listing: {REPO_URL}/issues/new?template=false-positive-review.yml",
    ]
