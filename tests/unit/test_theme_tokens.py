"""theme.py (terminal card, OG and report images) must match the site's dark tokens."""

from __future__ import annotations

import re
from pathlib import Path

from lureradar import theme

TOKENS = Path(__file__).resolve().parents[2] / "web" / "src" / "styles" / "tokens.css"
PAIRS = {
    "--bg": theme.BG,
    "--surface": theme.SURFACE,
    "--border": theme.BORDER,
    "--text": theme.TEXT,
    "--muted": theme.MUTED,
    "--radar": theme.RADAR,
    "--amber": theme.AMBER,
    "--danger": theme.DANGER,
    "--info": theme.INFO,
}


def test_theme_matches_dark_tokens() -> None:
    css = TOKENS.read_text(encoding="utf-8")
    root = css[css.index(":root {") : css.index("}", css.index(":root {"))]
    for name, value in PAIRS.items():
        m = re.search(rf"{re.escape(name)}:\s*(#[0-9a-fA-F]{{6}});", root)
        assert m, f"{name} missing from the dark :root block"
        assert m.group(1).lower() == value.lower(), (
            f"{name}: tokens.css {m.group(1)} != theme.py {value}"
        )
