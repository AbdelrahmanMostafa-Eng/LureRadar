"""Benchmark harness: run the engine over labelled corpora and compute metrics."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from bench.generators import Sample, lure_domains
from bench.text_generators import messages
from lureradar.enrich.types import Enrichment, RdapInfo
from lureradar.models import Tier, Verdict
from lureradar.scoring import calibration
from lureradar.scoring.engine import Engine

CORPORA = Path(__file__).parent / "corpora"
NOW = datetime(2026, 11, 21, 12, tzinfo=UTC)
TIERS = [t.value for t in Tier]


def read_list(name: str) -> list[str]:
    lines = (CORPORA / name).read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]


@dataclass
class Outcome:
    sample: Sample
    verdict: Verdict


@dataclass
class Metrics:
    name: str
    outcomes: list[Outcome] = field(default_factory=list)

    def at(self, tier: Tier) -> dict[str, float | int]:
        tp = sum(1 for o in self.outcomes if o.sample.label == "lure" and o.verdict.tier >= tier)
        fn = sum(1 for o in self.outcomes if o.sample.label == "lure" and o.verdict.tier < tier)
        fp = sum(1 for o in self.outcomes if o.sample.label == "benign" and o.verdict.tier >= tier)
        tn = sum(1 for o in self.outcomes if o.sample.label == "benign" and o.verdict.tier < tier)
        precision = tp / (tp + fp) if tp + fp else 1.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        fpr = fp / (fp + tn) if fp + tn else 0.0
        return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "precision": round(precision, 4),
                "recall": round(recall, 4), "f1": round(f1, 4), "fpr": round(fpr, 4)}  # fmt: skip

    def confusion(self) -> dict[str, dict[str, int]]:
        table: dict[str, dict[str, int]] = {
            "benign": dict.fromkeys(TIERS, 0),
            "lure": dict.fromkeys(TIERS, 0),
        }
        for o in self.outcomes:
            table[o.sample.label][o.verdict.tier.value] += 1
        return table

    def by_pattern(self) -> dict[str, dict[str, Any]]:
        groups: dict[str, list[Outcome]] = defaultdict(list)
        for o in self.outcomes:
            groups[o.sample.pattern].append(o)
        out = {}
        for pattern, items in sorted(groups.items()):
            tiers = Counter(o.verdict.tier.value for o in items)
            n = len(items)
            out[pattern] = {
                "n": n,
                "label": items[0].sample.label,
                "in_scope": items[0].sample.in_scope,
                "suspicious_plus": round(
                    sum(1 for o in items if o.verdict.tier >= Tier.SUSPICIOUS) / n, 4
                ),
                "likely_plus": round(sum(1 for o in items if o.verdict.tier >= Tier.LIKELY) / n, 4),
                "tiers": {t: tiers.get(t, 0) for t in TIERS},
                "example": items[0].sample.value,
            }
        return out


def _run(
    engine: Engine, samples: list[Sample], name: str, enrich: Enrichment | None = None
) -> Metrics:
    m = Metrics(name)
    for s in samples:
        v = engine.check(s.value, enricher=(lambda _t: enrich) if enrich else None)
        m.outcomes.append(Outcome(s, v))
    return m


def run(seed: int = 2026) -> dict[str, Any]:
    engine = Engine(pack_ids=["gta6"], now=NOW)
    raw_engine = Engine(pack_ids=["gta6"], now=NOW, allowlists=False)
    benign = [Sample(d, "benign", "benign_real_domain") for d in read_list("benign_domains.txt")]
    hard = [
        Sample(d, "benign", "benign_hard_negative") for d in read_list("benign_hard_negatives.txt")
    ]
    urls = [Sample(u, "benign", "benign_article_url") for u in read_list("benign_urls.txt")]
    lures = lure_domains(seed=seed)
    in_scope = [s for s in lures if s.in_scope]
    negatives = benign + hard + urls

    main = _run(engine, negatives + lures, "domains_offline")
    scoped = Metrics("domains_offline_in_scope", [o for o in main.outcomes if o.sample.in_scope])
    no_allow = _run(raw_engine, benign + hard + urls, "benign_without_allowlists")
    fresh = Enrichment(rdap=RdapInfo(registered=NOW - timedelta(days=1)))
    old = Enrichment(rdap=RdapInfo(registered=NOW - timedelta(days=3650)))
    live_lures = _run(engine, in_scope, "lures_newly_registered", fresh)
    live_benign = _run(raw_engine, benign, "benign_established_no_allowlist", old)
    text = _run(engine, messages(seed=seed), "text_messages")

    benign_scores = [
        o.verdict.score for o in no_allow.outcomes if o.sample.pattern == "benign_real_domain"
    ]
    lure_scores = [o.verdict.score for o in scoped.outcomes if o.sample.label == "lure"]
    likely, suspicious = Tier.LIKELY, Tier.SUSPICIOUS

    def benign_fpr(metrics: Metrics, pattern: str, tier: Tier) -> float:
        items = [o for o in metrics.outcomes if o.sample.pattern == pattern]
        return (
            round(sum(1 for o in items if o.verdict.tier >= tier) / len(items), 4) if items else 0.0
        )

    fp_examples = [
        {"value": o.sample.value, "tier": o.verdict.tier.value, "score": o.verdict.score,
         "signals": [s.id for s in o.verdict.signals if s.weight]}
        for o in no_allow.outcomes if o.verdict.tier >= suspicious
    ]  # fmt: skip
    return {
        "generated_with": {"seed": seed, "now": NOW.isoformat()},
        "corpus": {
            "benign_real_domains": len(benign),
            "benign_hard_negatives": len(hard),
            "benign_article_urls": len(urls),
            "synthetic_lures": len(lures),
            "synthetic_lures_in_scope": len(in_scope),
            "text_messages": len(text.outcomes),
        },
        "benign_fpr_likely": benign_fpr(main, "benign_real_domain", likely),
        "benign_fpr_suspicious": benign_fpr(main, "benign_real_domain", suspicious),
        "benign_fpr_likely_without_allowlists": benign_fpr(no_allow, "benign_real_domain", likely),
        "benign_fpr_suspicious_without_allowlists": benign_fpr(
            no_allow, "benign_real_domain", suspicious
        ),
        "hard_negative_fpr_likely": benign_fpr(main, "benign_hard_negative", likely),
        "hard_negative_fpr_suspicious": benign_fpr(main, "benign_hard_negative", suspicious),
        "article_url_fpr_suspicious": benign_fpr(main, "benign_article_url", suspicious),
        "offline": {"likely": main.at(likely), "suspicious": main.at(suspicious)},
        "offline_in_scope": {"likely": scoped.at(likely), "suspicious": scoped.at(suspicious)},
        "confusion_offline": main.confusion(),
        "patterns": main.by_pattern(),
        "newly_registered_lures": {
            "likely_plus": live_lures.at(likely)["recall"],
            "suspicious_plus": live_lures.at(suspicious)["recall"],
        },
        "established_benign_without_allowlists_fpr_likely": live_benign.at(likely)["fpr"],
        "text": {
            "likely": text.at(likely),
            "suspicious": text.at(suspicious),
            "confusion": text.confusion(),
        },
        "calibration": {
            "max_benign_score_without_allowlists": max(benign_scores, default=0),
            "lowest_zero_fpr_threshold": calibration.lowest_zero_fpr_threshold(benign_scores),
            "likely_threshold_margin": calibration.margin(benign_scores, 70),
            "benign_histogram": calibration.histogram(benign_scores),
            "lure_histogram": calibration.histogram(lure_scores),
            "sweep": [r.__dict__ for r in calibration.sweep(benign_scores, lure_scores)],
        },
        "benign_suspicious_examples_without_allowlists": fp_examples[:20],
    }
