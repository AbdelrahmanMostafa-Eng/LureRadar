"""Frozen signal weights.

These values were tuned against the benchmark (``make bench``) and then frozen;
docs/SIGNALS.md documents each one. Changing a weight is a reviewed change:
re-run ``make bench`` and update docs/BENCHMARKS.md in the same PR.
"""

from __future__ import annotations

from typing import Final

# Lexical / campaign
CLAIMS_UNRELEASED_PLATFORM_HOST: Final = 30
CLAIMS_UNRELEASED_PLATFORM_PATH: Final = 15
CLAIMS_UNRELEASED_PLATFORM_TEXT: Final = 30
KEYWORD_INTENT_COMBO_HOST: Final = 20
KEYWORD_INTENT_COMBO_PATH: Final = 10

# Brand
BRAND_IMPERSONATION: Final = 25
HOMOGLYPH_IDN: Final = 20

# Infrastructure (abused TLD is offline; the rest need --live)
ABUSED_TLD: Final = 8
DOMAIN_AGE_3D: Final = 20
DOMAIN_AGE_14D: Final = 15
DOMAIN_AGE_30D: Final = 8
FRESH_CERT: Final = 5
HOSTING_REPUTATION: Final = 8
REDIRECT_CHAIN: Final = 10

# Content (sum of patterns, capped)
CONTENT_LURE_MAX: Final = 25

# Reputation and trust
EXTERNAL_REPUTATION: Final = 40
ALLOWLISTED: Final = -40
ESTABLISHED_DOMAIN: Final = -15

#: Signals at or above this weight count as "strong" (used by established_domain
#: and by external-reputation corroboration).
STRONG_SIGNAL: Final = 20

#: Default age (days) after which an un-resighted indicator becomes STALE.
STALE_AFTER_DAYS: Final = 30
#: Stale indicators are purged from state after this many days.
PURGE_AFTER_DAYS: Final = 90

# Text-lure analyzer (messages, comments, DMs, ads)
TEXT_FREE_KEY_OFFER: Final = 20
TEXT_OFF_PLATFORM_CONTACT: Final = 15
TEXT_PAYMENT_RED_FLAG: Final = 20
TEXT_URGENCY_SCARCITY: Final = 10
TEXT_DISABLE_SECURITY: Final = 25
TEXT_EXECUTABLE_LURE: Final = 15
TEXT_LINK_SHORTENER: Final = 10
TEXT_TOO_GOOD_TO_BE_TRUE: Final = 15
TEXT_SURVEY_GATE: Final = 20
TEXT_IMPERSONATION_CLAIM: Final = 15
TEXT_ACCOUNT_THREAT: Final = 20
TEXT_RISKY_LINK: Final = 15
TEXT_WARNING_CONTEXT: Final = -25
#: An embedded URL at or above this score makes the message itself riskier.
TEXT_RISKY_LINK_MIN_SCORE: Final = 20

# Page content patterns (summed, then capped at CONTENT_LURE_MAX)
CONTENT_WEIGHTS: Final = {
    "download_cta": 5,
    "survey_gate": 10,
    "keygen_ui": 10,
    "scarcity": 5,
    "installer_links": 10,
    "social_proof": 5,
    "disable_av": 10,
    "unreleased_claim": 10,
}
