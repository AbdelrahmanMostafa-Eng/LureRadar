"""Design tokens shared by the terminal card, report images and the website.

Mirrors the dark theme in ``web/src/styles/tokens.css``;
``tests/unit/test_theme_tokens.py`` fails if the two drift.
"""

from __future__ import annotations

from typing import Final

from lureradar.models import Tier

BG: Final = "#080A09"
SURFACE: Final = "#0F1311"
BORDER: Final = "#1E2420"
TEXT: Final = "#E8EBE5"
MUTED: Final = "#8C948D"
RADAR: Final = "#5BE6A7"
AMBER: Final = "#F2B84B"
DANGER: Final = "#FF6B5F"
INFO: Final = "#9CC0FF"

TIER_COLORS: Final = {
    Tier.CLEAR: RADAR,
    Tier.SUSPICIOUS: AMBER,
    Tier.LIKELY: DANGER,
    Tier.CONFIRMED: DANGER,
}
