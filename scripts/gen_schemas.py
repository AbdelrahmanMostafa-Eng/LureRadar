"""Regenerate src/lureradar/schemas/*.schema.json from the pydantic models."""

from __future__ import annotations

import sys
from pathlib import Path

from lureradar.schemas import SCHEMA_FILES, generate, render

OUT = Path(__file__).resolve().parents[1] / "src" / "lureradar" / "schemas"


def main() -> int:
    for name, schema in generate().items():
        path = OUT / SCHEMA_FILES[name]
        path.write_text(render(schema), encoding="utf-8")
        print(f"wrote {path.relative_to(OUT.parents[2])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
