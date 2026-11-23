"""Turn a "Report a lure" issue into a validated data/reports/*.yaml file.

Used by .github/workflows/community-report.yml. The issue body is untrusted:
it is read from an environment variable, parsed as plain text, validated by
the Report model (must be defanged, must parse as a URL/domain), and re-emitted
by us. Nothing from the body is ever executed or interpolated into a shell.

    ISSUE_BODY="..." python scripts/community_report.py --issue 123 --out data/reports
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml

from lureradar.scoring.engine import Engine
from lureradar.sources.community_reports import Report
from lureradar.util.defang import defang
from lureradar.util.time import utcnow

FIELDS = {
    "Indicator (defanged URL or domain)": "indicator",
    "Campaign pack": "pack",
    "Where did you see it?": "where_seen",
    "What did it promise?": "notes",
}


def parse_issue_form(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    sections = re.split(r"^### +", body, flags=re.MULTILINE)
    for section in sections[1:]:
        title, _, value = section.partition("\n")
        key = FIELDS.get(title.strip())
        if key:
            value = value.strip()
            out[key] = "" if value == "_No response_" else value[:500]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", type=int, required=True)
    ap.add_argument("--out", type=Path, default=Path("data/reports"))
    ap.add_argument("--summary", type=Path, default=Path("report-summary.md"))
    args = ap.parse_args()
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    fields = parse_issue_form(os.environ.get("ISSUE_BODY", ""))
    fields["indicator"] = defang(fields.get("indicator", "").strip().strip("`"))
    try:
        report = Report.model_validate({**fields, "reported": utcnow().date().isoformat()})
    except ValueError as exc:
        args.summary.write_text(
            f"Could not accept this report: `{str(exc).splitlines()[0]}`\n", "utf-8"
        )
        print(json.dumps({"ok": False}))
        return 1
    verdict = Engine(pack_ids=[report.pack]).check(report.indicator)
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{report.reported.isoformat()}-issue{args.issue}.yaml"
    path.write_text(
        "# Community report, validated by scripts/community_report.py (CC0-1.0)\n"
        + yaml.safe_dump(report.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    signals = "\n".join(
        f"- `{s.id}` ({s.weight:+d}): {s.explanation}" for s in verdict.signals if s.weight
    )
    args.summary.write_text(
        f"Thanks! The report was validated and saved as `{path.as_posix()}`.\n\n"
        f"Offline LureRadar verdict for `{verdict.target}`: **{verdict.tier.value.upper()}** "
        f"(score {verdict.score}/100)\n\n{signals or '- no offline signals'}\n\n"
        "A maintainer will review the pull request. The pipeline then scores the indicator with "
        "live signals; it is only published if it reaches LIKELY or above.\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "path": path.as_posix(), "tier": verdict.tier.value}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
