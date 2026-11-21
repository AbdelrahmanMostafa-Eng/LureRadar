"""Calibration helpers used by the benchmark (``make bench``).

Weights live in ``weights.py`` and are frozen; these functions only measure
how well the frozen weights separate benign from lure samples.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class SweepRow:
    threshold: int
    fpr: float
    recall: float
    false_positives: int
    true_positives: int


def histogram(scores: Iterable[int], bucket: int = 10) -> dict[str, int]:
    counts: Counter[int] = Counter(min(s // bucket, 100 // bucket - 1) for s in scores)
    return {
        f"{b * bucket}-{b * bucket + bucket - 1}": counts.get(b, 0) for b in range(100 // bucket)
    }


def sweep(
    benign: Sequence[int], lure: Sequence[int], thresholds: Iterable[int] = range(20, 101, 5)
) -> list[SweepRow]:
    rows = []
    for t in thresholds:
        fp = sum(1 for s in benign if s >= t)
        tp = sum(1 for s in lure if s >= t)
        rows.append(
            SweepRow(
                threshold=t,
                fpr=fp / len(benign) if benign else 0.0,
                recall=tp / len(lure) if lure else 0.0,
                false_positives=fp,
                true_positives=tp,
            )
        )
    return rows


def lowest_zero_fpr_threshold(benign: Sequence[int]) -> int:
    """Smallest integer threshold at which no benign sample is flagged."""
    return (max(benign) + 1) if benign else 0


def margin(benign: Sequence[int], threshold: int) -> int:
    """Points between the highest benign score and ``threshold`` (negative = overlap)."""
    return threshold - max(benign, default=0)
