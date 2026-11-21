"""STIX 2.1 bundle export (validated against the `stix2` library in tests).

IDs are deterministic (UUIDv5) so unchanged indicators keep their ids.
"""

from __future__ import annotations

import uuid
from typing import Any

import orjson

from lureradar import __version__
from lureradar.config import REPO_URL, base_url
from lureradar.export.common import safe_host, select
from lureradar.export.jsonfeed import FeedDocument
from lureradar.models import Tier
from lureradar.util.time import isoformat

NAMESPACE = uuid.UUID("6f0b1c9e-6c55-4d0e-9a52-6c7572656172")
IDENTITY_ID = f"identity--{uuid.uuid5(NAMESPACE, 'lureradar')}"
CONFIDENCE = {Tier.SUSPICIOUS: 40, Tier.LIKELY: 75, Tier.CONFIRMED: 95, Tier.CLEAR: 0}
EPOCH = "2026-11-21T00:00:00.000Z"


def _ts(value: Any) -> str:
    return isoformat(value).replace("Z", ".000Z")


def to_stix(doc: FeedDocument, min_tier: Tier = Tier.LIKELY) -> str:
    created = _ts(doc.generated_at)
    identity = {
        "type": "identity",
        "spec_version": "2.1",
        "id": IDENTITY_ID,
        "created": EPOCH,
        "modified": EPOCH,
        "name": "LureRadar",
        "identity_class": "system",
        "description": f"Open threat radar for hyped-launch scams. {base_url()}",
    }
    objects: list[dict[str, Any]] = [identity]
    indicators = [i for i in select(doc, min_tier) if safe_host(i.domain)]
    for ind in indicators:
        reasons = "; ".join(f"{s.id} ({s.weight:+d})" for s in ind.signals[:6])
        objects.append(
            {
                "type": "indicator",
                "spec_version": "2.1",
                "id": f"indicator--{uuid.uuid5(NAMESPACE, ind.domain)}",
                "created_by_ref": IDENTITY_ID,
                "created": _ts(ind.first_seen),
                "modified": created,
                "name": f"Launch-lure domain ({ind.tier.value})",
                "description": f"LureRadar score {ind.score}/100. Signals: {reasons}. "
                f"Dispute: {ind.dispute_url}",
                "indicator_types": ["malicious-activity"],
                "pattern": f"[domain-name:value = '{ind.domain}']",
                "pattern_type": "stix",
                "valid_from": _ts(ind.first_seen),
                "confidence": CONFIDENCE[ind.tier],
                "labels": [f"lureradar-tier-{ind.tier.value}", *[f"pack-{p}" for p in ind.packs]],
                "external_references": [{"source_name": "LureRadar", "url": REPO_URL}],
            }
        )
    objects.append(
        {
            "type": "note",
            "spec_version": "2.1",
            "id": f"note--{uuid.uuid5(NAMESPACE, 'meta-' + created)}",
            "created_by_ref": IDENTITY_ID,
            "created": created,
            "modified": created,
            "abstract": "LureRadar feed metadata",
            "content": (
                f"generated_at={isoformat(doc.generated_at)}; schema_version={doc.schema_version}; "
                f"count={len(indicators)}; generator=LureRadar/{__version__}; license=CC0-1.0"
            ),
            "object_refs": [IDENTITY_ID],
        }
    )
    bundle = {
        "type": "bundle",
        "id": f"bundle--{uuid.uuid5(NAMESPACE, 'bundle-' + created)}",
        "objects": objects,
    }
    return orjson.dumps(bundle, option=orjson.OPT_INDENT_2).decode() + "\n"
