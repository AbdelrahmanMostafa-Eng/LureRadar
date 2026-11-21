"""CSV export for spreadsheets and SIEMs (leading ``#`` metadata lines)."""

from __future__ import annotations

import csv
import io

from lureradar.export.common import safe_host, select
from lureradar.export.jsonfeed import FeedDocument
from lureradar.models import Tier
from lureradar.util.defang import defang
from lureradar.util.time import isoformat

COLUMNS = [
    "domain", "url_defanged", "tier", "score", "first_seen", "last_seen",
    "signals", "sources", "packs", "dispute_url",
]  # fmt: skip


def to_csv(doc: FeedDocument, min_tier: Tier = Tier.LIKELY) -> str:
    rows = [i for i in select(doc, min_tier) if safe_host(i.domain)]
    buf = io.StringIO()
    buf.write(
        f"# generated_at={isoformat(doc.generated_at)}; schema_version={doc.schema_version}; "
        f"count={len(rows)}; license=CC0-1.0\n"
    )
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(COLUMNS)
    for i in rows:
        writer.writerow(
            [
                i.domain,
                defang(i.url) if i.url else "",
                i.tier.value,
                i.score,
                isoformat(i.first_seen),
                isoformat(i.last_seen),
                ";".join(f"{s.id}:{s.weight:+d}" for s in i.signals),
                ";".join(i.sources),
                ";".join(i.packs),
                i.dispute_url,
            ]
        )
    return buf.getvalue()


def parse_csv(text: str) -> list[dict[str, str]]:
    lines = [ln for ln in text.splitlines() if not ln.startswith("#")]
    return list(csv.DictReader(lines))
