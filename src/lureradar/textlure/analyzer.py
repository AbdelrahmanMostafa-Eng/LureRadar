"""Text-lure analyzer.

Input: a message such as "free GTA 6 PC beta key, DM me on Telegram".
Output: explainable text signals plus the URLs found in the text (the engine
scores those URLs separately and combines the results).

No LLM, no network: regular expressions and the pack's keywords/facts only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lureradar.detectors.base import CampaignIndex, shorteners
from lureradar.detectors.intent import claim_explanation, unreleased_claim
from lureradar.detectors.lexical import analyse
from lureradar.errors import LureRadarError
from lureradar.models import Signal
from lureradar.scoring import weights
from lureradar.textlure import patterns as p
from lureradar.util.defang import defang, defang_text, refang
from lureradar.util.domains import find_urls, parse_target

MAX_TEXT = 20_000


@dataclass
class TextAnalysis:
    signals: list[Signal] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    campaign_packs: list[str] = field(default_factory=list)


def _sig(sid: str, weight: int, explanation: str, matches: list[p.Match]) -> Signal:
    return Signal(
        id=sid,
        weight=weight,
        category="text",
        explanation=explanation,
        evidence=tuple(defang_text(m.snippet) for m in matches[:3]),
    )


def _brand_regex(indexes: tuple[CampaignIndex, ...]) -> re.Pattern[str] | None:
    names: set[str] = set()
    for idx in indexes:
        for brand in idx.pack.brands:
            names.add(brand.name)
            names.update(a for a in brand.aliases if len(a) >= 4)
    if not names:
        return None
    alt = "|".join(sorted((re.escape(n) for n in names), key=len, reverse=True))
    return re.compile(
        rf"\b(?:i|we)\s+(?:work|am|are)\s+(?:at|for|with)\s+(?:{alt})\b"
        rf"|\bofficial\s+(?:{alt})(?:\s+games)?\s+(?:giveaway|support|team|admin|staff|partner)\b"
        rf"|\b(?:{alt})(?:\s+games)?\s+(?:support|admin|staff|moderator|employee)\b"
        rf"|\byour\s+(?:{alt})(?:\s+games)?\s+account\s+(?:is|has|will|was)\b",
        re.IGNORECASE,
    )


def analyze_text(text: str, indexes: tuple[CampaignIndex, ...]) -> TextAnalysis:
    """Analyse a message. Never fetches anything."""
    clean = refang(text[:MAX_TEXT])
    out = TextAnalysis()
    out.urls = list(dict.fromkeys(find_urls(clean)))

    # Campaign context and unreleased-platform claims (pack facts)
    claim_signal: Signal | None = None
    for idx in indexes:
        hits = analyse(clean, idx)
        if hits.keywords or hits.brands:
            out.campaign_packs.append(idx.id)
        claim = unreleased_claim(hits, idx)
        if claim and claim_signal is None:
            platform, term, acq = claim
            claim_signal = Signal(
                id="text_unreleased_platform",
                weight=weights.CLAIMS_UNRELEASED_PLATFORM_TEXT,
                category="platform",
                explanation=claim_explanation(idx, platform, acq),
                evidence=(f"{hits.keywords[0] if hits.keywords else ''} + {term} + {acq}",),
            )
    campaign = bool(out.campaign_packs)
    if claim_signal:
        out.signals.append(claim_signal)

    checks: list[tuple[str, int, str, list[p.Match], bool]] = [
        (
            "text_free_key_offer",
            weights.TEXT_FREE_KEY_OFFER,
            "Offers free/early/beta keys, codes or downloads",
            p.find_all(p.FREE_OFFER, clean),
            campaign,
        ),
        (
            "text_off_platform_contact",
            weights.TEXT_OFF_PLATFORM_CONTACT,
            "Moves the conversation off-platform (Telegram, WhatsApp, Discord, DMs)",
            p.find_all(p.OFF_PLATFORM, clean),
            True,
        ),
        (
            "text_payment_red_flag",
            weights.TEXT_PAYMENT_RED_FLAG,
            "Asks for gift cards, crypto or untraceable payment",
            p.find_all(p.PAYMENT, clean),
            True,
        ),
        (
            "text_urgency_scarcity",
            weights.TEXT_URGENCY_SCARCITY,
            "Urgency or scarcity pressure (limited keys, expiring offer)",
            p.find_all(p.URGENCY, clean),
            True,
        ),
        (
            "text_disable_security",
            weights.TEXT_DISABLE_SECURITY,
            "Asks you to disable antivirus/Defender or run as administrator",
            p.find_all(p.DISABLE_SECURITY, clean),
            True,
        ),
        (
            "text_account_threat",
            weights.TEXT_ACCOUNT_THREAT,
            "Account-threat phishing language (suspended account, verify your login)",
            p.find_all(p.ACCOUNT_THREAT, clean),
            True,
        ),
        (
            "text_survey_gate",
            weights.TEXT_SURVEY_GATE,
            "Survey, offer or 'human verification' gate before the download",
            p.find_all(p.SURVEY, clean),
            True,
        ),
        (
            "text_too_good_to_be_true",
            weights.TEXT_TOO_GOOD_TO_BE_TRUE,
            "Too-good-to-be-true promise (100% working, no survey, unlimited money, cracked)",
            p.find_all(p.TOO_GOOD, clean),
            True,
        ),
    ]
    executables = p.find_all(p.EXECUTABLE, clean) + p.find_all(p.ARCHIVE_PASSWORD, clean)
    checks.append(
        (
            "text_executable_lure",
            weights.TEXT_EXECUTABLE_LURE,
            "Points to an executable, installer or password-protected archive",
            executables,
            True,
        )
    )
    cheap = p.find_all(p.CHEAP_PRICE, clean) if campaign else []
    if cheap and not any(c[0] == "text_too_good_to_be_true" and c[3] for c in checks):
        checks.append(
            (
                "text_too_good_to_be_true",
                weights.TEXT_TOO_GOOD_TO_BE_TRUE,
                "Price far below retail for a new release",
                cheap,
                True,
            )
        )
    brand_rx = _brand_regex(indexes)
    if brand_rx:
        checks.append(
            (
                "text_impersonation_claim",
                weights.TEXT_IMPERSONATION_CLAIM,
                "Claims to be staff, support or an 'official giveaway' of a brand",
                p.find_all(brand_rx, clean),
                True,
            )
        )

    seen: set[str] = set()
    for sid, weight, explanation, matches, enabled in checks:
        if enabled and matches and sid not in seen:
            seen.add(sid)
            out.signals.append(_sig(sid, weight, explanation, matches))

    short = []
    for url in out.urls:
        try:
            reg = parse_target(url).registrable_domain
        except LureRadarError:
            continue
        if reg in shorteners():
            short.append(p.Match(defang(url), 0, 0))
    if short:
        out.signals.append(
            _sig(
                "text_link_shortener",
                weights.TEXT_LINK_SHORTENER,
                "Uses a link shortener that hides the real destination",
                short,
            )
        )

    warnings = p.find_warnings(clean)
    positive = sum(s.weight for s in out.signals if s.weight > 0)
    if warnings and positive > 0:
        out.signals.append(
            _sig(
                "text_warning_context",
                weights.TEXT_WARNING_CONTEXT,
                "Reads as a warning or question about scams rather than an offer",
                warnings,
            )
        )
    return out
