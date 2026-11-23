"""Render LureRadar's raster brand assets with resvg (no browser needed).

    uv run python scripts/gen_og.py            # social preview + favicons
    uv run python scripts/gen_og.py --radar-gif FRAMES_DIR   # assets/screenshots/radar.gif
    (build_site_data.py calls render_site_cards() for per-page OG images)

Outputs:
* ``assets/social-preview-1280x640.png`` - GitHub/X/Reddit/Slack link preview;
* ``assets/favicon/*.png`` + ``site.webmanifest`` (also copied to web/public);
* ``web/public/og/*.png`` - per-page Open Graph cards (1200x630), including a
  daily stats card and a PC Watch card built from real (or labelled demo) data.

Fonts: Inter and JetBrains Mono (SIL OFL 1.1) TTFs from the npm packages
``@expo-google-fonts/inter`` and ``@expo-google-fonts/jetbrains-mono``
(``cd web && npm ci``). If those are missing, system Inter/DejaVu fonts are
used, so output may differ slightly.
"""

from __future__ import annotations

import json
import shutil
import sys
import textwrap
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
WEB = ROOT / "web"
PUBLIC = WEB / "public"

T = {
    "bg": "#07090D", "surface": "#0D1117", "border": "#1B232C", "text": "#E6EDF3",
    "muted": "#8B98A5", "radar": "#3CFFB0", "amber": "#FFB020", "danger": "#FF4D5E",
    "info": "#4CC2FF",
}  # fmt: skip
TIER = {
    "clear": ("CLEAR", T["radar"]),
    "suspicious": ("SUSPICIOUS", T["amber"]),
    "likely": ("LIKELY LURE", T["danger"]),
    "confirmed": ("CONFIRMED LURE", T["danger"]),
}


def font_files() -> list[str]:
    npm = WEB / "node_modules" / "@expo-google-fonts"
    wanted = [
        npm / "inter" / "400Regular" / "Inter_400Regular.ttf",
        npm / "inter" / "500Medium" / "Inter_500Medium.ttf",
        npm / "inter" / "600SemiBold" / "Inter_600SemiBold.ttf",
        npm / "inter" / "700Bold" / "Inter_700Bold.ttf",
        npm / "jetbrains-mono" / "400Regular" / "JetBrainsMono_400Regular.ttf",
        npm / "jetbrains-mono" / "500Medium" / "JetBrainsMono_500Medium.ttf",
        npm / "jetbrains-mono" / "700Bold" / "JetBrainsMono_700Bold.ttf",
    ]
    found = [str(p) for p in wanted if p.is_file()]
    if len(found) == len(wanted):
        return found
    system = [
        Path("/usr/share/fonts/opentype/inter"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"),
    ]
    for p in system:
        if p.is_dir():
            found += [str(f) for f in p.glob("Inter-*.otf") if "Italic" not in f.name]
        elif p.is_file():
            found.append(str(p))
    return found


def render(svg: str, out: Path, width: int | None = None) -> Path:
    import resvg_py

    out.parent.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {
        "svg_string": svg,
        "font_files": font_files(),
        "skip_system_fonts": True,
        "font_family": "Inter",
        "monospace_family": "JetBrains Mono",
        "sans_serif_family": "Inter",
    }
    if width:
        kwargs["width"] = width
    out.write_bytes(bytes(resvg_py.svg_to_bytes(**kwargs)))
    return out


# ------------------------------------------------------------------ pieces
def mark(x: float, y: float, scale: float, ring: str = T["radar"], hook: str = T["amber"]) -> str:
    """The LureRadar mark (same geometry as web/scripts/gen-brand.mjs)."""
    uid = f"m{int(x)}{int(y)}"
    return f"""
    <g transform="translate({x} {y}) scale({scale})">
      <defs><linearGradient id="{uid}" x1="32" y1="32" x2="54" y2="12" gradientUnits="userSpaceOnUse">
        <stop offset="0" stop-color="{ring}" stop-opacity="0"/><stop offset="1" stop-color="{ring}" stop-opacity=".6"/>
      </linearGradient></defs>
      <circle cx="32" cy="32" r="27" fill="none" stroke="{ring}" stroke-width="4"/>
      <circle cx="32" cy="32" r="15.5" fill="none" stroke="{ring}" stroke-width="2.5" opacity=".45"/>
      <path d="M32 32V5a27 27 0 0 1 23.4 13.5Z" fill="url(#{uid})"/>
      <path d="M32 32 55.4 18.5" stroke="{ring}" stroke-width="3" stroke-linecap="round"/>
      <circle cx="32" cy="32" r="3.2" fill="{ring}"/>
      <g fill="none" stroke="{hook}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M43 36.5V44a4.5 4.5 0 0 1-9 0v-3.2l2.8 2.6"/><circle cx="43" cy="33.6" r="1.9" stroke-width="2.4"/>
      </g>
    </g>"""


def hook(x: float, y: float, s: float, color: str, op: float = 1) -> str:
    return (
        f'<g transform="translate({x} {y}) scale({s})" fill="none" stroke="{color}" '
        f'stroke-opacity="{op}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M0 -6V4a5 5 0 0 1-10 0v-3.5l3 2.8"/><circle cx="0" cy="-9" r="2" stroke-width="2.4"/></g>'
    )


def radar_backdrop(w: int, h: int, cx: float, cy: float, r: float) -> str:
    rings = "".join(
        f'<circle cx="{cx}" cy="{cy}" r="{r * k:.1f}" fill="none" stroke="{T["radar"] if k == 1 else T["border"]}" '
        f'stroke-opacity="{0.35 if k == 1 else 1}" stroke-width="{2 if k == 1 else 1.5}"/>'
        for k in (0.25, 0.5, 0.75, 1)
    )
    ex, ey = cx + r * 0.866, cy - r * 0.5
    return f"""
    <defs>
      <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
        <path d="M32 0H0V32" fill="none" stroke="{T["border"]}" stroke-width="1" opacity=".5"/></pattern>
      <radialGradient id="glow" cx="{cx}" cy="{cy}" r="{r * 1.3}" gradientUnits="userSpaceOnUse">
        <stop offset="0" stop-color="{T["radar"]}" stop-opacity=".11"/><stop offset="1" stop-color="{T["radar"]}" stop-opacity="0"/></radialGradient>
      <linearGradient id="sweep" x1="{cx}" y1="{cy}" x2="{cx + r * 0.7}" y2="{cy - r * 0.7}" gradientUnits="userSpaceOnUse">
        <stop offset="0" stop-color="{T["radar"]}" stop-opacity="0"/><stop offset="1" stop-color="{T["radar"]}" stop-opacity=".4"/></linearGradient>
      <linearGradient id="fade" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="{T["bg"]}"/><stop offset=".5" stop-color="{T["bg"]}" stop-opacity=".25"/>
        <stop offset="1" stop-color="{T["bg"]}" stop-opacity="0"/></linearGradient>
    </defs>
    <rect width="{w}" height="{h}" fill="{T["bg"]}"/>
    <rect width="{w}" height="{h}" fill="url(#grid)"/>
    <rect width="{w}" height="{h}" fill="url(#fade)"/>
    <circle cx="{cx}" cy="{cy}" r="{r * 1.3}" fill="url(#glow)"/>
    {rings}
    <path d="M{cx - r} {cy}H{cx + r}M{cx} {cy - r}V{cy + r}" stroke="{T["border"]}" stroke-width="1.5"/>
    <path d="M{cx} {cy}L{cx} {cy - r}A{r} {r} 0 0 1 {ex:.1f} {ey:.1f}Z" fill="url(#sweep)"/>
    <path d="M{cx} {cy}L{ex:.1f} {ey:.1f}" stroke="{T["radar"]}" stroke-width="2.5" stroke-linecap="round"/>
    <circle cx="{cx + r * 0.3}" cy="{cy - r * 0.62}" r="5" fill="{T["radar"]}" fill-opacity=".9"/>
    <circle cx="{cx - r * 0.55}" cy="{cy + r * 0.25}" r="4" fill="{T["radar"]}" fill-opacity=".5"/>
    {hook(cx + r * 0.5, cy - r * 0.2, 1.7, T["amber"])}
    {hook(cx - r * 0.3, cy - r * 0.42, 1.4, T["danger"], 0.85)}
    {hook(cx + r * 0.18, cy + r * 0.55, 1.3, T["amber"], 0.55)}
    <circle cx="{cx}" cy="{cy}" r="6" fill="{T["radar"]}"/>"""


def wordmark(x: float, y: float, size: int) -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="Inter" font-weight="700" font-size="{size}" '
        f'letter-spacing="-1.5" fill="{T["text"]}">Lure<tspan fill="{T["radar"]}">Radar</tspan></text>'
    )


def wrap(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=width) or [text]


# --------------------------------------------------------------- products
def demo_verdict() -> dict[str, Any]:
    """The real verdict for the README demo command (never hand-written numbers)."""
    from lureradar.scoring.engine import Engine

    v = Engine(pack_ids=["gta6"]).check("https://rockstar-gta6-pc-download[.]test/free-key")
    return {
        "target": v.target,
        "tier": v.tier.value,
        "score": v.score,
        "signals": [(s.id, s.weight) for s in v.signals if s.weight][:3],
    }


def social_preview(out: Path) -> Path:
    W, H = 1280, 640
    v = demo_verdict()
    label, color = TIER[v["tier"]]
    bar_w = 520
    filled = bar_w * v["score"] / 100
    ticks = "".join(
        f'<rect x="{92 + bar_w * t / 100 - 1:.1f}" y="462" width="2" height="18" fill="{T["muted"]}" fill-opacity=".7"/>'
        for t in (40, 70, 90)
    )
    bar = (
        f'<rect x="92" y="464" width="{bar_w}" height="14" rx="7" fill="{T["border"]}"/>'
        f'<rect x="92" y="464" width="{filled:.1f}" height="14" rx="7" fill="{color}"/>{ticks}'
    )
    rows = "".join(
        f'<text x="92" y="{512 + i * 30}" font-family="JetBrains Mono" font-size="19" fill="{T["text"]}">'
        f'<tspan fill="{T["danger"] if w >= 20 else T["amber"]}" font-weight="700">+{w}</tspan>  {escape(sid)}</text>'
        for i, (sid, w) in enumerate(v["signals"])
    )
    card_w = 640
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
    {radar_backdrop(W, H, 1040, 300, 300)}
    {mark(64, 74, 1.25)}
    {wordmark(158, 132, 74)}
    <text x="66" y="196" font-family="Inter" font-weight="500" font-size="34" fill="{T["muted"]}">See the lure before you bite.</text>
    <text x="66" y="244" font-family="Inter" font-size="22" fill="{T["muted"]}">Open threat radar for hyped-launch scams: fake downloads,</text>
    <text x="66" y="274" font-family="Inter" font-size="22" fill="{T["muted"]}">key-gen traps and phishing. Explainable. Offline. Free blocklists.</text>
    <rect x="66" y="318" width="{card_w}" height="268" rx="16" fill="{T["surface"]}" stroke="{color}" stroke-opacity=".7" stroke-width="2"/>
    <circle cx="92" cy="344" r="6" fill="{T["danger"]}" fill-opacity=".85"/><circle cx="112" cy="344" r="6" fill="{T["amber"]}" fill-opacity=".85"/><circle cx="132" cy="344" r="6" fill="{T["radar"]}" fill-opacity=".85"/>
    <text x="92" y="388" font-family="JetBrains Mono" font-size="17" fill="{T["muted"]}"><tspan fill="{T["radar"]}">$</tspan> uvx lureradar check "{escape(v["target"])}"</text>
    <rect x="90" y="410" width="{len(label) * 12.2 + 22:.0f}" height="34" rx="6" fill="{color}"/>
    <text x="101" y="433" font-family="JetBrains Mono" font-weight="700" font-size="19" fill="{T["bg"]}">{label}</text>
    <text x="{90 + len(label) * 12.2 + 38:.0f}" y="434" font-family="JetBrains Mono" font-weight="700" font-size="22" fill="{color}">{v["score"]}<tspan fill="{T["muted"]}" font-weight="400" font-size="17">/100</tspan></text>
    {bar}
    {rows}
    <text x="{W - 64}" y="{H - 34}" text-anchor="end" font-family="JetBrains Mono" font-size="17" fill="{T["muted"]}">offline CLI · explainable scores · Pi-hole · uBlock · RPZ · STIX</text>
    <rect x="1" y="1" width="{W - 2}" height="{H - 2}" fill="none" stroke="{T["border"]}" stroke-width="2"/>
    </svg>"""
    return render(svg, out)


def page_card(out: Path, title: str, subtitle: str, *, badge: str | None = None,
              accent: str = T["radar"], footer: str = "") -> Path:  # fmt: skip
    W, H = 1200, 630
    from lureradar.config import base_url

    lines = wrap(title, 26)[:3]
    title_svg = "".join(
        f'<text x="72" y="{250 + i * 76}" font-family="Inter" font-weight="700" font-size="66" '
        f'letter-spacing="-1" fill="{T["text"]}">{escape(line)}</text>'
        for i, line in enumerate(lines)
    )
    sub_y = 250 + len(lines) * 76 + 18
    sub_svg = "".join(
        f'<text x="74" y="{sub_y + i * 38}" font-family="Inter" font-size="28" fill="{T["muted"]}">{escape(line)}</text>'
        for i, line in enumerate(wrap(subtitle, 58)[:2])
    )
    badge_svg = ""
    if badge:
        bw = len(badge) * 11.5 + 32
        badge_svg = (
            f'<rect x="72" y="134" width="{bw:.0f}" height="38" rx="19" fill="{accent}" fill-opacity=".14" '
            f'stroke="{accent}" stroke-opacity=".6"/><text x="88" y="159" font-family="JetBrains Mono" '
            f'font-weight="700" font-size="18" fill="{accent}">{escape(badge)}</text>'
        )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
    {radar_backdrop(W, H, 1020, 300, 260)}
    {mark(70, 50, 0.85)}
    <text x="134" y="92" font-family="Inter" font-weight="700" font-size="34" letter-spacing="-.5" fill="{T["text"]}">Lure<tspan fill="{T["radar"]}">Radar</tspan></text>
    {badge_svg}{title_svg}{sub_svg}
    <text x="74" y="{H - 44}" font-family="JetBrains Mono" font-size="20" fill="{T["muted"]}">{escape(footer or base_url())}</text>
    <rect x="0" y="{H - 8}" width="{W}" height="8" fill="{accent}"/>
    </svg>"""
    return render(svg, out)


def render_site_cards(
    out_dir: Path, *, stats: dict[str, Any], pcwatch: dict[str, Any], demo: bool
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    demo_badge = "DEMO DATA · synthetic fixtures" if demo else None
    pages = {
        "default": ("See the lure before you bite.", "Open threat radar for hyped-launch scams. Explainable scores, offline CLI, free blocklists."),
        "radar": ("Latest launch-lure detections", "Every indicator with its signals and evidence, defanged."),
        "check": ("Is this link a lure?", "Check a URL, domain or message in your browser. Nothing is sent anywhere."),
        "feeds": ("Block GTA 6 scam sites in 60 seconds", "Free blocklists for Pi-hole, AdGuard, uBlock Origin, hosts and RPZ."),
        "methodology": ("How LureRadar scores a lure", "Named signals, frozen weights, reproducible benchmarks, honest blind spots."),
        "packs": ("Campaign packs", "Add a hyped launch in about 20 lines of YAML."),
        "report": ("Report a lure", "Help others: submit a scam link or dispute a listing."),
        "about": ("About LureRadar", "Independent, open-source, defensive. No trackers, no accounts."),
    }  # fmt: skip
    for name, (title, sub) in pages.items():
        page_card(
            out_dir / f"{name}.png", title, sub, badge=demo_badge if name == "radar" else None
        )
    new24 = int(stats.get("new_24h") or 0)
    if new24:
        title = f"Today: {new24} new fake GTA 6 download site{'s' if new24 != 1 else ''} caught"
    else:
        title = "No new fake GTA 6 download sites in the last 24 hours"
    sub = f"{stats.get('active_listed', 0)} active indicators in the free blocklists · updated {str(stats.get('generated_at', ''))[:16].replace('T', ' ')} UTC"
    page_card(
        out_dir / "stats.png",
        title,
        sub,
        badge=demo_badge or "LIVE STATS",
        accent=T["danger"] if new24 else T["radar"],
    )
    status = str(pcwatch.get("status", "UNKNOWN"))
    accent = {"NOT_ANNOUNCED": T["radar"], "UNKNOWN": T["muted"]}.get(status, T["amber"])
    page_card(
        out_dir / "pc-watch.png",
        "Is GTA 6 coming to PC?",
        str(pcwatch.get("answer") or "Official sources only. Dated, cited, humble."),
        badge=f"PC WATCH · {status.replace('_', ' ')}",
        accent=accent,
    )


def favicons() -> None:
    src = (ASSETS / "favicon" / "favicon.svg").read_text("utf-8")
    sizes = {"favicon-16.png": 16, "favicon-32.png": 32, "apple-touch-icon.png": 180,
             "icon-192.png": 192, "icon-512.png": 512}  # fmt: skip
    for name, size in sizes.items():
        render(src, ASSETS / "favicon" / name, width=size)
    manifest = {
        "name": "LureRadar",
        "short_name": "LureRadar",
        "description": "See the lure before you bite. Open threat radar for hyped-launch scams.",
        "start_url": ".",
        "scope": ".",
        "display": "standalone",
        "background_color": T["bg"],
        "theme_color": T["bg"],
        "icons": [
            {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "favicon.svg", "sizes": "any", "type": "image/svg+xml"},
        ],
    }
    (ASSETS / "favicon" / "site.webmanifest").write_text(
        json.dumps(manifest, indent=2) + "\n", "utf-8"
    )
    PUBLIC.mkdir(parents=True, exist_ok=True)
    for f in (ASSETS / "favicon").iterdir():
        shutil.copyfile(f, PUBLIC / f.name)


def radar_gif(frames_dir: Path, out: Path, fps: int = 12, max_bytes: int = 3_000_000) -> Path:
    """Assemble radar animation frames (web/scripts/screenshots.mjs) into a looping GIF."""
    from PIL import Image

    paths = sorted(frames_dir.glob("f*.png"))
    if not paths:
        raise SystemExit(f"no frames in {frames_dir}")
    width = 440
    for colors in (160, 128, 96, 64):
        frames = []
        for p in paths:
            im = Image.open(p).convert("RGB")
            im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
            frames.append(
                im.quantize(
                    colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
                )
            )
        out.parent.mkdir(parents=True, exist_ok=True)
        frames[0].save(out, save_all=True, append_images=frames[1:], duration=round(1000 / fps),
                       loop=0, optimize=True, disposal=1)  # fmt: skip
        if out.stat().st_size <= max_bytes:
            break
    return out


def main() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    if len(sys.argv) == 3 and sys.argv[1] == "--radar-gif":
        out = radar_gif(Path(sys.argv[2]), ASSETS / "screenshots" / "radar.gif")
        print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KiB)")
        return 0
    favicons()
    out = social_preview(ASSETS / "social-preview-1280x640.png")
    print(f"wrote {out.relative_to(ROOT)} and favicons")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
