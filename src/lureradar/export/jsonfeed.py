"""The canonical JSON feed document (``/feeds/latest.json``).

Every other format is derived from this document.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import orjson
from pydantic import BaseModel, Field, ValidationError, model_validator

from lureradar import __version__
from lureradar.config import FEED_SCHEMA_VERSION, base_url
from lureradar.errors import FeedError
from lureradar.models import Indicator, Tier


class FeedDocument(BaseModel):
    schema_version: str = FEED_SCHEMA_VERSION
    generated_at: datetime
    generator: str = Field(default_factory=lambda: f"LureRadar/{__version__}")
    base_url: str = Field(default_factory=base_url)
    license: str = "CC0-1.0"
    min_tier: Tier = Tier.LIKELY
    count: int = 0
    notice: str = (
        "Detections are automated and may contain false positives. Dispute any entry via "
        "its dispute_url. No warranty."
    )
    indicators: list[Indicator] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _default_count(cls, data: Any) -> Any:
        if isinstance(data, dict) and "count" not in data:
            data = {**data, "count": len(data.get("indicators") or [])}
        return data


def dumps(doc: FeedDocument) -> bytes:
    doc.count = len(doc.indicators)
    return (
        orjson.dumps(doc.model_dump(mode="json"), option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS)
        + b"\n"
    )


def loads(data: bytes | str) -> FeedDocument:
    try:
        doc = FeedDocument.model_validate(orjson.loads(data))
    except (orjson.JSONDecodeError, ValidationError) as exc:
        raise FeedError(f"invalid feed document: {exc}") from exc
    if doc.count != len(doc.indicators):
        raise FeedError(f"count {doc.count} != {len(doc.indicators)} indicators")
    return doc


def load(path: Path) -> FeedDocument:
    try:
        return loads(path.read_bytes())
    except FileNotFoundError as exc:
        raise FeedError(f"{path}: not found") from exc


def write(doc: FeedDocument, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(dumps(doc))
    return path
