"""abuse.ch URLhaus (candidates + reputation). Requires a free Auth-Key."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime
from typing import Any

import orjson

from lureradar.enrich.types import ReputationHit
from lureradar.errors import InvalidTargetError, SourceError
from lureradar.models import Candidate
from lureradar.sources.base import HttpSource, SourceInfo
from lureradar.util.domains import parse_target
from lureradar.util.time import parse_iso

API = "https://urlhaus-api.abuse.ch/v1/"


def parse_recent(data: dict[str, Any], since: datetime) -> Iterator[Candidate]:
    for item in data.get("urls") or []:
        try:
            seen = parse_iso(str(item.get("date_added", "")).replace(" UTC", "Z").replace(" ", "T"))
            target = parse_target(str(item.get("url", "")))
        except (ValueError, InvalidTargetError):
            continue
        if seen < since or not target.host:
            continue
        yield Candidate(
            domain=target.host,
            url=target.url,
            source="urlhaus",
            first_seen=seen,
            reputation_hit=True,
            metadata={"threat": item.get("threat"), "tags": item.get("tags") or []},
        )


class UrlhausSource(HttpSource):
    info = SourceInfo(
        name="urlhaus",
        title="abuse.ch URLhaus",
        kind="both",
        endpoint=API,
        terms_url="https://urlhaus.abuse.ch/api/",
        requires_key=True,
        key_env="LURERADAR_URLHAUS_KEY",
        rate_limit="fair use; Auth-Key required for the API",
        redistribution="not redistributed raw; hits only corroborate our own scores",
    )
    fixture_name = "urlhaus.json"

    @property
    def key(self) -> str | None:
        return self.settings.urlhaus_key

    def _headers(self) -> dict[str, str]:
        return {"Auth-Key": self.key or ""}

    def fetch(self, since: datetime) -> Iterable[Candidate]:
        if self.fixtures is not None:
            yield from parse_recent(orjson.loads(self.fixture_bytes()), since)
            return
        if not self.key:
            return
        resp = self.request("GET", API + "urls/recent/limit/1000/", headers=self._headers())
        yield from parse_recent(orjson.loads(resp.content), since)

    def lookup(self, host: str, url: str | None = None) -> list[ReputationHit]:
        if self.fixtures is not None:
            data = orjson.loads(self.fixture_bytes("urlhaus_host.json"))
        elif not self.key:
            return []
        else:
            try:
                resp = self.request(
                    "POST", API + "host/", data={"host": host}, headers=self._headers()
                )
                data = orjson.loads(resp.content)
            except (SourceError, orjson.JSONDecodeError):
                return []
        if data.get("query_status") == "ok" and data.get("urls"):
            online = [u for u in data["urls"] if u.get("url_status") == "online"]
            return [
                ReputationHit(
                    source="urlhaus", detail=f"{len(data['urls'])} URL(s), {len(online)} online"
                )
            ]
        return []
