"""Evidence timeline helpers (entries live in pc_watch.yaml; see config.py)."""

from __future__ import annotations

from lureradar.pcwatch.config import PcWatchConfig, TimelineEntry
from lureradar.pcwatch.status import Finding


def ordered(config: PcWatchConfig, include_reported: bool = False) -> list[TimelineEntry]:
    """Newest first. 'Reported / unconfirmed' items are off by default."""
    items = [e for e in config.timeline if include_reported or e.kind == "official"]
    return sorted(items, key=lambda e: (e.date, e.title), reverse=True)


def pending_entry_yaml(finding: Finding) -> str:
    """A ready-to-edit YAML stub a maintainer can paste after verifying a finding."""
    return (
        f"  - date: YYYY-MM-DD   # publication date on the official page\n"
        f"    source: {finding.source}\n"
        f'    title: "{finding.title}"\n'
        f"    url: {finding.url}\n"
        f'    paraphrase: "<your own words, <= 40 words>"\n'
        f'    meaning: "<what it means for PC players>"\n'
        f"    kind: official\n"
        f"    verified_on: YYYY-MM-DD\n"
        f'    verification: "maintainer reviewed the official page"\n'
    )
