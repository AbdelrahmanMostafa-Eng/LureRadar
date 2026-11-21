"""Design tokens shared by the terminal card, report images and the website.

Mirrors ``web/src/styles/tokens.css`` (a test keeps them in sync).
"""

from __future__ import annotations

from typing import Final

from lureradar.models import Tier

BG: Final = "#07090D"
SURFACE: Final = "#0D1117"
BORDER: Final = "#1B232C"
TEXT: Final = "#E6EDF3"
MUTED: Final = "#8B98A5"
RADAR: Final = "#3CFFB0"
AMBER: Final = "#FFB020"
DANGER: Final = "#FF4D5E"
INFO: Final = "#4CC2FF"

TIER_COLORS: Final = {
    Tier.CLEAR: RADAR,
    Tier.SUSPICIOUS: AMBER,
    Tier.LIKELY: DANGER,
    Tier.CONFIRMED: DANGER,
}
