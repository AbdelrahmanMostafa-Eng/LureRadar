"""Lexical analysis: campaign keywords and intent terms in hostnames and paths.

Signal: ``keyword_intent_combo``. A campaign keyword (e.g. "gta 6") together
with an intent term (download, free, key, crack...) in the hostname, or, at
half weight, only in the URL path. Keywords alone never score.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import lru_cache

from lureradar.detectors.base import CampaignIndex, Context
from lureradar.models import Signal
from lureradar.scoring import weights
from lureradar.util.defang import defang

_SPLIT = re.compile(r"[^a-z0-9]+")
_SHORT = 3  # vocabulary words this short only count inside a fully-segmented token


@dataclass(frozen=True)
class TermHits:
    """What one campaign index found in a piece of text (hostname or path)."""

    keywords: tuple[str, ...] = ()
    intents: tuple[str, ...] = ()
    brands: tuple[str, ...] = ()  # compact brand tokens (names or aliases)
    words: tuple[str, ...] = ()  # every vocabulary word recognised
    unreleased: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def acquisition(self) -> tuple[str, ...]:
        return self.intents


def find_keywords(text: str, index: CampaignIndex) -> list[tuple[str, int, int]]:
    """Return ``(keyword, start, end)`` spans of campaign keywords in ``text``."""
    lowered = text.lower()
    spans: list[tuple[str, int, int]] = []
    for kp in index.keywords:
        for m in kp.regex.finditer(lowered):
            end = m.end()
            if kp.needs_right_boundary and end < len(lowered) and lowered[end].isalpha():
                # "gtavideos" is not "gta vi"; but "gtavipc" (followed by an intent) is
                rest = lowered[end:]
                if not any(rest.startswith(w) for w in index.vocabulary if len(w) > 1):
                    continue
            spans.append((kp.term, m.start(), end))
    # drop spans contained in a longer span
    spans.sort(key=lambda s: (s[1], -(s[2] - s[1])))
    kept: list[tuple[str, int, int]] = []
    for span in spans:
        if kept and span[1] < kept[-1][2]:
            continue
        kept.append(span)
    return kept


def segment(token: str, vocabulary: frozenset[str], max_word: int) -> tuple[list[str], int]:
    """Word-break ``token`` over ``vocabulary`` minimising unknown characters.

    Returns ``(words, unknown_chars)``. Ties prefer fewer, longer words.
    """
    n = len(token)
    if n == 0:
        return [], 0
    inf = (n + 1, n + 1)
    best: list[tuple[int, int]] = [inf] * (n + 1)
    back: list[tuple[int, str | None]] = [(0, None)] * (n + 1)
    best[0] = (0, 0)
    for i in range(1, n + 1):
        # unknown character
        cand = (best[i - 1][0] + 1, best[i - 1][1])
        if cand < best[i]:
            best[i], back[i] = cand, (i - 1, None)
        for j in range(max(0, i - max_word), i):
            piece = token[j:i]
            if piece in vocabulary:
                cand = (best[j][0], best[j][1] + 1)
                if cand < best[i]:
                    best[i], back[i] = cand, (j, piece)
    words: list[str] = []
    i = n
    while i > 0:
        j, found = back[i]
        if found is not None:
            words.append(found)
        i = j
    words.reverse()
    return words, best[n][0]


@lru_cache(maxsize=8192)
def _segment_cached(token: str, index: CampaignIndex) -> tuple[tuple[str, ...], int]:
    words, unknown = segment(token, index.vocabulary, index.max_word)
    return tuple(words), unknown


def recognised_words(text: str, index: CampaignIndex) -> list[str]:
    """Vocabulary words in ``text`` after removing keyword spans.

    Short words (<= 3 chars, e.g. "pc", "key", "ios") only count when their
    token segments completely, so "npc" or "studios" do not yield "pc"/"ios".
    """
    lowered = text.lower()
    spans = find_keywords(lowered, index)
    pieces: list[str] = []
    cursor = 0
    for _, start, end in spans:
        pieces.append(lowered[cursor:start])
        pieces.append(" ")
        cursor = end
    pieces.append(lowered[cursor:])
    remainder = "".join(pieces)
    found: list[str] = []
    for token in _SPLIT.split(remainder):
        if not token:
            continue
        if token in index.vocabulary:
            found.append(token)
            continue
        words, unknown = _segment_cached(token, index)
        for w in words:
            if len(w) > _SHORT or unknown == 0:
                found.append(w)
    return found


def analyse(text: str, index: CampaignIndex) -> TermHits:
    """Find keywords, intents, brand tokens and unreleased-platform terms."""
    if not text:
        return TermHits()
    keywords = tuple(dict.fromkeys(k for k, _, _ in find_keywords(text, index)))
    words = recognised_words(text, index)
    # multi-word terms ("epic games", "pc version") are matched on the compact text too
    compact_text = re.sub(r"[^a-z0-9]", "", text.lower())
    intents = [w for w in words if w in index.intents]
    intents += [i for i in index.intents if len(i) >= 8 and i in compact_text and i not in intents]
    brands = [w for w in words if w in index.brand_tokens]
    unreleased: dict[str, tuple[str, ...]] = {}
    for platform, terms in index.unreleased.items():
        hit = [t for t in words if t in terms]
        hit += [t for t in terms if len(t) >= 8 and t in compact_text and t not in hit]
        if hit:
            unreleased[platform] = tuple(dict.fromkeys(hit))
    return TermHits(
        keywords=keywords,
        intents=tuple(dict.fromkeys(intents)),
        brands=tuple(dict.fromkeys(brands)),
        words=tuple(words),
        unreleased=unreleased,
    )


def host_text(ctx: Context) -> str:
    """The attacker-controlled part of the hostname (subdomain + label).

    Empty for allowlisted outlets and for user-content platforms, whose
    hostnames are not attacker-chosen.
    """
    t = ctx.target
    if ctx.allow.outlet or ctx.allow.platform or t.is_ip:
        return ""
    owned = ".".join(p for p in (t.subdomain, t.domain_label) if p)
    if "xn--" in owned:
        # analyse what a human reads: the Unicode skeleton ("gtа6" -> "gta6")
        from lureradar.detectors.homoglyph import skeleton
        from lureradar.util.domains import to_unicode_host

        owned = "".join(c for c in skeleton(to_unicode_host(owned)) if c.isascii())
    return owned


def path_text(ctx: Context) -> str:
    from urllib.parse import unquote

    return unquote(ctx.target.path or "")


def host_hits(ctx: Context, index: CampaignIndex) -> TermHits:
    key = f"host:{index.id}"
    return ctx.memo(key, lambda: analyse(host_text(ctx), index))  # type: ignore[return-value]


def path_hits(ctx: Context, index: CampaignIndex) -> TermHits:
    key = f"path:{index.id}"
    return ctx.memo(key, lambda: analyse(path_text(ctx), index))  # type: ignore[return-value]


def _fmt(items: Iterable[str]) -> str:
    return ", ".join(f'"{i}"' for i in items)


def detect_keyword_intent_combo(ctx: Context) -> list[Signal]:
    best: Signal | None = None
    for index in ctx.indexes:
        for where, hits, weight in (
            ("hostname", host_hits(ctx, index), weights.KEYWORD_INTENT_COMBO_HOST),
            ("URL path", path_hits(ctx, index), weights.KEYWORD_INTENT_COMBO_PATH),
        ):
            if not (hits.keywords and hits.intents):
                continue
            if best is not None and best.weight >= weight:
                continue
            best = Signal(
                id="keyword_intent_combo",
                weight=weight,
                category="lexical",
                explanation=(
                    f"Keyword {_fmt(hits.keywords[:2])} + intent {_fmt(hits.intents[:4])} "
                    f"in the {where}"
                ),
                evidence=(defang(ctx.target.host) if where == "hostname" else ctx.target.path,),
            )
    return [best] if best else []
