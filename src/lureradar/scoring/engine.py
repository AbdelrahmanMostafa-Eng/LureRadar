"""The scoring engine: run detectors, sum signals, decide the tier, explain.

>>> from lureradar.scoring.engine import Engine
>>> v = Engine().check("hxxps://rockstar-gta6-pc-download[.]test/free-key")
>>> v.tier.value
'likely'
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

from lureradar.detectors.age import (
    detect_domain_age,
    detect_established_domain,
    detect_fresh_cert,
)
from lureradar.detectors.allowlist import detect_allowlist
from lureradar.detectors.base import CampaignIndex, Context, Detector, allow_state, build_indexes
from lureradar.detectors.brand import detect_brand_impersonation
from lureradar.detectors.content import detect_content_lure_patterns
from lureradar.detectors.homoglyph import detect_homoglyph_idn
from lureradar.detectors.hosting import detect_hosting_reputation
from lureradar.detectors.intent import detect_claims_unreleased_platform
from lureradar.detectors.lexical import detect_keyword_intent_combo
from lureradar.detectors.redirects import detect_redirect_chain
from lureradar.detectors.reputation import detect_external_reputation, detect_feed_listed
from lureradar.detectors.tld import detect_abused_tld
from lureradar.enrich.types import Enrichment
from lureradar.errors import LureRadarError
from lureradar.models import ParsedTarget, Signal, TargetKind, Tier, Verdict
from lureradar.packs.loader import load_packs
from lureradar.packs.schema import Pack
from lureradar.pipeline.snapshot import FeedSnapshot
from lureradar.scoring import tiers, weights
from lureradar.scoring.explain import next_steps
from lureradar.textlure.analyzer import analyze_text
from lureradar.util.defang import defang, defang_text
from lureradar.util.domains import parse_target
from lureradar.util.time import utcnow

OFFLINE_DETECTORS: tuple[Detector, ...] = (
    detect_allowlist,
    detect_keyword_intent_combo,
    detect_claims_unreleased_platform,
    detect_brand_impersonation,
    detect_homoglyph_idn,
    detect_abused_tld,
    detect_feed_listed,
)

LIVE_DETECTORS: tuple[Detector, ...] = (
    detect_domain_age,
    detect_fresh_cert,
    detect_hosting_reputation,
    detect_content_lure_patterns,
    detect_redirect_chain,
    detect_external_reputation,
)

Enricher = Callable[[ParsedTarget], Enrichment]


def run_detectors(ctx: Context) -> list[Signal]:
    signals: list[Signal] = []
    for detector in OFFLINE_DETECTORS:
        signals.extend(detector(ctx))
    if ctx.enrichment is not None:
        for detector in LIVE_DETECTORS:
            signals.extend(detector(ctx))
        signals.extend(detect_established_domain(ctx, signals))
    return signals


def _facts_note(signals: list[Signal], indexes: Sequence[CampaignIndex]) -> str | None:
    if not any(s.id in ("claims_unreleased_platform", "text_unreleased_platform") for s in signals):
        return None
    for idx in indexes:
        facts = idx.pack.facts
        if facts is None:
            continue
        fact = facts.fact("pc_release")
        if fact is not None:
            return f"Fact check: {fact.claim.strip()} (packs/{idx.id}/facts.yaml)"
        return f"Fact check: see packs/{idx.id}/facts.yaml (as of {facts.as_of.isoformat()})"
    return None


class Engine:
    """Stateless scorer bound to a set of campaign packs and an optional snapshot."""

    def __init__(
        self,
        packs: Sequence[Pack] | None = None,
        *,
        pack_ids: Sequence[str] | None = None,
        snapshot: FeedSnapshot | None = None,
        now: datetime | None = None,
    ) -> None:
        loaded = list(packs) if packs is not None else load_packs(pack_ids)
        self.packs = loaded
        self.indexes: tuple[CampaignIndex, ...] = build_indexes(loaded)
        self.snapshot = snapshot
        self._now = now

    @property
    def now(self) -> datetime:
        return self._now or utcnow()

    # ------------------------------------------------------------------ targets
    def assess(self, target: ParsedTarget, enrichment: Enrichment | None = None) -> Verdict:
        """Score a parsed URL/domain target."""
        if target.kind is TargetKind.TEXT:
            raise ValueError("use check()/assess_text() for text targets")
        allow = allow_state(target, self.indexes)
        ctx = Context(
            target=target,
            indexes=self.indexes,
            now=self.now,
            allow=allow,
            enrichment=enrichment,
            snapshot=self.snapshot,
        )
        signals = run_detectors(ctx)
        score = 0 if allow.outlet else tiers.total(signals)
        floor = None
        if self.snapshot is not None and not allow.outlet:
            entry = self.snapshot.lookup(target.host) or self.snapshot.lookup(
                target.registrable_domain
            )
            floor = entry.tier if entry else None
        tier, corroborated = tiers.decide(
            score, signals, outlet=allow.outlet, platform=allow.platform, floor=floor
        )
        display = target.url if target.kind is TargetKind.URL and target.url else target.host
        verdict = Verdict(
            target=defang(display or target.raw),
            kind=target.kind,
            host=defang(target.host) if target.host else None,
            registrable_domain=defang(target.registrable_domain)
            if target.registrable_domain
            else None,
            score=score,
            tier=tier,
            signals=sorted(signals, key=lambda s: (-s.weight, s.id)),
            corroborated=corroborated,
            allowlisted=allow.outlet,
            mode="live" if enrichment is not None else "offline",
            packs=[i.id for i in self.indexes],
            generated_at=self.now,
        )
        verdict.next_steps = next_steps(verdict, _facts_note(signals, self.indexes))
        return verdict

    def assess_text(self, text: str, enricher: Enricher | None = None) -> Verdict:
        """Score a message and every URL inside it; the overall tier is the max."""
        analysis = analyze_text(text, self.indexes)
        url_verdicts: list[Verdict] = []
        for url in analysis.urls[:10]:
            try:
                target = parse_target(url)
            except LureRadarError:
                continue
            if target.kind is TargetKind.TEXT:
                continue
            url_verdicts.append(self.assess(target, enricher(target) if enricher else None))
        risky = [
            u
            for u in url_verdicts
            if u.score >= weights.TEXT_RISKY_LINK_MIN_SCORE and not u.allowlisted
        ]
        if risky:
            worst = max(risky, key=lambda u: u.score)
            analysis.signals.append(
                Signal(
                    id="text_risky_link",
                    weight=weights.TEXT_RISKY_LINK,
                    category="text",
                    explanation=(
                        f"Links to {worst.host or worst.target} which shows lure signals "
                        f"(score {worst.score})"
                    ),
                    evidence=tuple(u.target for u in risky[:3]),
                )
            )
        text_score = tiers.total(analysis.signals)
        text_tier = tiers.tier_for_score(text_score)
        best_url = max(url_verdicts, key=lambda v: (v.tier.rank, v.score), default=None)
        score, tier = text_score, text_tier
        if best_url is not None and (best_url.tier.rank, best_url.score) > (tier.rank, score):
            score, tier = best_url.score, best_url.tier
        snippet = " ".join(text.split())
        verdict = Verdict(
            target=defang_text(snippet[:200] + ("..." if len(snippet) > 200 else "")),
            kind=TargetKind.TEXT,
            score=score,
            tier=tier,
            signals=sorted(analysis.signals, key=lambda s: (-s.weight, s.id)),
            corroborated=any(v.corroborated for v in url_verdicts),
            mode="live" if enricher is not None else "offline",
            packs=[i.id for i in self.indexes],
            urls=url_verdicts,
            generated_at=self.now,
        )
        verdict.next_steps = next_steps(verdict, _facts_note(analysis.signals, self.indexes))
        return verdict

    def check(self, raw: str, enricher: Enricher | None = None) -> Verdict:
        """Parse and score anything: URL, domain (defanged or not) or free text."""
        target = parse_target(raw)
        if target.kind is TargetKind.TEXT:
            return self.assess_text(raw, enricher)
        return self.assess(target, enricher(target) if enricher else None)


def quick_check(raw: str) -> Verdict:
    """Convenience wrapper for the Python API: offline check with all packs."""
    return Engine().check(raw)


__all__ = ["LIVE_DETECTORS", "OFFLINE_DETECTORS", "Engine", "Tier", "quick_check", "run_detectors"]
