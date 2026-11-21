"""Detector plumbing: the compiled campaign index and the detection context.

A detector is a pure function ``(Context) -> list[Signal]``. Detectors never do
I/O: everything they need (pack data, enrichment results, local feed snapshot)
is already in the :class:`Context`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property, lru_cache
from importlib import resources
from typing import TYPE_CHECKING

import yaml

from lureradar.models import ParsedTarget, Signal
from lureradar.packs.loader import base_allowlist
from lureradar.packs.schema import Pack

if TYPE_CHECKING:
    from lureradar.enrich.types import Enrichment
    from lureradar.pipeline.snapshot import FeedSnapshot

# Generic words that appear in lure hostnames. They let the segmenter split
# concatenated names like "freegta6pckeys" without inventing intents.
FILLER_WORDS: frozenset[str] = frozenset(
    """
    get got now official online game games play player players gaming gamer store shop
    gift gifts card cards login signin sign support help account accounts verify
    verification secure update updates app apps web site portal center centre hub zone
    world club pro best top new news info community trade offer offers deal deals promo
    reward rewards bonus event events edition ultimate deluxe premium full version real
    legit working latest here the my your for and to of in on is it vice city six vi
    grand theft auto 2025 2026 2027 x go fast instant direct unlimited cash gems coins
    buy sale cheap price prices pass access early pre order preorder win winner prize
    prizes daily today users user servers server mods mod menu tool tools tv net com org
    link links page pages day days pack packs bundle download downloads file files exe
    zip rar msi box live
    """.split()
)

_SEP = r"[\W_]*"


def compact(term: str) -> str:
    """Lowercase alphanumerics only: ``"Early-Access" -> "earlyaccess"``."""
    return re.sub(r"[^a-z0-9]", "", term.lower())


def _term_parts(term: str) -> list[str]:
    # split on separators and letter/digit transitions: "gta6" -> ["gta", "6"]
    parts: list[str] = []
    for chunk in re.split(r"[^a-z0-9]+", term.lower()):
        parts.extend(p for p in re.findall(r"[a-z]+|\d+", chunk) if p)
    return parts


@dataclass(frozen=True)
class KeywordPattern:
    term: str
    regex: re.Pattern[str]
    needs_right_boundary: bool


def _keyword_pattern(term: str) -> KeywordPattern:
    parts = _term_parts(term)
    body = _SEP.join(re.escape(p) for p in parts)
    last = parts[-1]
    # digit-ending keywords must not run into more digits ("gta6" != "gta60")
    tail = r"(?!\d)" if last.isdigit() else ""
    return KeywordPattern(
        term=term,
        regex=re.compile(body + tail, re.IGNORECASE),
        needs_right_boundary=last.isalpha(),
    )


@dataclass(frozen=True, eq=False)
class CampaignIndex:
    """A pack compiled into lookup structures for fast, repeated matching."""

    pack: Pack
    keywords: tuple[KeywordPattern, ...]
    intents: frozenset[str]  # compact forms
    unreleased: dict[str, frozenset[str]]  # platform -> compact terms
    platform_terms: frozenset[str]
    brand_tokens: dict[str, str]  # compact token -> brand name
    official_domains: frozenset[str]
    vocabulary: frozenset[str]

    @property
    def id(self) -> str:
        return self.pack.id

    @cached_property
    def acquisition(self) -> frozenset[str]:
        """Intents that promise to *get* something (not platform names)."""
        return self.intents - self.platform_terms

    @cached_property
    def max_word(self) -> int:
        return max((len(w) for w in self.vocabulary), default=1)

    @classmethod
    def build(cls, pack: Pack) -> CampaignIndex:
        intents = frozenset(compact(i) for i in pack.intents)
        unreleased: dict[str, frozenset[str]] = {}
        platform_terms: set[str] = set()
        if pack.facts:
            for name, platform in pack.facts.platforms.items():
                terms = frozenset(compact(t) for t in platform.terms)
                platform_terms |= terms
                if pack.facts.effective_status(name) == "unreleased":
                    unreleased[name] = terms
        brand_tokens: dict[str, str] = {}
        official: set[str] = set()
        for brand in pack.brands:
            brand_tokens[brand.name] = brand.name
            for alias in brand.aliases:
                brand_tokens.setdefault(compact(alias), brand.name)
            official.update(brand.official)
        vocab = (
            set(FILLER_WORDS)
            | intents
            | platform_terms
            | set(brand_tokens)
            | {compact(k) for k in pack.keywords}
        )
        return cls(
            pack=pack,
            keywords=tuple(_keyword_pattern(k) for k in pack.keywords),
            intents=intents,
            unreleased=unreleased,
            platform_terms=frozenset(platform_terms),
            brand_tokens=brand_tokens,
            official_domains=frozenset(official),
            vocabulary=frozenset(v for v in vocab if v),
        )


_INDEX_CACHE: dict[int, tuple[Pack, CampaignIndex]] = {}


def _index_for(pack: Pack) -> CampaignIndex:
    cached = _INDEX_CACHE.get(id(pack))
    if cached is not None and cached[0] is pack:
        return cached[1]
    index = CampaignIndex.build(pack)
    _INDEX_CACHE[id(pack)] = (pack, index)
    return index


def build_indexes(packs: Iterable[Pack]) -> tuple[CampaignIndex, ...]:
    return tuple(_index_for(p) for p in packs)


@dataclass(frozen=True)
class AllowState:
    """Allowlist status of a target's registrable domain."""

    outlet: bool = False
    platform: bool = False
    matched: str = ""
    reason: str = ""


@lru_cache(maxsize=1)
def _shared_lists() -> dict[str, frozenset[str]]:
    def _load(name: str, key: str) -> frozenset[str]:
        text = resources.files("lureradar.data").joinpath(name).read_text("utf-8")
        data = yaml.safe_load(text) or {}
        return frozenset(str(x).lower() for x in data.get(key, []))

    return {
        "abused_tlds": _load("abused_tlds.yaml", "tlds"),
        "shorteners": _load("shorteners.yaml", "domains"),
    }


def abused_tlds() -> frozenset[str]:
    return _shared_lists()["abused_tlds"]


def shorteners() -> frozenset[str]:
    return _shared_lists()["shorteners"]


def allow_state(target: ParsedTarget, indexes: Sequence[CampaignIndex]) -> AllowState:
    reg = target.registrable_domain
    if not reg or target.is_ip:
        return AllowState()
    base = base_allowlist()
    outlets = set(base.outlets)
    platforms = set(base.platforms)
    for idx in indexes:
        outlets.update(idx.pack.allowlist.outlets)
        outlets.update(idx.official_domains)
        outlets.update(idx.pack.release_storefronts)
        platforms.update(idx.pack.allowlist.platforms)
    if reg in outlets:
        return AllowState(outlet=True, matched=reg, reason="established legitimate outlet")
    if reg in platforms:
        return AllowState(platform=True, matched=reg, reason="user-content platform")
    return AllowState()


@dataclass
class Context:
    """Everything a detector may look at for one target."""

    target: ParsedTarget
    indexes: tuple[CampaignIndex, ...]
    now: datetime
    allow: AllowState = field(default_factory=AllowState)
    enrichment: Enrichment | None = None
    snapshot: FeedSnapshot | None = None
    _cache: dict[str, object] = field(default_factory=dict, repr=False)

    def memo(self, key: str, factory: Callable[[], object]) -> object:
        if key not in self._cache:
            self._cache[key] = factory()
        return self._cache[key]


Detector = Callable[[Context], list[Signal]]
