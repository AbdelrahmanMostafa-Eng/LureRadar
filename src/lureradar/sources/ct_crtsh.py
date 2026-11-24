"""crt.sh Certificate Transparency search (candidates).

Politeness: one query per campaign term, at most one request every 5 seconds,
exponential backoff on 429/5xx. crt.sh is a free community service run by
Sectigo; we only derive our own indicators from it.
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Iterator
from datetime import datetime
from typing import Any
from urllib.parse import quote

import orjson

from lureradar.config import Settings
from lureradar.errors import InvalidTargetError, SourceError
from lureradar.models import Candidate
from lureradar.sources.base import HttpSource, SourceInfo
from lureradar.util.domains import normalise_domain
from lureradar.util.time import parse_iso

DEFAULT_TERMS = ["gta6", "gtavi", "gta-6", "grandtheftauto6"]


def parse_entries(entries: list[dict[str, Any]], since: datetime) -> Iterator[Candidate]:
    for entry in entries:
        try:
            seen = parse_iso(str(entry.get("entry_timestamp") or entry.get("not_before")))
        except ValueError:
            continue
        if seen < since:
            continue
        for raw in str(entry.get("name_value", "")).split("\n"):
            name = raw.strip().lstrip("*.").lower()
            if not name or " " in name or "@" in name:
                continue
            try:
                domain = normalise_domain(name)
            except InvalidTargetError:
                continue
            yield Candidate(
                domain=domain,
                source="crtsh",
                first_seen=seen,
                metadata={
                    "cert_id": entry.get("id"),
                    "issuer": str(entry.get("issuer_name", ""))[:120],
                    "not_before": entry.get("not_before"),
                },
            )


class CrtShSource(HttpSource):
    info = SourceInfo(
        name="crtsh",
        title="crt.sh (Certificate Transparency search)",
        kind="candidates",
        endpoint="https://crt.sh/",
        terms_url="https://crt.sh/",
        requires_key=False,
        rate_limit="be polite: <= 1 request / 5 s, retries with backoff",
        redistribution="derived indicators only (domain names from public CT logs)",
    )
    fixture_name = "crtsh.json"
    interval_s = 5.0

    def __init__(
        self, settings: Settings | None = None, *, keywords: list[str] | None = None, **kw: Any
    ) -> None:
        super().__init__(settings, **kw)
        self.terms = keywords or DEFAULT_TERMS
        self.failed_queries = 0

    def probe_url(self) -> str:
        return "https://crt.sh/?q=example.com&output=json&exclude=expired"

    def fetch(self, since: datetime) -> Iterable[Candidate]:
        self.failed_queries = 0
        if self.fixtures is not None:
            yield from parse_entries(orjson.loads(self.fixture_bytes()), since)
            return
        last_error = ""
        for i, term in enumerate(self.terms):
            if i:
                time.sleep(self.interval_s)
            url = f"https://crt.sh/?q={quote('%' + term + '%')}&output=json&exclude=expired"
            try:
                data = orjson.loads(self.request("GET", url).content)
            except (SourceError, orjson.JSONDecodeError) as exc:
                # One failed term must not stop the others, but it is counted:
                # an outage must never be reported as "ok, nothing found".
                self.failed_queries += 1
                last_error = str(exc)[:120]
                continue
            if isinstance(data, list):
                yield from parse_entries(data, since)
        if self.terms and self.failed_queries == len(self.terms):
            raise SourceError(f"all {len(self.terms)} crt.sh queries failed (last: {last_error})")
