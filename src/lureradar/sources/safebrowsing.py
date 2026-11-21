"""Google Safe Browsing v4 Lookup API (reputation only). Requires an API key.

Google restricts the free Lookup API to non-commercial use; commercial users
should use the Web Risk API instead. Verdicts are never redistributed.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

import orjson

from lureradar import __version__
from lureradar.enrich.types import ReputationHit
from lureradar.errors import SourceError
from lureradar.models import Candidate
from lureradar.sources.base import HttpSource, SourceInfo

API = "https://safebrowsing.googleapis.com/v4/threatMatches:find"


class SafeBrowsingSource(HttpSource):
    info = SourceInfo(
        name="safebrowsing",
        title="Google Safe Browsing (Lookup API v4)",
        kind="reputation",
        endpoint=API,
        terms_url="https://developers.google.com/safe-browsing/v4/usage-limits",
        requires_key=True,
        key_env="LURERADAR_SAFEBROWSING_KEY",
        rate_limit="per-key quota (Google Cloud console); non-commercial use only",
        redistribution="never redistributed; used only as a corroborating signal",
    )
    fixture_name = "safebrowsing.json"

    @property
    def key(self) -> str | None:
        return self.settings.safebrowsing_key

    def probe_url(self) -> str:
        return f"{API}?key={self.key}"

    def fetch(self, since: datetime) -> Iterable[Candidate]:
        return iter(())

    def health(self):  # type: ignore[no-untyped-def]
        if self.fixtures is not None:
            return self._health("degraded", "fixture mode (recorded responses)")
        if not self.key:
            return self._health("requires_key", "set LURERADAR_SAFEBROWSING_KEY to enable")
        hits = self.lookup("example.com", "http://example.com/")
        return self._health("ok", f"lookup API answered ({len(hits)} match)")

    def lookup(self, host: str, url: str | None = None) -> list[ReputationHit]:
        body = {
            "client": {"clientId": "lureradar", "clientVersion": __version__},
            "threatInfo": {
                "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"],
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": url or f"http://{host}/"}],
            },
        }
        if self.fixtures is not None:
            data = orjson.loads(self.fixture_bytes())
        elif not self.key:
            return []
        else:
            try:
                resp = self.request("POST", f"{API}?key={self.key}", json=body)
                data = orjson.loads(resp.content or b"{}")
            except (SourceError, orjson.JSONDecodeError):
                return []
        types = sorted({m.get("threatType", "?") for m in data.get("matches") or []})
        return [ReputationHit(source="safebrowsing", detail=", ".join(types))] if types else []
