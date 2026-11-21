"""``claims_unreleased_platform``: offers a download/key for a platform that the
pack's dated facts say does not exist (e.g. a GTA VI PC version, as of the
date in packs/gta6/facts.yaml)."""

from __future__ import annotations

from lureradar.detectors.base import CampaignIndex, Context
from lureradar.detectors.lexical import TermHits, host_hits, path_hits
from lureradar.models import Signal
from lureradar.scoring import weights
from lureradar.util.defang import defang

# Platform terms that are themselves a download (an Android/iOS package).
SELF_ACQUIRING = frozenset({"apk", "ipa"})


def unreleased_claim(hits: TermHits, index: CampaignIndex) -> tuple[str, str, str] | None:
    """Return ``(platform, platform_term, acquisition_term)`` if ``hits`` claim one."""
    if not hits.keywords or not hits.unreleased:
        return None
    acquisition = [i for i in hits.intents if i in index.acquisition]
    for platform, terms in hits.unreleased.items():
        self_acq = [t for t in terms if t in SELF_ACQUIRING]
        if acquisition or self_acq:
            return platform, terms[0], (acquisition or self_acq)[0]
    return None


def _fact_note(index: CampaignIndex, platform: str) -> str:
    facts = index.pack.facts
    if not facts:
        return ""
    plat = facts.platforms.get(platform)
    fact = facts.fact(plat.fact) if plat and plat.fact else None
    if fact:
        return f" (fact {fact.id}, as of {fact.as_of.isoformat()})"
    return f" (facts as of {facts.as_of.isoformat()})"


def claim_explanation(index: CampaignIndex, platform: str, acq: str) -> str:
    pack = index.pack
    label = pack.platform_label(platform)
    return (
        f'Promises "{acq}" of {pack.subject_label} for {label}: no official {label} '
        f"release exists{_fact_note(index, platform)}"
    )


def detect_claims_unreleased_platform(ctx: Context) -> list[Signal]:
    best: Signal | None = None
    for index in ctx.indexes:
        for where, hits, weight in (
            ("hostname", host_hits(ctx, index), weights.CLAIMS_UNRELEASED_PLATFORM_HOST),
            ("URL path", path_hits(ctx, index), weights.CLAIMS_UNRELEASED_PLATFORM_PATH),
        ):
            claim = unreleased_claim(hits, index)
            if claim is None or (best is not None and best.weight >= weight):
                continue
            platform, _term, acq = claim
            best = Signal(
                id="claims_unreleased_platform",
                weight=weight,
                category="platform",
                explanation=claim_explanation(index, platform, acq),
                evidence=(defang(ctx.target.host) if where == "hostname" else ctx.target.path,),
            )
    return [best] if best else []
