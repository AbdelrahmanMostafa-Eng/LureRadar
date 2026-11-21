"""The committed JSON Schemas are the public contract: they must match the models."""

from __future__ import annotations

from lureradar.schemas import SCHEMA_FILES, generate, load, render


def test_committed_schemas_match_models() -> None:
    generated = generate()
    for name in SCHEMA_FILES:
        assert render(load(name)) == render(generated[name]), (
            f"{name} schema drifted: run `make schemas`"
        )


def test_schema_ids_are_versioned() -> None:
    for name in SCHEMA_FILES:
        schema = load(name)
        assert schema["$id"].endswith(f"{name}-{schema['x-schema-version']}.schema.json")
