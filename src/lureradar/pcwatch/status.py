"""Status model and the resolution rules (the heart of PC Watch).

Rules:
1. The *published* status is the maintainer-approved fact in facts.yaml.
2. If the last fully successful check (all required sources OK) is older than
   ``stale_after_hours`` (or never happened) the published status is UNKNOWN.
   Failures never produce NOT_ANNOUNCED.
3. If a successful official source suggests a status above the approved one,
   ``review_pending`` is set (and the workflow opens an issue); the published
   status does NOT change until a maintainer commits facts.yaml.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from lureradar.packs.schema import Pack
from lureradar.pcwatch.config import PcWatchConfig, TimelineEntry

PCWATCH_SCHEMA_VERSION = "1.0"
DISCLAIMER = (
    "LureRadar is an independent, unofficial project, not affiliated with Rockstar Games or "
    "Take-Two Interactive. Status reflects official sources only."
)


class Status(StrEnum):
    NOT_ANNOUNCED = "NOT_ANNOUNCED"
    ANNOUNCED_UNDATED = "ANNOUNCED_UNDATED"
    ANNOUNCED_DATED = "ANNOUNCED_DATED"
    RELEASED = "RELEASED"
    UNKNOWN = "UNKNOWN"

    @property
    def rank(self) -> int:
        return {
            "NOT_ANNOUNCED": 0,
            "ANNOUNCED_UNDATED": 1,
            "ANNOUNCED_DATED": 2,
            "RELEASED": 3,
        }.get(self.value, -1)

    @property
    def headline(self) -> str:
        return {
            "NOT_ANNOUNCED": "No official PC release has been announced",
            "ANNOUNCED_UNDATED": "A PC version has been officially announced (no date yet)",
            "ANNOUNCED_DATED": "A PC version has been officially announced with a date",
            "RELEASED": "The PC version has been officially released",
            "UNKNOWN": "Status unknown: official sources could not be checked recently",
        }[self.value]


FACT_TO_STATUS = {
    "not_announced": Status.NOT_ANNOUNCED,
    "announced": Status.ANNOUNCED_UNDATED,
    "announced_undated": Status.ANNOUNCED_UNDATED,
    "announced_dated": Status.ANNOUNCED_DATED,
    "released": Status.RELEASED,
}


class Finding(BaseModel):
    source: str
    status: Status
    url: str
    title: str
    snippet: str = Field(description="At most 15 words of context")
    negated: bool = False


class SourceCheck(BaseModel):
    id: str
    name: str
    kind: str
    status: Literal["ok", "failed", "unsupported"]
    detail: str = ""
    items_seen: int = 0
    required: bool = False
    findings: list[Finding] = Field(default_factory=list)


class CheckResult(BaseModel):
    checked_at: datetime
    sources: list[SourceCheck]

    @property
    def full_success(self) -> bool:
        required = [s for s in self.sources if s.required]
        return bool(required) and all(s.status == "ok" for s in required)

    @property
    def suggested(self) -> Status:
        best = Status.NOT_ANNOUNCED
        for src in self.sources:
            if src.status != "ok":
                continue
            for f in src.findings:
                if not f.negated and f.status.rank > best.rank:
                    best = f.status
        return best


class PcWatchState(BaseModel):
    schema_version: str = PCWATCH_SCHEMA_VERSION
    generated_at: datetime
    subject: str
    platform: str
    status: Status
    headline: str
    note: str = ""
    confirmed_status: Status
    confirmed_as_of: date | None = None
    last_checked: datetime | None = None
    last_success: datetime | None = None
    last_changed: datetime | None = None
    stale: bool = True
    review_pending: bool = False
    suggested_status: Status | None = None
    fact_id: str
    sources: list[SourceCheck] = Field(default_factory=list)
    timeline: list[TimelineEntry] = Field(default_factory=list)
    count: int = 0
    disclaimer: str = DISCLAIMER


def confirmed_status(pack: Pack, config: PcWatchConfig) -> tuple[Status, date | None]:
    fact = pack.facts.fact(config.fact) if pack.facts else None
    if fact is None:
        return Status.UNKNOWN, None
    return FACT_TO_STATUS.get(fact.status, Status.UNKNOWN), fact.as_of


def resolve(
    pack: Pack,
    config: PcWatchConfig,
    check: CheckResult | None,
    previous: PcWatchState | None,
    now: datetime,
) -> PcWatchState:
    confirmed, as_of = confirmed_status(pack, config)
    last_success = previous.last_success if previous else None
    if check is not None and check.full_success:
        last_success = check.checked_at
    last_checked = check.checked_at if check else (previous.last_checked if previous else None)
    stale = last_success is None or now - last_success > timedelta(hours=config.stale_after_hours)

    last_changed: datetime | None
    if previous is not None and previous.confirmed_status == confirmed and previous.last_changed:
        last_changed = previous.last_changed
    elif previous is not None and previous.confirmed_status != confirmed:
        last_changed = now
    else:
        last_changed = (
            datetime(as_of.year, as_of.month, as_of.day, tzinfo=now.tzinfo) if as_of else None
        )

    status = Status.UNKNOWN if stale or confirmed is Status.UNKNOWN else confirmed
    note = ""
    if status is Status.UNKNOWN and confirmed is not Status.UNKNOWN:
        when = (
            last_success.date().isoformat()
            if last_success
            else (as_of.isoformat() if as_of else "?")
        )
        note = f"UNKNOWN (last confirmed {confirmed.value} on {when})"
    suggested = check.suggested if check else None
    review = bool(suggested and suggested.rank > confirmed.rank)
    if review:
        note = (note + " · " if note else "") + (
            f"official-source evidence suggests {suggested.value if suggested else ''}; "
            "awaiting maintainer review"
        )
    timeline = sorted(config.timeline, key=lambda e: e.date, reverse=True)
    return PcWatchState(
        generated_at=now,
        subject=config.subject,
        platform=config.platform,
        status=status,
        headline=status.headline,
        note=note,
        confirmed_status=confirmed,
        confirmed_as_of=as_of,
        last_checked=last_checked,
        last_success=last_success,
        last_changed=last_changed,
        stale=stale,
        review_pending=review,
        suggested_status=suggested,
        fact_id=config.fact,
        sources=check.sources if check else (previous.sources if previous else []),
        timeline=timeline,
        count=len(timeline),
    )


def honest_sentence(state: PcWatchState) -> str:
    """The one-line answer used on the page, badge alt text and feeds."""
    stamp = state.last_success.strftime("%Y-%m-%d %H:%M UTC") if state.last_success else "never"
    if state.status is Status.NOT_ANNOUNCED:
        return f"No official PC release of {state.subject} has been announced as of {stamp}."
    if state.status is Status.UNKNOWN:
        detail = state.note.removeprefix("UNKNOWN ").strip("() ")
        last = detail.split(" · ", 1)[0] if detail.startswith("last confirmed") else ""
        suffix = (
            f" Official sources could not be checked recently ({last})."
            if last
            else (" Official sources could not be checked recently.")
        )
        return f"PC status for {state.subject} is unknown right now.{suffix}"
    return f"{state.headline} (official sources, confirmed as of {stamp})."
