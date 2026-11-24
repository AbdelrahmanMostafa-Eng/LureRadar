"""``lureradar scan``: collect -> normalise -> dedupe -> prefilter -> enrich ->
score -> tier -> state -> retention -> publish.

Every stage is idempotent (state is keyed by registrable domain), resumable
(re-running simply re-scores) and time-boxed so a run fits GitHub Actions
limits. Stages log one structured line each.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from lureradar.config import Settings
from lureradar.detectors.base import allow_state
from lureradar.enrich.live import FixtureEnricher, LiveEnricher
from lureradar.enrich.types import Enrichment, ReputationHit
from lureradar.errors import LureRadarError
from lureradar.export.signing import SigningKey
from lureradar.models import Candidate, Signal, Tier
from lureradar.pipeline.dedupe import Merged, merge
from lureradar.pipeline.publish import publish
from lureradar.pipeline.state import State
from lureradar.scoring import tiers
from lureradar.scoring.engine import Engine
from lureradar.sources import build_sources
from lureradar.util.domains import parse_target
from lureradar.util.logging import get_logger
from lureradar.util.time import isoformat, utcnow

log = get_logger("pipeline")
RELEVANT_CATEGORIES = frozenset({"lexical", "platform", "brand"})


@dataclass
class ScanConfig:
    """``fixtures`` is a root holding ``sources/`` and ``enrich/`` recordings."""

    state_path: Path
    out_dir: Path | None = None
    fixtures: Path | None = None
    enrich: bool = True
    sources: list[str] | None = None
    since_hours: int = 72
    budget_s: float = 1200.0
    max_enrich: int = 300
    concurrency: int = 8
    signer: SigningKey | None = None
    fpr: float | None = None
    now: datetime | None = None
    packs: list[str] | None = None
    reports_dir: Path | None = None
    stats: dict[str, Any] = field(default_factory=dict)


def _relevant(signals: list[Signal], merged: Merged) -> bool:
    if "community" in merged.sources:
        return True
    return any(s.weight > 0 and s.category in RELEVANT_CATEGORIES for s in signals)


def collect(
    cfg: ScanConfig, settings: Settings, since: datetime
) -> tuple[list[Candidate], dict[str, Any]]:
    report: dict[str, Any] = {}
    candidates: list[Candidate] = []
    fixtures = cfg.fixtures / "sources" if cfg.fixtures is not None else None
    reports = cfg.reports_dir or (fixtures / "reports" if fixtures is not None else None)
    for src in build_sources(settings, fixtures=fixtures, reports_dir=reports):
        name = src.info.name
        if cfg.sources and name not in cfg.sources:
            continue
        if src.info.kind == "reputation" or (name == "certstream" and cfg.fixtures is None):
            continue
        start = time.monotonic()
        try:
            got = list(src.fetch(since))
            report[name] = {"status": "ok", "candidates": len(got)}
            if failed := int(getattr(src, "failed_queries", 0) or 0):
                report[name] |= {"status": "partial", "failed_queries": failed}
            candidates.extend(got)
        except LureRadarError as exc:
            report[name] = {"status": "failed", "error": str(exc)[:200]}
        except Exception as exc:
            report[name] = {"status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
        finally:
            src.close()
        report[name]["seconds"] = round(time.monotonic() - start, 2)
        log.info("collect", extra={"source": name, **report[name]})
    return candidates, report


async def _enrich_all(
    items: list[Merged],
    enricher: Callable[..., Any] | None,
    concurrency: int,
    deadline: float,
) -> dict[str, Enrichment]:
    out: dict[str, Enrichment] = {}
    if enricher is None:
        return out
    sem = asyncio.Semaphore(concurrency)

    async def one(m: Merged) -> None:
        if time.monotonic() > deadline:
            return
        target = parse_target(m.url or m.domain)
        async with sem:
            try:
                if isinstance(enricher, LiveEnricher):
                    out[m.domain] = await asyncio.wait_for(
                        enricher.enrich_async(target), max(1.0, deadline - time.monotonic())
                    )
                else:
                    out[m.domain] = enricher(target)
            except (TimeoutError, LureRadarError) as exc:
                out[m.domain] = Enrichment(errors=[f"enrich: {exc}"])

    await asyncio.gather(*(one(m) for m in items))
    return out


def _rescore_existing(
    engine: Engine, state: State, seen: set[str], now: datetime
) -> dict[str, int]:
    """Re-apply allowlist and offline rules to indicators not sighted this run.

    This is what makes an allowlist PR (or a facts.yaml change such as a PC
    announcement) take effect within one pipeline run.
    """
    removed = rescored = 0
    for ind in state.all("active"):
        if ind.domain in seen:
            continue
        target = parse_target(ind.url or ind.domain)
        allow = allow_state(target, engine.indexes)
        if allow.outlet or allow.platform:
            state.delete(ind.domain)
            removed += 1
            continue
        offline = engine.assess(target)
        live = [s for s in ind.signals if s.live]
        signals = sorted([*offline.signals, *live], key=lambda s: (-s.weight, s.id))
        score = tiers.total(signals)
        tier, _ = tiers.decide(score, signals)
        if tier < Tier.SUSPICIOUS:
            state.delete(ind.domain)
            removed += 1
            continue
        state.upsert(
            domain=ind.domain, url=ind.url, seen=ind.last_seen, now=now, score=score, tier=tier,
            sources=ind.sources, packs=ind.packs, signals=signals,
        )  # fmt: skip
        rescored += 1
    return {"removed": removed, "rescored": rescored}


def run_scan(cfg: ScanConfig) -> dict[str, Any]:
    started = utcnow() if cfg.now is None else cfg.now
    t0 = time.monotonic()
    deadline = t0 + cfg.budget_s
    settings = Settings.from_env()
    engine = Engine(pack_ids=cfg.packs, now=started)
    state = State(cfg.state_path)
    since = started - timedelta(hours=cfg.since_hours)
    report: dict[str, Any] = {"started_at": isoformat(started)}
    try:
        candidates, report["sources"] = collect(cfg, settings, since)
        merged, invalid = merge(candidates, started)
        report["collected"] = len(candidates)
        report["invalid"] = invalid
        report["unique_domains"] = len(merged)

        # cheap lexical prefilter: drops non-campaign noise before any network work
        kept: list[Merged] = []
        for m in merged.values():
            verdict = engine.assess(parse_target(m.url or m.domain))
            if not verdict.allowlisted and _relevant(verdict.signals, m):
                kept.append(m)
        dropped = len(merged) - len(kept)
        report["prefilter_dropped"] = dropped
        report["prefilter_drop_ratio"] = round(dropped / len(merged), 3) if merged else 0.0
        log.info("prefilter", extra={"kept": len(kept), "dropped": dropped})

        enricher: Callable[..., Any] | None = None
        if cfg.fixtures is not None:
            enricher = FixtureEnricher(cfg.fixtures / "enrich")
        elif cfg.enrich:
            enricher = LiveEnricher.from_env()
        to_enrich = kept[: cfg.max_enrich]
        enrichments = asyncio.run(_enrich_all(to_enrich, enricher, cfg.concurrency, deadline))
        report["enriched"] = len(enrichments)

        seen: set[str] = set()
        counts = {t.value: 0 for t in Tier}
        for m in kept:
            e = enrichments.get(m.domain)
            if m.reputation_sources:
                e = e or Enrichment()
                for src in sorted(m.reputation_sources):
                    e.reputation.append(ReputationHit(source=src, detail="listed in source feed"))
            verdict = engine.assess(parse_target(m.url or m.domain), e)
            counts[verdict.tier.value] += 1
            if verdict.tier < Tier.SUSPICIOUS:
                state.delete(m.domain)
                continue
            seen.add(m.domain)
            state.upsert(
                domain=m.domain, url=m.url, seen=m.first_seen, now=started, score=verdict.score,
                tier=verdict.tier, sources=sorted(m.sources), packs=verdict.packs,
                signals=verdict.signals,
            )  # fmt: skip
        report["tiers"] = counts
        report["existing"] = _rescore_existing(engine, state, seen, started)
        stale, purged = state.apply_retention(started)
        report["retention"] = {"newly_stale": stale, "purged": purged}
        report["seconds"] = round(time.monotonic() - t0, 2)
        report["timed_out"] = time.monotonic() > deadline
        finished = utcnow() if cfg.now is None else cfg.now
        report["finished_at"] = isoformat(finished)
        state.record_run(started, finished, report)
        if cfg.out_dir is not None:
            history = [
                {"at": r.get("started_at"), "tiers": r.get("tiers", {})} for r in state.last_runs()
            ]
            publish(
                state.all(), cfg.out_dir, started, signer=cfg.signer, run=report,
                history=history, fpr=cfg.fpr,
            )  # fmt: skip
        log.info("scan complete", extra={"seconds": report["seconds"]})
        return report
    finally:
        state.close()
