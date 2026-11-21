"""Pydantic schema for campaign packs (``packs/<id>/pack.yaml``).

The JSON Schema in ``src/lureradar/schemas/pack.schema.json`` is generated from
these models (``make schemas``) and checked for drift in the test suite.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
_DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9-]{2,63}$")


def _clean_terms(values: list[str], what: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        term = " ".join(str(raw).lower().split())
        if not term:
            raise ValueError(f"empty {what}")
        if len(term) < 2:
            raise ValueError(f"{what} {raw!r} is too short (min 2 characters)")
        if term in seen:
            raise ValueError(f"duplicate {what} {term!r}")
        seen.add(term)
        out.append(term)
    return out


def _clean_domains(values: list[str], what: str) -> list[str]:
    out = []
    for raw in values:
        dom = str(raw).strip().lower().rstrip(".")
        if not _DOMAIN_RE.match(dom):
            raise ValueError(f"{what}: {raw!r} is not a valid registrable domain")
        out.append(dom)
    if len(set(out)) != len(out):
        raise ValueError(f"{what}: duplicate domains")
    return out


class Brand(BaseModel):
    """An impersonation target: an official-looking *name*, never a logo."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Canonical brand token, lowercase, no spaces")
    display: str | None = Field(default=None, description="Human-readable name for verdicts")
    aliases: list[str] = Field(default_factory=list, description="Other tokens lures use")
    official: list[str] = Field(min_length=1, description="Official registrable domains")

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.fullmatch(r"[a-z0-9]{3,40}", v):
            raise ValueError(f"brand name {v!r} must be 3-40 lowercase letters/digits")
        return v

    @property
    def label(self) -> str:
        return self.display or self.name

    @field_validator("aliases")
    @classmethod
    def _aliases(cls, v: list[str]) -> list[str]:
        cleaned = _clean_terms(v, "brand alias")
        for alias in cleaned:
            if not re.fullmatch(r"[a-z0-9]{3,40}", alias):
                raise ValueError(f"brand alias {alias!r} must be 3-40 lowercase letters/digits")
        return cleaned

    @field_validator("official")
    @classmethod
    def _official(cls, v: list[str]) -> list[str]:
        return _clean_domains(v, "brand official domains")


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    title: str
    publisher: str | None = None
    published: date | None = None
    accessed: date


class Fact(BaseModel):
    """A dated, sourced claim. Facts drive rules; they are never asserted undated."""

    model_config = ConfigDict(extra="forbid")

    id: str
    claim: str
    status: Literal[
        "confirmed",
        "not_announced",
        "announced",
        "announced_undated",
        "announced_dated",
        "released",
        "rumoured",
        "denied",
    ]
    value: str | None = None
    as_of: date
    sources: list[Source] = Field(min_length=1)
    notes: str | None = None


#: Fact statuses meaning "this platform is (being) released": rules referencing
#: such a fact treat the platform as released (PC Watch coupling).
RELEASE_STATUSES = frozenset({"announced", "announced_undated", "announced_dated", "released"})


class Platform(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["released", "unreleased"]
    label: str | None = Field(default=None, description="Display name, e.g. 'PC'")
    terms: list[str] = Field(min_length=1)
    fact: str | None = Field(default=None, description="Fact id backing the status")

    @field_validator("terms")
    @classmethod
    def _terms(cls, v: list[str]) -> list[str]:
        return _clean_terms(v, "platform term")


class Facts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: date
    facts: list[Fact] = Field(default_factory=list)
    platforms: dict[str, Platform] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _refs(self) -> Facts:
        ids = [f.id for f in self.facts]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate fact ids")
        for name, platform in self.platforms.items():
            if platform.fact and platform.fact not in ids:
                raise ValueError(f"platform {name!r} references unknown fact {platform.fact!r}")
        return self

    def fact(self, fact_id: str) -> Fact | None:
        return next((f for f in self.facts if f.id == fact_id), None)

    def effective_status(self, name: str) -> str:
        """Platform status after applying its backing fact (PC Watch coupling)."""
        platform = self.platforms[name]
        fact = self.fact(platform.fact) if platform.fact else None
        if platform.status == "unreleased" and fact is not None and fact.status in RELEASE_STATUSES:
            return "released"
        return platform.status

    @property
    def unreleased_terms(self) -> dict[str, list[str]]:
        return {
            k: p.terms
            for k, p in self.platforms.items()
            if self.effective_status(k) == "unreleased"
        }


class Allowlist(BaseModel):
    """Legitimate domains.

    ``outlets`` are hard-cleared (publishers, wikis, retailers, official sites).
    ``platforms`` host user content: they are never listed at domain level, but
    URL paths on them are still analysed (verdict capped at SUSPICIOUS).
    """

    model_config = ConfigDict(extra="forbid")

    outlets: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)

    @field_validator("outlets", "platforms")
    @classmethod
    def _domains(cls, v: list[str]) -> list[str]:
        return _clean_domains(v, "allowlist")

    @model_validator(mode="after")
    def _disjoint(self) -> Allowlist:
        both = set(self.outlets) & set(self.platforms)
        if both:
            raise ValueError(f"domains in both outlets and platforms: {sorted(both)}")
        return self


class Pack(BaseModel):
    """A campaign pack, fully resolved (file references already loaded)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    subject: str | None = Field(default=None, description="What is launching, e.g. a game title")
    version: int = Field(ge=1)
    as_of: date
    description: str = ""
    keywords: list[str] = Field(min_length=1)
    intents: list[str] = Field(min_length=1)
    brands: list[Brand] = Field(default_factory=list)
    allowlist: Allowlist = Field(default_factory=Allowlist)
    facts: Facts | None = None
    pc_watch: dict[str, Any] | None = Field(
        default=None, description="PC Watch config (validated by lureradar.pcwatch.config)"
    )

    @property
    def release_storefronts(self) -> list[str]:
        """Official storefront domains allowlisted once the watched platform is announced."""
        if not self.pc_watch or not self.facts:
            return []
        fact = self.facts.fact(str(self.pc_watch.get("fact", "")))
        if fact is None or fact.status not in RELEASE_STATUSES:
            return []
        return [str(d) for d in self.pc_watch.get("pc_storefronts") or []]

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not _ID_RE.match(v):
            raise ValueError(f"pack id {v!r} must match {_ID_RE.pattern}")
        return v

    @field_validator("keywords")
    @classmethod
    def _keywords(cls, v: list[str]) -> list[str]:
        cleaned = _clean_terms(v, "keyword")
        for kw in cleaned:
            if len(re.sub(r"[^a-z0-9]", "", kw)) < 4:
                raise ValueError(
                    f"keyword {kw!r} is too generic: at least 4 letters/digits are required"
                )
        return cleaned

    @field_validator("intents")
    @classmethod
    def _intents(cls, v: list[str]) -> list[str]:
        return _clean_terms(v, "intent")

    @property
    def subject_label(self) -> str:
        return self.subject or self.name

    def platform_label(self, platform: str) -> str:
        if self.facts and platform in self.facts.platforms:
            label = self.facts.platforms[platform].label
            if label:
                return label
        return platform.replace("_", " ")

    def brand(self, name: str) -> Brand | None:
        return next((b for b in self.brands if b.name == name), None)

    @model_validator(mode="after")
    def _brands_unique(self) -> Pack:
        names = [b.name for b in self.brands]
        if len(set(names)) != len(names):
            raise ValueError("duplicate brand names")
        return self


class PackFile(BaseModel):
    """On-disk ``pack.yaml``: list fields may instead name a sibling YAML file."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    subject: str | None = None
    version: int
    as_of: date
    description: str = ""
    keywords: list[str] | str
    intents: list[str] | str
    brands: list[Brand] | str = Field(default_factory=list)
    allowlist: Allowlist | str | None = None
    facts: Facts | str | None = None
    pc_watch: str | None = None
