"""PC Watch configuration (``packs/<id>/pc_watch.yaml``)."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from lureradar.errors import PackError
from lureradar.packs.schema import Pack

SourceFormat = Literal["html", "atom", "steam_search_json", "unsupported"]
MAX_QUOTE_WORDS = 15


class WatchSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    kind: Literal["publisher", "investor_relations", "regulatory", "storefront", "social"]
    url: HttpUrl
    format: SourceFormat
    official_domains: list[str] = Field(min_length=1)
    required: bool = False
    expect_min_items: int = 0
    terms_url: str | None = None
    notes: str = ""


class TimelineEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: dt.date
    source: str
    title: str
    url: HttpUrl
    paraphrase: str
    quote: str | None = None
    meaning: str
    kind: Literal["official", "reported"] = "official"
    verified_on: dt.date
    verification: str

    @field_validator("quote")
    @classmethod
    def _short_quote(cls, v: str | None) -> str | None:
        if v and len(v.split()) > MAX_QUOTE_WORDS:
            raise ValueError(f"quotes are limited to {MAX_QUOTE_WORDS} words")
        return v

    @field_validator("paraphrase")
    @classmethod
    def _short_paraphrase(cls, v: str) -> str:
        if len(v.split()) > 40:
            raise ValueError("paraphrase must be 40 words or fewer")
        return v


class PcWatchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    subject: str
    platform: str = "pc"
    fact: str
    stale_after_hours: int = Field(default=36, ge=1, le=24 * 14)
    proximity_chars: int = Field(default=140, ge=20, le=2000)
    game_terms: list[str] = Field(min_length=1)
    platform_terms: list[str] = Field(min_length=1)
    pc_storefronts: list[str] = Field(default_factory=list)
    sources: list[WatchSource] = Field(min_length=1)
    timeline: list[TimelineEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _refs(self) -> PcWatchConfig:
        ids = [s.id for s in self.sources]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate source ids")
        by_id = {s.id: s for s in self.sources}
        for entry in self.timeline:
            src = by_id.get(entry.source)
            if src is None:
                raise ValueError(
                    f"timeline entry {entry.title!r} has unknown source {entry.source!r}"
                )
            host = (entry.url.host or "").lower()
            if entry.kind == "official" and not any(
                host == d or host.endswith("." + d) for d in src.official_domains
            ):
                raise ValueError(
                    f"official timeline entry {entry.title!r} is not on an official domain"
                )
        return self

    def source(self, source_id: str) -> WatchSource:
        return next(s for s in self.sources if s.id == source_id)


def load_config(pack: Pack) -> PcWatchConfig:
    if not pack.pc_watch:
        raise PackError(f"pack {pack.id} has no pc_watch.yaml")
    try:
        return PcWatchConfig.model_validate(pack.pc_watch)
    except ValueError as exc:
        raise PackError(f"{pack.id}/pc_watch.yaml: {exc}") from exc
