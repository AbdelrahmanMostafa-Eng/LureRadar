"""Write shields.io endpoint JSON badges from a stats.json (and optional bench
results) without running the pipeline. The pipeline writes the same badges;
this script exists for local previews and for repos that only publish stats.

    python scripts/gen_stats_badge.py build/feeds/stats.json --bench bench/results/latest.json --out build/badges
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lureradar.theme import AMBER, DANGER, INFO, RADAR


def badge(label: str, message: str, color: str) -> dict[str, object]:
    return {"schemaVersion": 1, "label": label, "message": message, "color": color.lstrip("#")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stats", type=Path)
    ap.add_argument("--bench", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=Path("build/badges"))
    args = ap.parse_args()
    stats = json.loads(args.stats.read_text(encoding="utf-8"))
    out = {
        "shields-detections-24h.json": badge(
            "detections (24h)", str(stats["new_24h"]), DANGER if stats["new_24h"] else RADAR
        ),
        "shields-active.json": badge("active indicators", str(stats["active_listed"]), AMBER),
        "shields-updated.json": badge(
            "feed updated", stats["generated_at"][:16].replace("T", " ") + " UTC", INFO
        ),
    }
    if args.bench and args.bench.is_file():
        fpr = json.loads(args.bench.read_text(encoding="utf-8"))["benign_fpr_likely"]
        out["shields-fpr.json"] = badge(
            "FPR on benign corpus", f"{fpr:.1%}", RADAR if fpr == 0 else AMBER
        )
    args.out.mkdir(parents=True, exist_ok=True)
    for name, data in out.items():
        (args.out / name).write_text(json.dumps(data) + "\n", encoding="utf-8")
        print(f"wrote {args.out / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
