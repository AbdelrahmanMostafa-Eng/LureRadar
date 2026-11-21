"""The common Source protocol and HTTP plumbing shared by all adapters.

Adapters are *fixtures-aware*: given ``fixtures=<dir>`` they read recorded
responses (reserved domains only) instead of the network, which is how the
test suite and ``lureradar scan --fixtures`` run fully offline.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

import httpx

from lureradar.config import Settings, user_agent
from lureradar.enrich.types import ReputationHit
from lureradar.errors import SourceError
from lureradar.models import Candidate, HealthStatus, SourceHealth
from lureradar.util.time import utcnow

SourceKind = Literal["candidates", "reputation", "both"]


@dataclass(frozen=True)
class SourceInfo:
    name: str
    title: str
    kind: SourceKind
    endpoint: str
    terms_url: str
    requires_key: bool
    rate_limit: str
    redistribution: str
    key_env: str | None = None


@runtime_checkable
class Source(Protocol):
    info: SourceInfo

    def fetch(self, since: datetime) -> Iterable[Candidate]: ...

    def health(self) -> SourceHealth: ...


@runtime_checkable
class ReputationLookup(Protocol):
    info: SourceInfo

    def lookup(self, host: str, url: str | None = None) -> list[ReputationHit]: ...


class HttpSource:
    """Base class: settings, fixtures, a polite HTTP client and a health probe."""

    info: SourceInfo
    fixture_name: str = ""
    retries: int = 2
    backoff_s: float = 2.0

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        fixtures: Path | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.fixtures = fixtures
        self._client = client

    # ---------------------------------------------------------------- plumbing
    @property
    def key(self) -> str | None:
        return None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=httpx.Timeout(20.0),
                headers={"User-Agent": user_agent()},
                follow_redirects=True,
                max_redirects=3,
            )
        return self._client

    def fixture_bytes(self, name: str | None = None) -> bytes:
        if self.fixtures is None:
            raise SourceError(f"{self.info.name}: no fixtures directory configured")
        path = self.fixtures / (name or self.fixture_name)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise SourceError(f"{self.info.name}: fixture {path} missing") from exc

    def request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        """HTTP with retries/backoff on 429 and 5xx. Raises SourceError."""
        last: str = ""
        for attempt in range(self.retries + 1):
            try:
                resp = self.client.request(method, url, **kwargs)  # type: ignore[arg-type]
            except httpx.HTTPError as exc:
                last = f"{type(exc).__name__}: {exc}"
            else:
                if resp.status_code < 400:
                    return resp
                last = f"HTTP {resp.status_code}"
                if resp.status_code not in (429, 500, 502, 503, 504):
                    break
            if attempt < self.retries:
                time.sleep(self.backoff_s * (2**attempt))
        raise SourceError(f"{self.info.name}: {last}")

    # ------------------------------------------------------------------ health
    def _health(self, status: HealthStatus, detail: str) -> SourceHealth:
        return SourceHealth(
            source=self.info.name,
            status=status,
            detail=detail,
            checked_at=utcnow(),
            terms_url=self.info.terms_url,
            requires_key=self.info.requires_key,
        )

    def probe_url(self) -> str:
        return self.info.endpoint

    def health(self) -> SourceHealth:
        if self.fixtures is not None:
            return self._health("degraded", "fixture mode (recorded responses)")
        if self.info.requires_key and not self.key:
            return self._health("requires_key", f"set {self.info.key_env} to enable")
        try:
            resp = self.client.get(self.probe_url(), timeout=8.0)
        except httpx.HTTPError as exc:
            return self._health("down", f"{type(exc).__name__}: {str(exc)[:120]}")
        if resp.status_code in (401, 403) and self.info.requires_key:
            return self._health("requires_key", f"HTTP {resp.status_code}: key rejected or missing")
        if resp.status_code >= 400:
            return self._health("down", f"HTTP {resp.status_code}")
        return self._health("ok", f"HTTP {resp.status_code} from {self.probe_url()}")

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
