"""Core data models shared by the engine, CLI, pipeline and exporters."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from lureradar.config import VERDICT_SCHEMA_VERSION


class Tier(StrEnum):
    """Verdict tiers, ordered from least to most severe."""

    CLEAR = "clear"
    SUSPICIOUS = "suspicious"
    LIKELY = "likely"
    CONFIRMED = "confirmed"

    @property
    def rank(self) -> int:
        return _TIER_RANK[self]

    @property
    def exit_code(self) -> int:
        """CLI exit code: 0 clear, 10 suspicious, 20 likely, 30 confirmed."""
        return self.rank * 10

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Tier):
            return NotImplemented
        return self.rank >= other.rank

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Tier):
            return NotImplemented
        return self.rank > other.rank

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Tier):
            return NotImplemented
        return self.rank <= other.rank

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Tier):
            return NotImplemented
        return self.rank < other.rank

    @classmethod
    def parse(cls, value: str) -> Tier:
        try:
            return cls(value.strip().lower())
        except ValueError as exc:
            choices = ", ".join(t.value for t in cls)
            raise ValueError(f"unknown tier {value!r} (choose from {choices})") from exc


_TIER_RANK = {Tier.CLEAR: 0, Tier.SUSPICIOUS: 1, Tier.LIKELY: 2, Tier.CONFIRMED: 3}


class TargetKind(StrEnum):
    URL = "url"
    DOMAIN = "domain"
    TEXT = "text"


SignalCategory = Literal[
    "lexical", "brand", "platform", "infrastructure", "content", "reputation", "trust", "text"
]


class Signal(BaseModel):
    """One named, weighted, explainable piece of evidence."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Stable signal identifier, see docs/SIGNALS.md")
    weight: int = Field(description="Contribution to the 0-100 score (may be negative)")
    explanation: str = Field(description="Human-readable reason")
    evidence: tuple[str, ...] = Field(default=(), description="Defanged evidence snippets")
    category: SignalCategory = "lexical"
    live: bool = Field(default=False, description="True if produced by --live enrichment")


class ParsedTarget(BaseModel):
    """A normalised URL or domain."""

    model_config = ConfigDict(frozen=True)

    raw: str
    kind: TargetKind
    url: str | None = None
    scheme: str | None = None
    host: str = ""
    unicode_host: str = ""
    registrable_domain: str = ""
    domain_label: str = ""
    subdomain: str = ""
    suffix: str = ""
    path: str = ""
    is_ip: bool = False
    is_private_suffix: bool = False

    @property
    def hostname_tokens(self) -> list[str]:
        from lureradar.util.domains import tokenize

        owned = ".".join(p for p in (self.subdomain, self.domain_label) if p)
        return tokenize(owned)


class Verdict(BaseModel):
    """Result of scoring one target. Serialised by ``check --json``."""

    schema_version: str = VERDICT_SCHEMA_VERSION
    target: str = Field(description="The target, defanged")
    kind: TargetKind
    host: str | None = Field(default=None, description="Hostname, defanged")
    registrable_domain: str | None = Field(default=None, description="eTLD+1, defanged")
    score: int = Field(ge=0, le=100)
    tier: Tier
    signals: list[Signal] = Field(default_factory=list)
    corroborated: bool = Field(
        default=False, description="External reputation corroborated by independent evidence"
    )
    allowlisted: bool = False
    mode: Literal["offline", "live"] = "offline"
    packs: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    urls: list[Verdict] = Field(
        default_factory=list, description="For text targets: verdicts for embedded URLs"
    )
    generated_at: datetime

    @property
    def top_signals(self) -> list[Signal]:
        return sorted(self.signals, key=lambda s: (-abs(s.weight), s.id))


class Candidate(BaseModel):
    """A potential indicator emitted by a source adapter."""

    model_config = ConfigDict(frozen=True)

    domain: str
    url: str | None = None
    source: str
    first_seen: datetime
    reputation_hit: bool = Field(
        default=False, description="The source itself flags this as malicious"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


HealthStatus = Literal["ok", "degraded", "requires_key", "down", "disabled"]


class SourceHealth(BaseModel):
    source: str
    status: HealthStatus
    detail: str = ""
    checked_at: datetime
    terms_url: str = ""
    requires_key: bool = False


IndicatorStatus = Literal["active", "stale"]


class Indicator(BaseModel):
    """A published feed entry."""

    domain: str
    url: str | None = None
    tier: Tier
    score: int = Field(ge=0, le=100)
    first_seen: datetime
    last_seen: datetime
    status: IndicatorStatus = "active"
    sources: list[str] = Field(default_factory=list)
    packs: list[str] = Field(default_factory=list)
    signals: list[Signal] = Field(default_factory=list)
    dispute_url: str = ""

    @property
    def signal_ids(self) -> list[str]:
        return [s.id for s in self.signals]
