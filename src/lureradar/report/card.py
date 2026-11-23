"""Daily "lure report" card: SVG (always), HTML (always), PNG (with resvg-py).

The headline only uses real numbers from stats.json; demo/fixture data is
labelled as such on the card itself.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from lureradar import theme
from lureradar.config import base_url

WIDTH, HEIGHT = 1200, 630


def headline(stats: dict[str, Any], subject: str = "GTA 6") -> str:
    n = int(stats.get("new_24h", 0))
    if n == 0:
        return f"No new fake {subject} download sites in the last 24 hours"
    noun = "site" if n == 1 else "sites"
    return f"{n} new fake {subject} download {noun} detected in the last 24 hours"


def share_text(stats: dict[str, Any], subject: str = "GTA 6", demo: bool = False) -> str:
    tag = " (demo data)" if demo else ""
    return f"{headline(stats, subject)}{tag}. Blocklists and checker: {base_url()} #LureRadar"


def render_svg(stats: dict[str, Any], *, subject: str = "GTA 6", demo: bool = False) -> str:
    active = int(stats.get("active_listed", stats.get("count", 0)))
    week = int(stats.get("new_7d", 0))
    tops = stats.get("top_signals", [])[:3]
    when = str(stats.get("generated_at", ""))[:16].replace("T", " ") + " UTC"
    lines = [escape(line) for line in textwrap.wrap(headline(stats, subject), width=30)][:3]
    bars = ""
    for i, sig in enumerate(tops):
        y = 430 + i * 44
        bars += (
            f'<text x="80" y="{y}" fill="{theme.MUTED}" font-family="JetBrains Mono, monospace" '
            f'font-size="22">{escape(str(sig["id"]))}</text>'
            f'<text x="560" y="{y}" fill="{theme.TEXT}" font-family="JetBrains Mono, monospace" '
            f'font-size="22" text-anchor="end">{int(sig["count"])}</text>'
        )
    head = "".join(
        f'<text x="80" y="{150 + i * 62}" fill="{theme.TEXT}" font-family="Inter, sans-serif" '
        f'font-size="50" font-weight="700">{line}</text>'
        for i, line in enumerate(lines)
    )
    demo_tag = (
        f'<text x="1120" y="70" text-anchor="end" fill="{theme.AMBER}" '
        f'font-family="Inter, sans-serif" font-size="22">DEMO DATA (synthetic fixtures)</text>'
        if demo
        else ""
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
  <rect width="100%" height="100%" fill="{theme.BG}"/>
  <rect x="24" y="24" width="{WIDTH - 48}" height="{HEIGHT - 48}" rx="28" fill="{theme.SURFACE}" stroke="{theme.BORDER}" stroke-width="2"/>
  <g transform="translate(980 330)">
    <circle r="190" fill="none" stroke="{theme.BORDER}" stroke-width="2"/>
    <circle r="125" fill="none" stroke="{theme.BORDER}" stroke-width="2"/>
    <circle r="60" fill="none" stroke="{theme.BORDER}" stroke-width="2"/>
    <path d="M0 0 L190 0 A190 190 0 0 0 134 -134 Z" fill="{theme.RADAR}" fill-opacity="0.18"/>
    <circle cx="96" cy="-70" r="9" fill="{theme.DANGER}"/>
    <circle cx="-60" cy="40" r="7" fill="{theme.AMBER}"/>
    <circle cx="30" cy="110" r="6" fill="{theme.RADAR}"/>
  </g>
  <text x="80" y="70" fill="{theme.RADAR}" font-family="Inter, sans-serif" font-size="26" font-weight="700">LureRadar · daily lure report</text>
  {demo_tag}
  {head}
  <text x="80" y="350" fill="{theme.MUTED}" font-family="Inter, sans-serif" font-size="24">Active blocklisted: <tspan fill="{theme.TEXT}" font-weight="700">{active}</tspan>   ·   New this week: <tspan fill="{theme.TEXT}" font-weight="700">{week}</tspan></text>
  <text x="80" y="392" fill="{theme.MUTED}" font-family="Inter, sans-serif" font-size="20">Top signals</text>
  {bars}
  <text x="80" y="590" fill="{theme.MUTED}" font-family="JetBrains Mono, monospace" font-size="20">{escape(when)} · {escape(base_url())}</text>
</svg>
"""


def render_html(stats: dict[str, Any], svg: str) -> str:
    return (
        "<!doctype html><html lang=en><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>LureRadar daily report</title><body style='margin:0;background:{theme.BG}'>"
        f"<main style='max-width:1200px;margin:auto'>{svg}"
        f"<p style='color:{theme.MUTED};font-family:sans-serif'>{escape(share_text(stats))}</p>"
        "</main></body></html>\n"
    )


def render_png(svg: str) -> bytes | None:
    try:
        import resvg_py
    except ImportError:
        return None
    data = resvg_py.svg_to_bytes(svg_string=svg)
    return bytes(data)


def write_report(stats: dict[str, Any], out_dir: Path, *, demo: bool = False) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    svg = render_svg(stats, demo=demo)
    paths = [out_dir / "lure-report.svg", out_dir / "lure-report.html"]
    paths[0].write_text(svg, encoding="utf-8")
    paths[1].write_text(render_html(stats, svg), encoding="utf-8")
    png = render_png(svg)
    if png:
        p = out_dir / "lure-report.png"
        p.write_bytes(png)
        paths.append(p)
    return paths
