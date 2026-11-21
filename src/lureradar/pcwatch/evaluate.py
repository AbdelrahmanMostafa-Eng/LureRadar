"""Explicit, testable rules that turn official statements into findings.

A statement counts only if ALL hold:
1. its URL is on one of the source's official domains (official-domain match);
2. it names the game (``game_terms``);
3. a platform term (PC, Windows, Steam, Epic...) appears in the title, or
   within ``proximity_chars`` of the game name.
Classification: "available now / out now" near the platform -> RELEASED; a
date or window near the platform -> ANNOUNCED_DATED; otherwise
ANNOUNCED_UNDATED. Negations ("no plans for PC") mark the finding negated.
Every finding still needs a maintainer to act on it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from lureradar.pcwatch.config import PcWatchConfig, WatchSource
from lureradar.pcwatch.status import Finding, Status
from lureradar.util.domains import parse_target

MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
DATE_RE = re.compile(
    rf"\b(?:(?:{MONTHS})\s+\d{{1,2}},?\s+\d{{4}}|\d{{1,2}}\s+(?:{MONTHS})\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}}"
    rf"|q[1-4]\s+\d{{4}}|(?:first|second|third|fourth)\s+quarter\s+(?:of\s+)?\d{{4}}"
    rf"|(?:early|spring|summer|fall|autumn|winter|late|mid)\s+\d{{4}}|(?:{MONTHS})\s+\d{{4}})\b",
    re.IGNORECASE,
)
RELEASED_RE = re.compile(
    r"\b(?:available\s+now|out\s+now|now\s+available|available\s+today|play\s+(?:it\s+)?now|"
    r"launches\s+today|is\s+here)\b",
    re.IGNORECASE,
)
NEGATION_RE = re.compile(
    r"\b(?:no\s+plans?|not\s+(?:coming|planned|available|announced)|no\s+pc|isn'?t\s+coming|"
    r"won'?t\s+(?:be|come))\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Statement:
    source: str
    title: str
    url: str
    text: str = ""
    published: date | None = None


def _official(url: str, source: WatchSource) -> bool:
    try:
        host = parse_target(url).host
    except Exception:
        return False
    return any(host == d or host.endswith("." + d) for d in source.official_domains)


def _terms_re(terms: list[str]) -> re.Pattern[str]:
    alt = "|".join(sorted((re.escape(t) for t in terms), key=len, reverse=True))
    return re.compile(rf"(?<![\w-])(?:{alt})(?![\w-])", re.IGNORECASE)


def snippet(text: str, start: int, end: int, words: int = 15) -> str:
    left = text[:start].split()[-5:]
    mid = text[start:end].split()
    right = text[end:].split()[: max(0, words - len(left) - len(mid))]
    return " ".join([*left, *mid, *right][:words])


def evaluate(statement: Statement, source: WatchSource, config: PcWatchConfig) -> Finding | None:
    if not _official(statement.url, source):
        return None
    full = f"{statement.title}. {statement.text}"
    game_re = _terms_re(config.game_terms)
    plat_re = _terms_re(config.platform_terms)
    games = list(game_re.finditer(full))
    if not games:
        return None
    title_platform = plat_re.search(statement.title)
    hit = None
    if title_platform and game_re.search(statement.title):
        hit = title_platform
    else:
        for p in plat_re.finditer(full):
            if any(abs(p.start() - g.start()) <= config.proximity_chars for g in games):
                hit = p
                break
    if hit is None:
        return None
    lo = max(0, hit.start() - config.proximity_chars)
    window = full[lo : hit.end() + config.proximity_chars]
    if RELEASED_RE.search(window):
        status = Status.RELEASED
    elif DATE_RE.search(window):
        status = Status.ANNOUNCED_DATED
    else:
        status = Status.ANNOUNCED_UNDATED
    return Finding(
        source=source.id,
        status=status,
        url=statement.url,
        title=statement.title[:200],
        snippet=snippet(full, hit.start(), hit.end()),
        negated=bool(NEGATION_RE.search(window)),
    )
