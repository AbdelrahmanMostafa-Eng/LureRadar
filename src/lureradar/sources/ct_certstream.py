"""CertStream-compatible Certificate Transparency stream (for `lureradar watch`).

Public CertStream endpoints come and go, so the websocket URL is configurable
(``LURERADAR_CERTSTREAM_URL``). Batch ``fetch`` yields nothing: streaming is
done by ``lureradar watch`` (needs the optional ``websockets`` package).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime
from typing import Any

import orjson

from lureradar.errors import InvalidTargetError
from lureradar.models import Candidate, SourceHealth
from lureradar.sources.base import HttpSource, SourceInfo
from lureradar.util.domains import normalise_domain
from lureradar.util.time import utcnow


def parse_message(message: dict[str, Any] | bytes | str) -> Iterator[Candidate]:
    """Turn one CertStream ``certificate_update`` message into candidates."""
    data = orjson.loads(message) if isinstance(message, (bytes, str)) else message
    if data.get("message_type") != "certificate_update":
        return
    leaf = (data.get("data") or {}).get("leaf_cert") or {}
    seen_ts = (data.get("data") or {}).get("seen")
    seen = datetime.fromtimestamp(float(seen_ts), tz=utcnow().tzinfo) if seen_ts else utcnow()
    for raw in leaf.get("all_domains") or []:
        name = str(raw).strip().lstrip("*.").lower()
        try:
            domain = normalise_domain(name)
        except InvalidTargetError:
            continue
        yield Candidate(
            domain=domain,
            source="certstream",
            first_seen=seen,
            metadata={"issuer": str((leaf.get("issuer") or {}).get("O", ""))[:120]},
        )


class CertStreamSource(HttpSource):
    info = SourceInfo(
        name="certstream",
        title="CertStream-compatible CT websocket (watch mode)",
        kind="candidates",
        endpoint="wss://certstream.calidog.io/",
        terms_url="https://certstream.calidog.io/",
        requires_key=False,
        rate_limit="push stream; availability varies, endpoint configurable",
        redistribution="derived indicators only",
    )
    fixture_name = "certstream.jsonl"

    def fetch(self, since: datetime) -> Iterable[Candidate]:
        if self.fixtures is None:
            return
        for line in self.fixture_bytes().splitlines():
            if line.strip():
                for cand in parse_message(line):
                    if cand.first_seen >= since:
                        yield cand

    def health(self) -> SourceHealth:
        if self.fixtures is not None:
            return self._health("degraded", "fixture mode (recorded messages)")
        try:
            import websockets  # noqa: F401
        except ImportError:
            return self._health(
                "disabled",
                "stream-only source for `lureradar watch` (pip install 'lureradar[watch]')",
            )
        return self._health("disabled", f"stream-only; endpoint {self.settings.certstream_url}")
