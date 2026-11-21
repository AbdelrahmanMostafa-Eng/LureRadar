"""``homoglyph_idn``: an internationalised domain whose characters imitate a
brand or campaign keyword (e.g. Cyrillic "о" in "rоckstar")."""

from __future__ import annotations

import unicodedata
from functools import lru_cache

from confusable_homoglyphs import confusables

from lureradar.detectors.base import Context, compact
from lureradar.detectors.brand import _targets
from lureradar.detectors.typosquat import typo_match
from lureradar.models import Signal
from lureradar.scoring import weights
from lureradar.util.defang import defang

# Latin letters that do not decompose under NFKD but are classic look-alikes.
_EXTRA = {
    "ł": "l",
    "ɡ": "g",
    "ı": "i",
    "ȷ": "j",
    "ø": "o",
    "đ": "d",
    "ħ": "h",
    "ŀ": "l",
    "ƚ": "l",
    "ɑ": "a",
    "ʀ": "r",
    "ʏ": "y",
    "ꜱ": "s",
    "ᴏ": "o",
    "ᴄ": "c",
    "ᴠ": "v",
}


@lru_cache(maxsize=4096)
def _skeleton_char(ch: str) -> str:
    if ch.isascii():
        return ch.lower()
    if ch in _EXTRA:
        return _EXTRA[ch]
    norm = unicodedata.normalize("NFKC", ch)
    if norm.isascii() and norm:
        return norm.lower()
    decomposed = "".join(
        c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c)
    )
    if decomposed.isascii() and decomposed:
        return decomposed.lower()
    found = confusables.is_confusable(ch, preferred_aliases=["latin"], greedy=True)
    if found:
        for glyph in found[0]["homoglyphs"]:
            c = glyph["c"]
            if c.isascii() and c.isalnum():
                return str(c).lower()
    return ch


def skeleton(text: str) -> str:
    """Map look-alike characters to their ASCII counterparts (UTS #39 style)."""
    return "".join(_skeleton_char(c) for c in text)


def scripts(text: str) -> set[str]:
    out: set[str] = set()
    for ch in text:
        if ch.isalpha():
            name = unicodedata.name(ch, "")
            out.add(name.split(" ", 1)[0] if name else "UNKNOWN")
    return out


def detect_homoglyph_idn(ctx: Context) -> list[Signal]:
    t = ctx.target
    if ctx.allow.outlet or ctx.allow.platform or t.is_ip:
        return []
    uni = t.unicode_host
    owned_unicode = uni[: -len(t.suffix) - 1] if t.suffix and uni.endswith(t.suffix) else uni
    if owned_unicode.isascii():
        return []
    label_unicode = owned_unicode.rsplit(".", 1)[-1]
    skel = compact("".join(c for c in skeleton(owned_unicode) if c.isascii()))
    label_skel = compact("".join(c for c in skeleton(label_unicode) if c.isascii()))
    used = sorted(scripts(owned_unicode) - {"LATIN", "DIGIT"})
    for index in ctx.indexes:
        candidates: dict[str, str] = {}
        for brand, targets in _targets(index).items():
            for target in targets:
                candidates.setdefault(target, brand)
        for kp in index.keywords:
            candidates.setdefault(compact(kp.term), f'campaign keyword "{kp.term}"')
        for target, what in candidates.items():
            hit = label_skel == target or (len(target) >= 4 and target in skel)
            if not hit and typo_match(label_skel, target) is None:
                continue
            return [
                Signal(
                    id="homoglyph_idn",
                    weight=weights.HOMOGLYPH_IDN,
                    category="brand",
                    explanation=(
                        f'Internationalised domain "{defang(uni)}" reads as "{skel}", '
                        f"imitating {what}"
                        + (f" with {', '.join(used).title()} characters" if used else "")
                    ),
                    evidence=(defang(t.host), defang(uni)),
                )
            ]
    return []
