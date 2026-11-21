"""``content_lure_patterns``: lure patterns in a fetched page (``--live`` only).

Feature extraction is pure (HTML string in, features out) and never executes
JavaScript. Only short trimmed snippets are kept, never the page itself.
"""

from __future__ import annotations

from urllib.parse import urljoin

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from lureradar.detectors.base import CampaignIndex, Context
from lureradar.detectors.intent import unreleased_claim
from lureradar.detectors.lexical import analyse, find_keywords
from lureradar.enrich.types import ContentFeatures
from lureradar.models import Signal
from lureradar.scoring import weights
from lureradar.textlure import patterns as p
from lureradar.util.defang import defang_text

INSTALLER_EXT = (
    ".exe",
    ".msi",
    ".apk",
    ".ipa",
    ".dmg",
    ".pkg",
    ".zip",
    ".rar",
    ".7z",
    ".scr",
    ".bat",
)
MAX_TEXT = 60_000


def _snips(matches: list[p.Match]) -> list[str]:
    return [m.snippet for m in matches[:3]]


def extract_features(
    html: str, base_url: str, indexes: tuple[CampaignIndex, ...]
) -> ContentFeatures:
    tree = HTMLParser(html)
    for node in tree.css("script, style, noscript, template, svg"):
        node.decompose()
    title_node = tree.css_first("title")
    title = " ".join(title_node.text().split())[:160] if title_node else None
    body = tree.body
    text = " ".join((body.text(separator=" ") if body else tree.text(separator=" ")).split())
    text = text[:MAX_TEXT]
    full = f"{title or ''} {text}"

    mentions = 0
    claim: str | None = None
    for idx in indexes:
        mentions += len(find_keywords(full, idx))
        if claim is None:
            found = unreleased_claim(analyse(full[:5000], idx), idx)
            if found:
                platform, term, acq = found
                claim = f"{acq} on {term} ({platform})"

    installer: list[str] = []
    for a in tree.css("a[href]"):
        href = (a.attributes.get("href") or "").strip()
        path = href.split("?", 1)[0].split("#", 1)[0].lower()
        if path.endswith(INSTALLER_EXT):
            installer.append(urljoin(base_url, href)[:160])
        if len(installer) >= 5:
            break

    scarcity = _snips(p.find_all(p.URGENCY, full))
    if p.COUNTDOWN.search(full):
        scarcity.append("countdown timer")
    return ContentFeatures(
        title=title,
        campaign_mentions=mentions,
        download_cta=_snips(p.find_all(p.DOWNLOAD_CTA, full)),
        survey_gate=_snips(p.find_all(p.SURVEY, full)),
        keygen_ui=_snips(p.find_all(p.KEYGEN_UI, full)),
        scarcity=scarcity[:3],
        installer_links=installer,
        social_proof=_snips(p.find_all(p.SOCIAL_PROOF, full)),
        disable_av=_snips(p.find_all(p.DISABLE_SECURITY, full)),
        unreleased_claim=claim,
    )


def score_features(f: ContentFeatures) -> tuple[int, list[str]]:
    """Return (capped weight, matched pattern descriptions)."""
    relevant = f.campaign_mentions > 0
    total = 0
    found: list[str] = []
    table = weights.CONTENT_WEIGHTS
    checks: list[tuple[str, list[str] | str | None, bool]] = [
        ("download_cta", f.download_cta, relevant),
        ("survey_gate", f.survey_gate, True),
        ("keygen_ui", f.keygen_ui, True),
        ("scarcity", f.scarcity, relevant),
        ("installer_links", f.installer_links, relevant),
        ("social_proof", f.social_proof, relevant),
        ("disable_av", f.disable_av, True),
        ("unreleased_claim", f.unreleased_claim, True),
    ]
    for name, value, enabled in checks:
        if enabled and value:
            total += table[name]
            sample = value if isinstance(value, str) else value[0]
            found.append(f"{name.replace('_', ' ')}: {defang_text(sample)[:60]}")
    return min(total, weights.CONTENT_LURE_MAX), found


def detect_content_lure_patterns(ctx: Context) -> list[Signal]:
    e = ctx.enrichment
    if e is None or e.http is None or e.http.features is None or ctx.allow.outlet:
        return []
    weight, found = score_features(e.http.features)
    if weight <= 0:
        return []
    return [
        Signal(
            id="content_lure_patterns",
            weight=weight,
            category="content",
            live=True,
            explanation=f"Page shows {len(found)} lure pattern(s): "
            + "; ".join(x.split(":", 1)[0] for x in found),
            evidence=tuple(found[:4]),
        )
    ]
