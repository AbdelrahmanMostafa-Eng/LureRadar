"""Typosquat matching: edit distance plus ASCII look-alike normalisation.

Thresholds scale with target length so short brands ("steam") are only matched
through look-alike substitutions ("5team", "stearn"), never plain edits that
would also match ordinary words ("stream", "steak").
"""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz.distance import OSA

# Multi-character look-alikes first.
_LOOKALIKES: tuple[tuple[str, str], ...] = (
    ("rn", "m"),
    ("vv", "w"),
    ("cl", "d"),
    ("0", "o"),
    ("1", "l"),
    ("3", "e"),
    ("4", "a"),
    ("5", "s"),
    ("7", "t"),
    ("8", "b"),
    ("9", "g"),
    ("$", "s"),
    ("@", "a"),
)


def deconfuse_ascii(token: str) -> str:
    out = token.lower()
    for src, dst in _LOOKALIKES:
        out = out.replace(src, dst)
    return out


def max_distance(target: str) -> int:
    """Allowed OSA distance for a target of this length (0 = look-alike only)."""
    n = len(target)
    if n >= 10:
        return 2
    if n >= 7:
        return 1
    return 0


@dataclass(frozen=True)
class TypoMatch:
    candidate: str
    target: str
    distance: int
    method: str  # "edit" or "lookalike"


def typo_match(candidate: str, target: str) -> TypoMatch | None:
    """Return a match if ``candidate`` is a typo/look-alike of ``target`` (not equal)."""
    cand = candidate.lower()
    if cand == target or len(target) < 4:
        return None
    deconf = deconfuse_ascii(cand)
    # look-alike pairs like "rn"->"m" change length by one per pair
    if abs(len(cand) - len(target)) > 2 and len(deconf) != len(target):
        return None
    if deconf == target:
        return TypoMatch(candidate, target, OSA.distance(cand, target), "lookalike")
    limit = max_distance(target)
    if limit == 0:
        return None
    # avoid matching very short candidates against long targets and vice versa
    if len(cand) < len(target) - limit or len(cand) > len(target) + limit:
        return None
    dist = OSA.distance(deconf, target, score_cutoff=limit)
    if dist <= limit:
        # require the first character to match: most real typosquats keep it,
        # and it removes a large class of accidental near-words
        if deconf[:1] != target[:1]:
            return None
        return TypoMatch(candidate, target, dist, "edit")
    return None
