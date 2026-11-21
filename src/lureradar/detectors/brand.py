"""``brand_impersonation``: typosquat, combosquat or exact brand use off-domain.

Brands are *names* from the pack (``brands.yaml``). Official domains are
always legitimate. Matching never looks at logos or page design.
"""

from __future__ import annotations

from dataclasses import dataclass

from lureradar.detectors.base import CampaignIndex, Context, compact
from lureradar.detectors.lexical import _segment_cached
from lureradar.detectors.typosquat import typo_match
from lureradar.models import Signal
from lureradar.scoring import weights
from lureradar.util.defang import defang
from lureradar.util.domains import split_host, tokenize

_SUBSTRING_MIN = 7  # brand tokens this long also match inside concatenated words


@dataclass(frozen=True)
class BrandFinding:
    brand: str
    kind: str  # typosquat | exact | combosquat
    detail: str
    rank: int  # lower is stronger


def _targets(index: CampaignIndex) -> dict[str, dict[str, str]]:
    """brand name -> {compact target token -> human label}."""
    out: dict[str, dict[str, str]] = {}
    for brand in index.pack.brands:
        targets = {brand.name: brand.label}
        for alias in brand.aliases:
            targets.setdefault(compact(alias), brand.label)
        for dom in brand.official:
            label = split_host(dom)[1]
            if len(label) >= 4:
                targets.setdefault(compact(label), f"{brand.label}, {dom}")
        out[brand.name] = targets
    return out


def find_brand_abuse(ctx: Context, index: CampaignIndex) -> list[BrandFinding]:
    t = ctx.target
    if ctx.allow.outlet or ctx.allow.platform or t.is_ip or not t.domain_label:
        return []
    if t.registrable_domain in index.official_domains:
        return []
    owned = ".".join(p for p in (t.subdomain, t.domain_label) if p)
    label = t.domain_label
    if "xn--" in owned:
        # analyse what the user *sees*: the Unicode skeleton, not punycode noise
        from lureradar.detectors.homoglyph import skeleton
        from lureradar.util.domains import to_unicode_host

        owned = "".join(c for c in skeleton(to_unicode_host(owned)) if c.isascii())
        label = owned.rsplit(".", 1)[-1]
    owned_compact = compact(owned)
    label_compact = compact(label)
    tokens = [tok for tok in tokenize(owned) if len(tok) >= 4]
    # brand words found in hostname tokens that segment *completely* into known
    # words ("freesteamkeys" -> free+steam+keys), so "steamboat" does not count
    segmented: set[str] = set()
    for tok in tokenize(owned):
        words, unknown = _segment_cached(tok, index)
        if unknown == 0:
            segmented.update(words)
    findings: list[BrandFinding] = []
    idn = "xn--" in ".".join(p for p in (t.subdomain, t.domain_label) if p)
    for brand, targets in _targets(index).items():
        # 1. exact brand/official label on a different domain (TLD swap, hyphens, IDN)
        if label_compact in targets:
            desc = targets[label_compact]
            detail = (
                f'"{label_compact}" spelled with look-alike Unicode ({desc})'
                if idn
                else f'brand label "{label_compact}" ({desc}) on a non-official domain'
            )
            findings.append(
                BrandFinding(brand, "confusable" if idn else "exact", detail, 0 if idn else 1)
            )
            continue
        # 2. typosquat of a brand token or official label
        typo: BrandFinding | None = None
        for target, desc in targets.items():
            for cand in sorted({label, *tokens}):
                if cand in targets:
                    continue  # an exact brand token is a combosquat, not a typo
                m = typo_match(cand, target)
                if m and typo is None:
                    how = "look-alike characters" if m.method == "lookalike" else "typo"
                    typo = BrandFinding(
                        brand,
                        "typosquat",
                        f'"{cand}" imitates "{target}" ({desc}; {how}, distance {m.distance})',
                        0,
                    )
        if typo:
            findings.append(typo)
            continue
        # 3. combosquat: brand token combined with other words
        for target, desc in targets.items():
            if target in segmented or (len(target) >= _SUBSTRING_MIN and target in owned_compact):
                findings.append(
                    BrandFinding(brand, "combosquat", f'"{target}" ({desc}) plus other words', 2)
                )
                break
    return sorted(findings, key=lambda f: (f.rank, f.brand))


def detect_brand_impersonation(ctx: Context) -> list[Signal]:
    best: list[BrandFinding] = []
    for index in ctx.indexes:
        best.extend(find_brand_abuse(ctx, index))
    if not best:
        return []
    best.sort(key=lambda f: (f.rank, f.brand))
    top = best[0]
    details = list(dict.fromkeys(f.detail for f in best))[:3]
    return [
        Signal(
            id="brand_impersonation",
            weight=weights.BRAND_IMPERSONATION,
            category="brand",
            explanation=f"{top.kind.capitalize()}: {details[0]}",
            evidence=(defang(ctx.target.host), *details[1:]),
        )
    ]
