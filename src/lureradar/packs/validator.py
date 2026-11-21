"""``lureradar pack validate``: schema errors plus quality lints."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from lureradar.errors import PackError
from lureradar.packs.loader import load_pack
from lureradar.packs.schema import Pack
from lureradar.util.time import utcnow

STALE_FACT_DAYS = 120


@dataclass
class ValidationReport:
    path: Path
    pack: Pack | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def lint_pack(pack: Pack, today: date | None = None) -> list[str]:
    """Non-fatal quality checks. Returned strings are warnings."""
    today = today or utcnow().date()
    warnings: list[str] = []
    outlets = set(pack.allowlist.outlets)
    for brand in pack.brands:
        for dom in brand.official:
            if dom in pack.allowlist.platforms:
                warnings.append(
                    f"brand {brand.name}: official domain {dom} is listed as a platform"
                )
        if brand.name in pack.keywords:
            warnings.append(f"brand {brand.name} is also a keyword; brands should be separate")
    overlap = set(pack.keywords) & set(pack.intents)
    if overlap:
        warnings.append(f"terms used as both keyword and intent: {sorted(overlap)}")
    if pack.facts is None:
        warnings.append("no facts.yaml: claims_unreleased_platform will never fire")
    else:
        if (today - pack.facts.as_of).days > STALE_FACT_DAYS:
            warnings.append(
                f"facts as_of {pack.facts.as_of} is older than {STALE_FACT_DAYS} days: re-verify"
            )
        for fact in pack.facts.facts:
            if (today - fact.as_of).days > STALE_FACT_DAYS:
                warnings.append(f"fact {fact.id} as_of {fact.as_of} is stale: re-verify sources")
        for name, platform in pack.facts.platforms.items():
            if platform.status == "unreleased" and not platform.fact:
                warnings.append(f"platform {name} is 'unreleased' without a backing fact id")
    for dom in outlets:
        if dom.count(".") > 2:
            warnings.append(f"allowlist entry {dom} looks like a subdomain; use the eTLD+1")
    return warnings


def validate_pack_dir(path: Path, today: date | None = None) -> ValidationReport:
    report = ValidationReport(path=path)
    try:
        report.pack = load_pack(path)
    except PackError as exc:
        report.errors.append(str(exc))
        return report
    report.warnings.extend(lint_pack(report.pack, today))
    return report
