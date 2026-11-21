"""OpenPhish community feed (candidates + reputation lookups).

The community feed is a plain-text list of phishing URLs, refreshed by
OpenPhish; its terms restrict redistribution, so LureRadar never republishes
the feed: entries only *seed* candidates that we then score ourselves, and a
hit counts as one external reputation source.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from functools import cached_property

from lureradar.enrich.types import ReputationHit
from lureradar.errors import InvalidTargetError
from lureradar.models import Candidate, TargetKind
from lureradar.sources.base import HttpSource, SourceInfo
from lureradar.util.domains import parse_target
from lureradar.util.time import utcnow

FEED_URL = "https://openphish.com/feed.txt"


class OpenPhishSource(HttpSource):
    info = SourceInfo(
        name="openphish",
        title="OpenPhish community feed",
        kind="both",
        endpoint=FEED_URL,
        terms_url="https://openphish.com/terms.html",
        requires_key=False,
        rate_limit="community feed refreshes about every 12 hours; fetch at most hourly",
        redistribution="not redistributed; used only to seed and corroborate our own scores",
    )
    fixture_name = "openphish.txt"

    def _lines(self) -> list[str]:
        raw = (
            self.fixture_bytes()
            if self.fixtures is not None
            else self.request("GET", FEED_URL).content
        )
        return [ln.strip() for ln in raw.decode("utf-8", "replace").splitlines() if ln.strip()]

    @cached_property
    def _index(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for url in self._lines():
            try:
                t = parse_target(url)
            except InvalidTargetError:
                continue
            if t.kind is not TargetKind.TEXT:
                out.setdefault(t.host, url)
        return out

    def fetch(self, since: datetime) -> Iterable[Candidate]:
        now = utcnow()
        for host, url in self._index.items():
            yield Candidate(
                domain=host, url=url, source="openphish", first_seen=now, reputation_hit=True
            )

    def lookup(self, host: str, url: str | None = None) -> list[ReputationHit]:
        if host.lower() in self._index:
            return [ReputationHit(source="openphish", detail="listed in community feed")]
        return []
