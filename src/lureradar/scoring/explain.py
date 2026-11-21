"""Human-readable explanations: signal documentation and "what to do next"."""

from __future__ import annotations

from dataclasses import dataclass

from lureradar.config import issue_url
from lureradar.models import TargetKind, Tier, Verdict


@dataclass(frozen=True)
class SignalDoc:
    title: str
    weight: str
    description: str


SIGNAL_DOCS: dict[str, SignalDoc] = {
    "claims_unreleased_platform": SignalDoc(
        "Claims an unreleased platform",
        "+30 hostname / +15 path",
        "Offers a download or key for a platform the pack's dated facts say has no release "
        "(e.g. a GTA VI PC download while facts.yaml records no PC version).",
    ),
    "keyword_intent_combo": SignalDoc(
        "Campaign keyword + lure intent",
        "+20 hostname / +10 path",
        "A campaign keyword (gta 6, gtavi...) together with an intent term (download, free, "
        "key, crack...). Keywords alone never score.",
    ),
    "brand_impersonation": SignalDoc(
        "Brand impersonation",
        "+25",
        "Typosquat (edit distance or look-alike characters), combosquat (brand plus other "
        "words) or exact brand label on a non-official domain.",
    ),
    "homoglyph_idn": SignalDoc(
        "Homoglyph IDN",
        "+20",
        "Internationalised domain whose characters imitate a brand or campaign keyword "
        "(Unicode confusables skeleton).",
    ),
    "abused_tld": SignalDoc(
        "Abuse-prone TLD",
        "+8",
        "TLD appears on public most-abused-TLD rankings. Never decisive on its own.",
    ),
    "domain_age": SignalDoc(
        "Newly registered",
        "+20 / +15 / +8",
        "RDAP registration less than 3 / 14 / 30 days ago (--live).",
    ),
    "fresh_cert": SignalDoc(
        "Fresh certificate", "+5", "First CT sighting or certificate notBefore < 48h (--live)."
    ),
    "content_lure_patterns": SignalDoc(
        "Lure page patterns",
        "up to +25",
        "Fake download CTA, survey/human-verification gate, key generator UI, countdown or "
        "'keys left', installer links, fake social proof, 'disable antivirus' (--live).",
    ),
    "redirect_chain": SignalDoc(
        "Redirect chain",
        "+10",
        "More than 2 redirects, or cross-domain hops through a URL shortener (--live).",
    ),
    "hosting_reputation": SignalDoc(
        "Hosting reputation",
        "+8",
        "Hosted on an ASN from a sourced reputation list (empty in v0.1.0, --live).",
    ),
    "external_reputation": SignalDoc(
        "External reputation",
        "+40",
        "Flagged by Safe Browsing, URLhaus, OpenPhish or urlscan. Corroborated hits (two "
        "sources, or one plus strong LureRadar evidence) floor the tier at CONFIRMED.",
    ),
    "feed_listed": SignalDoc(
        "Listed in local feed snapshot",
        "0 (floors tier)",
        "Present in the LureRadar feed snapshot pulled with `lureradar feed pull`.",
    ),
    "allowlisted": SignalDoc(
        "Allowlisted outlet",
        "-40 (hard clear)",
        "Established legitimate publisher, store, wiki or official site: always CLEAR.",
    ),
    "user_content_platform": SignalDoc(
        "User-content platform",
        "0 (caps at SUSPICIOUS)",
        "YouTube, Reddit, file hosts...: the domain is never blocklisted; the URL is still "
        "assessed.",
    ),
    "established_domain": SignalDoc(
        "Established domain",
        "-15",
        "Registered more than a year ago and no strong lure signal (--live).",
    ),
    "text_unreleased_platform": SignalDoc(
        "Text: unreleased platform claim",
        "+30",
        "Message offers the game on a platform with no release according to the pack facts.",
    ),
    "text_free_key_offer": SignalDoc(
        "Text: free/early/beta keys", "+20", "Offers free, early-access or beta keys/downloads."
    ),
    "text_off_platform_contact": SignalDoc(
        "Text: off-platform contact", "+15", "Telegram/WhatsApp/Discord/'DM me' redirection."
    ),
    "text_payment_red_flag": SignalDoc(
        "Text: payment red flag", "+20", "Gift cards, crypto or untraceable payment methods."
    ),
    "text_urgency_scarcity": SignalDoc(
        "Text: urgency/scarcity", "+10", "'Only 20 keys left', 'expires tonight'..."
    ),
    "text_disable_security": SignalDoc(
        "Text: disable security", "+25", "Asks to disable antivirus/Defender or run as admin."
    ),
    "text_executable_lure": SignalDoc(
        "Text: executable lure", "+15", "Mentions .exe/.apk/.msi files or archive passwords."
    ),
    "text_link_shortener": SignalDoc(
        "Text: link shortener", "+10", "Shortened links hide the real destination."
    ),
    "text_too_good_to_be_true": SignalDoc(
        "Text: too good to be true",
        "+15",
        "'100% working', 'no survey', 'unlimited money', 'cracked', implausibly low prices.",
    ),
    "text_survey_gate": SignalDoc(
        "Text: survey gate", "+20", "'Complete a survey' / 'human verification' before access."
    ),
    "text_impersonation_claim": SignalDoc(
        "Text: impersonation claim", "+15", "Claims to be brand staff or an official giveaway."
    ),
    "text_account_threat": SignalDoc(
        "Text: account threat",
        "+20",
        "Phishing language: suspended/locked account, 'verify your login', unusual activity.",
    ),
    "text_risky_link": SignalDoc(
        "Text: links to a risky domain",
        "+15",
        "The message links to a URL that itself scores 20 or more.",
    ),
    "text_warning_context": SignalDoc(
        "Text: warning context",
        "-25",
        "Reads as a warning or question about scams (PSA, 'is this real?'), not an offer.",
    ),
}

TIER_LABELS = {
    Tier.CLEAR: "CLEAR",
    Tier.SUSPICIOUS: "SUSPICIOUS",
    Tier.LIKELY: "LIKELY LURE",
    Tier.CONFIRMED: "CONFIRMED LURE",
}


def headline(v: Verdict) -> str:
    ids = {s.id for s in v.signals if s.weight > 0}
    if v.allowlisted:
        return "Allowlisted legitimate outlet"
    if v.tier is Tier.CLEAR:
        return "No lure signals strong enough to flag" if ids else "No lure signals found"
    parts = []
    if "claims_unreleased_platform" in ids or "text_unreleased_platform" in ids:
        parts.append("unreleased platform")
    if "brand_impersonation" in ids or "homoglyph_idn" in ids:
        parts.append("brand impersonation")
    if "keyword_intent_combo" in ids and not parts:
        parts.append("campaign keyword with download/key intent")
    if "external_reputation" in ids:
        parts.append("flagged by external reputation")
    if v.kind is TargetKind.TEXT and not parts:
        parts.append("lure language")
    return (
        ("Looks like a launch lure: " + " + ".join(parts)) if parts else "Lure indicators present"
    )


def next_steps(v: Verdict, facts_note: str | None = None) -> list[str]:
    steps: list[str] = []
    if v.allowlisted:
        steps.append(
            "This domain is on the allowlist. Still check the exact link before downloading."
        )
        return steps
    if v.tier is Tier.CLEAR:
        if v.mode == "offline" and v.kind is not TargetKind.TEXT:
            steps.append(
                "Offline heuristics found nothing decisive. That is not a guarantee: re-run with "
                "--live for DNS, RDAP, TLS and page checks."
            )
        else:
            steps.append("Nothing decisive found. Stay cautious with unexpected offers.")
        return steps
    if facts_note:
        steps.append(facts_note)
    if v.tier is Tier.SUSPICIOUS:
        steps += [
            "Do not download files or sign in until you have verified the source.",
            "Buy and download games only through official stores and publisher sites.",
        ]
        if v.mode == "offline" and v.kind is not TargetKind.TEXT:
            steps.append("Re-check with --live for registration age and page content.")
    else:
        steps += [
            "Do not visit, download, enter credentials or pay.",
            "Block it: subscribe to the LureRadar feeds (Pi-hole, AdGuard, uBlock Origin).",
        ]
        if v.kind is not TargetKind.TEXT and v.host:
            steps.append("Report it: " + issue_url("report-a-lure.yml", f"[Lure] {v.host}"))
        if v.tier is Tier.CONFIRMED and v.host:
            steps.append(f"Takedown help: lureradar report --abuse {v.host}")
    steps.append("Think this is wrong? Dispute it: " + issue_url("false-positive-review.yml"))
    return steps
