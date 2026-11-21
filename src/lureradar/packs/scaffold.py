"""``lureradar pack new``: scaffold a minimal, valid campaign pack."""

from __future__ import annotations

import re
from pathlib import Path

from lureradar.errors import PackError
from lureradar.util.time import utcnow

_TEMPLATE = """\
# {name}: campaign pack (see docs/PACKS.md)
id: {pack_id}
name: "{name}"
version: 1
as_of: {today}
description: "Lures around the {name} launch."
keywords: [{pack_id}, "{spaced}"]
intents: [download, free, key, keygen, crack, apk, pc, beta, early-access, generator, leak]
brands:
  - {{name: examplestore, official: [example.com]}}
allowlist:
  outlets: [example.org]
  platforms: []
facts:
  as_of: {today}
  facts:
    - id: pc_release
      claim: "Replace with a dated, sourced claim, e.g. 'No PC version announced'."
      status: not_announced
      as_of: {today}
      sources: [{{url: "https://example.com/source", title: "Source title", accessed: {today}}}]
  platforms:
    pc: {{status: unreleased, fact: pc_release, terms: [pc, windows, steam]}}
"""

_README = """\
# {name} pack

Campaign pack for lures around **{name}**. Edit `pack.yaml`, then run:

```bash
lureradar pack validate packs/{pack_id}
lureradar check "{pack_id}-free-download.test" --pack {pack_id}
```

Every fact must have a date and at least one source. See `docs/PACKS.md`.
"""


def new_pack(pack_id: str, root: Path, name: str | None = None) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,40}", pack_id):
        raise PackError("pack id must be 2-41 chars: lowercase letters, digits, hyphens")
    if len(re.sub(r"[^a-z0-9]", "", pack_id)) < 4:
        raise PackError("pack id must contain at least 4 letters/digits (it is used as a keyword)")
    target = root / pack_id
    if target.exists():
        raise PackError(f"{target} already exists")
    target.mkdir(parents=True)
    display = name or pack_id.replace("-", " ").title()
    spaced = pack_id.replace("-", " ")
    if spaced == pack_id:
        spaced = re.sub(r"(?<=[a-z])(?=\d)", " ", pack_id)
    if spaced == pack_id:
        spaced = f"{pack_id} game"
    today = utcnow().date().isoformat()
    (target / "pack.yaml").write_text(
        _TEMPLATE.format(pack_id=pack_id, name=display, today=today, spaced=spaced),
        encoding="utf-8",
    )
    (target / "README.md").write_text(_README.format(pack_id=pack_id, name=display), "utf-8")
    return target
