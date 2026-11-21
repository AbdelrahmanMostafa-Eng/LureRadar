"""Rich rendering of verdict cards for the terminal."""

from __future__ import annotations

import re

from rich import box
from rich.console import Console, Group, RenderableType
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from lureradar import __version__, theme
from lureradar.models import Signal, TargetKind, Tier, Verdict
from lureradar.scoring.explain import SIGNAL_DOCS, TIER_LABELS, headline
from lureradar.scoring.tiers import CONFIRMED_AT, LIKELY_AT, SUSPICIOUS_AT

_URL_IN_STEP = re.compile(r"(https://\S+)")
BAR_WIDTH = 30


def tier_badge(tier: Tier) -> Text:
    color = theme.TIER_COLORS[tier]
    label = f" {TIER_LABELS[tier]} "
    return Text(label, style=f"bold {theme.BG} on {color}")


def score_bar(score: int, tier: Tier, width: int = BAR_WIDTH) -> Text:
    filled = round(score / 100 * width)
    marks = {round(t / 100 * width) for t in (SUSPICIOUS_AT, LIKELY_AT, CONFIRMED_AT)}
    bar = Text()
    color = theme.TIER_COLORS[tier]
    for i in range(width):
        if i < filled:
            bar.append("█", style=color)
        elif i in marks:
            bar.append("┊", style=theme.MUTED)
        else:
            bar.append("░", style=theme.BORDER)
    return bar


def _weight(signal: Signal) -> Text:
    if signal.weight > 0:
        return Text(
            f"+{signal.weight}",
            style=f"bold {theme.DANGER if signal.weight >= 20 else theme.AMBER}",
        )
    if signal.weight < 0:
        return Text(str(signal.weight), style=f"bold {theme.RADAR}")
    return Text(" 0", style=theme.MUTED)


def _step(text: str) -> Text:
    out = Text()
    pos = 0
    for m in _URL_IN_STEP.finditer(text):
        out.append(text[pos : m.start()])
        url = m.group(1)
        label = "issue form ↗" if "/issues/new" in url else url
        out.append(label, style=f"underline {theme.INFO} link {url}")
        pos = m.end()
    out.append(text[pos:])
    return out


def signals_table(signals: list[Signal], explain: bool = False, limit: int = 6) -> Table:
    table = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    table.add_column("w", justify="right", width=4, no_wrap=True)
    table.add_column("id", style=theme.INFO, no_wrap=True)
    table.add_column("why", style=theme.TEXT, ratio=1)
    for s in signals[:limit]:
        why = Text(s.explanation)
        if s.live:
            why.append(" (live)", style=theme.MUTED)
        if explain:
            doc = SIGNAL_DOCS.get(s.id)
            if doc:
                why.append(f"\n{doc.description}", style=theme.MUTED)
            for ev in s.evidence[:3]:
                why.append(f"\n  evidence: {ev}", style=theme.MUTED)
        table.add_row(_weight(s), s.id, why)
    if len(signals) > limit:
        table.add_row(
            "", "", Text(f"+{len(signals) - limit} more (use --explain)", style=theme.MUTED)
        )
    return table


def verdict_card(v: Verdict, explain: bool = False, compact: bool = False) -> RenderableType:
    color = theme.TIER_COLORS[v.tier]
    top = Text.assemble(
        tier_badge(v.tier),
        "  ",
        (f"{v.score:>3}", f"bold {color}"),
        ("/100  ", theme.MUTED),
        score_bar(v.score, v.tier),
    )
    target = Text(v.target, style=f"bold {theme.TEXT}")
    head = Text(headline(v), style=color if v.tier is not Tier.CLEAR else theme.MUTED)
    parts: list[RenderableType] = [top, Text(""), target, head]

    shown = [
        s for s in v.signals if s.weight != 0 or s.id in ("user_content_platform", "feed_listed")
    ]
    if shown:
        parts += [Text(""), Text("WHY", style=f"bold {theme.MUTED}"), signals_table(shown, explain)]
    if v.kind is TargetKind.TEXT and v.urls:
        parts += [Text(""), Text("LINKS IN THE MESSAGE", style=f"bold {theme.MUTED}")]
        for u in v.urls[:5]:
            line = Text.assemble(
                tier_badge(u.tier),
                " ",
                (f"{u.score:>3} ", theme.TIER_COLORS[u.tier]),
                (u.target, theme.TEXT),
            )
            parts.append(line)
    if v.next_steps and not compact:
        parts += [Text(""), Text("WHAT TO DO NEXT", style=f"bold {theme.MUTED}")]
        steps = Table(box=None, show_header=False, padding=(0, 1, 0, 0), expand=True)
        steps.add_column(width=1, no_wrap=True)
        steps.add_column(ratio=1)
        for step in v.next_steps:
            steps.add_row(Text("›", style=color), _step(step))
        parts.append(steps)

    title = Text.assemble(("◉ ", theme.RADAR), ("LureRadar", f"bold {theme.TEXT}"))
    mode = "live" if v.mode == "live" else "offline"
    subtitle = Text(
        f"packs: {', '.join(v.packs)} · {mode} · exit {v.tier.exit_code} · v{__version__}",
        style=theme.MUTED,
    )
    return Panel(
        Padding(Group(*parts), (0, 1)),
        title=title,
        title_align="left",
        subtitle=subtitle,
        subtitle_align="right",
        border_style=color if v.tier >= Tier.LIKELY else theme.BORDER,
        box=box.ROUNDED,
        width=None,
    )


def print_verdict(console: Console, v: Verdict, explain: bool = False) -> None:
    console.print(verdict_card(v, explain=explain))
