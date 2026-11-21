from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from lureradar.errors import FeedError
from lureradar.export.jsonfeed import FeedDocument, dumps, load, loads, write
from lureradar.models import Indicator, Tier

NOW = datetime(2026, 11, 21, 12, tzinfo=UTC)


def _doc() -> FeedDocument:
    ind = Indicator(domain="a.test", tier=Tier.LIKELY, score=75, first_seen=NOW, last_seen=NOW)
    return FeedDocument(generated_at=NOW, indicators=[ind])


def test_feed_document_roundtrip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    doc = _doc()
    assert doc.count == 1
    again = loads(dumps(doc))
    assert again.indicators[0].domain == "a.test" and again.schema_version == "1.0"
    path = write(doc, tmp_path / "x" / "latest.json")
    assert load(path).count == 1


def test_feed_document_errors(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(FeedError, match="invalid"):
        loads(b"{not json")
    data = json.loads(dumps(_doc()))
    data["count"] = 5
    with pytest.raises(FeedError, match="count"):
        loads(json.dumps(data))
    with pytest.raises(FeedError, match="not found"):
        load(tmp_path / "missing.json")
