"""JSON Schemas generated from the pydantic models (see scripts/gen_schemas.py).

The committed ``*.schema.json`` files are the public contract; a test fails if
they drift from the models.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

from lureradar.config import DEFAULT_BASE_URL, FEED_SCHEMA_VERSION, VERDICT_SCHEMA_VERSION

SCHEMA_FILES = {
    "verdict": "verdict.schema.json",
    "feed": "feed.schema.json",
    "pack": "pack.schema.json",
}


def generate() -> dict[str, dict[str, Any]]:
    from lureradar.export.jsonfeed import FeedDocument
    from lureradar.models import Verdict
    from lureradar.packs.schema import Pack

    out: dict[str, dict[str, Any]] = {}
    for name, model, version in (
        ("verdict", Verdict, VERDICT_SCHEMA_VERSION),
        ("feed", FeedDocument, FEED_SCHEMA_VERSION),
        ("pack", Pack, "1"),
    ):
        schema = model.model_json_schema(mode="serialization")
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        # Always the canonical default (not the env override) so output is stable.
        schema["$id"] = f"{DEFAULT_BASE_URL}schemas/{name}-{version}.schema.json"
        schema["x-schema-version"] = version
        out[name] = schema
    return out


def load(name: str) -> dict[str, Any]:
    text = resources.files("lureradar.schemas").joinpath(SCHEMA_FILES[name]).read_text("utf-8")
    data: dict[str, Any] = json.loads(text)
    return data


def render(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
