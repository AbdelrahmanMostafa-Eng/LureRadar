"""urlscan.io search API (candidates + reputation). A key is optional but
raises limits; results are used as signals and never republished."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime
from typing import Any
from urllib.parse import quote

import orjson

from lureradar.config import Settings
from lureradar.enrich.types import ReputationHit
from lureradar.errors import InvalidTargetError, SourceError
from lureradar.models import Candidate
from lureradar.sources.base import HttpSource, SourceInfo
from lureradar.util.domains import normalise_domain
from lureradar.util.time import parse_iso

API = "https://urlscan.io/api/v1/search/"


def _malicious(result: dict[str, Any]) -> bool:
    verdicts = result.get("verdicts") or {}
    overall = verdicts.get("overall") or {}
    return bool(overall.get("malicious") or verdicts.get("malicious"))


def parse_search(data: dict[str, Any], since: datetime) -> Iterator[Candidate]:
    for result in data.get("results") or []:
        page = result.get("page") or {}
        try:
            domain = normalise_domain(str(page.get("domain", "")))
            seen = parse_iso(str((result.get("task") or {}).get("time", "")))
        except (InvalidTargetError, ValueError):
            continue
        if seen < since:
            continue
        yield Candidate(
            domain=domain,
            url=str(page.get("url") or "") or None,
            source="urlscan",
            first_seen=seen,
            reputation_hit=_malicious(result),
        )


class UrlscanSource(HttpSource):
    info = SourceInfo(
        name="urlscan",
        title="urlscan.io search API",
        kind="both",
        endpoint=API,
        terms_url="https://urlscan.io/terms/",
        requires_key=False,
        key_env="LURERADAR_URLSCAN_KEY",
        rate_limit="public search is rate-limited; an API key raises quotas",
        redistribution="results not republished; only our derived indicators",
    )
    fixture_name = "urlscan.json"

    def __init__(
        self, settings: Settings | None = None, *, keywords: list[str] | None = None, **kw: Any
    ) -> None:
        super().__init__(settings, **kw)
        self.terms = keywords or ["gta6", "gtavi"]

    @property
    def key(self) -> str | None:
        return self.settings.urlscan_key

    def _headers(self) -> dict[str, str]:
        return {"API-Key": self.key} if self.key else {}

    def probe_url(self) -> str:
        return API + "?q=domain:example.com&size=1"

    def _search(self, query: str) -> dict[str, Any]:
        resp = self.request("GET", f"{API}?q={quote(query)}&size=100", headers=self._headers())
        data: dict[str, Any] = orjson.loads(resp.content)
        return data

    def fetch(self, since: datetime) -> Iterable[Candidate]:
        if self.fixtures is not None:
            yield from parse_search(orjson.loads(self.fixture_bytes()), since)
            return
        for term in self.terms:
            try:
                yield from parse_search(self._search(f"page.domain:*{term}*"), since)
            except (SourceError, orjson.JSONDecodeError):
                continue

    def lookup(self, host: str, url: str | None = None) -> list[ReputationHit]:
        if self.fixtures is not None:
            data = orjson.loads(self.fixture_bytes())
        else:
            try:
                data = self._search(f"page.domain:{host}")
            except (SourceError, orjson.JSONDecodeError):
                return []
        host = host.lower()
        bad = [
            r
            for r in data.get("results") or []
            if _malicious(r) and str((r.get("page") or {}).get("domain", "")).lower() == host
        ]
        return (
            [ReputationHit(source="urlscan", detail=f"{len(bad)} malicious verdict(s)")]
            if bad
            else []
        )
