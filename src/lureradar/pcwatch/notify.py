"""Human-in-the-loop notifications: issue text for maintainers and webhook
payloads for subscribers. Nothing here changes the published status."""

from __future__ import annotations

from typing import Any

from lureradar.config import site_url
from lureradar.pcwatch.status import CheckResult, PcWatchState, honest_sentence
from lureradar.pcwatch.timeline import pending_entry_yaml

ISSUE_TITLE = "PC Watch: possible PC announcement detected (maintainer review needed)"


def issue_body(state: PcWatchState, check: CheckResult) -> str:
    suggested = state.suggested_status.value if state.suggested_status else "?"
    lines = [
        "Automated PC Watch found official-source evidence that may indicate a status change.",
        "",
        f"- Published status (facts.yaml `{state.fact_id}`): **{state.confirmed_status.value}**",
        f"- Suggested by automation: **{suggested}**",
        f"- Checked at: {state.last_checked}",
        "",
        "## Evidence (official sources only)",
        "",
    ]
    for src in check.sources:
        for f in src.findings:
            flag = " (negated wording, likely not an announcement)" if f.negated else ""
            lines.append(f'- **{src.name}**: [{f.title}]({f.url}) - "{f.snippet}"{flag}')
    lines += [
        "",
        "## What a maintainer must do",
        "",
        "1. Open each link and confirm it is genuinely official and says what the snippet",
        "   suggests.",
        "2. If confirmed: in `packs/gta6/facts.yaml`, set the `pc_release` fact `status` to",
        "   `announced_undated`, `announced_dated` (put the date in `value`) or `released`,",
        "   update `as_of` and add the official source.",
        "3. Add a timeline entry to `packs/gta6/pc_watch.yaml` (stub below), then open a PR.",
        "4. Merging that PR switches off `claims_unreleased_platform` for PC and allowlists",
        "   the official PC storefronts on the next pipeline run.",
        "",
        "If the evidence is wrong (parser bug, fake page, rumour), close this issue.",
        "",
        "```yaml",
    ]
    for src in check.sources:
        for f in src.findings:
            lines.append(pending_entry_yaml(f).rstrip())
    lines += ["```", "", "---", "_Opened automatically by the `pc-watch` workflow._"]
    return "\n".join(lines) + "\n"


def webhook_payload(state: PcWatchState, kind: str = "discord") -> dict[str, Any]:
    text = f"{honest_sentence(state)} {site_url('pc-watch/')}"
    if kind == "slack":
        return {"text": text}
    return {"content": text, "allowed_mentions": {"parse": []}}
