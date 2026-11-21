"""Pipeline state: a compact SQLite file cached between runs (Actions cache).

Retention policy (docs/FEEDS.md):
* an indicator not re-sighted for ``STALE_AFTER_DAYS`` (30) becomes ``stale``
  and leaves every feed;
* stale indicators are deleted after ``PURGE_AFTER_DAYS`` (90), so recycled
  domains are never blocklisted forever;
* an indicator whose domain becomes allowlisted is deleted on the next run.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import orjson

from lureradar.config import false_positive_url
from lureradar.models import Indicator, Signal, Tier
from lureradar.scoring import weights
from lureradar.util.time import isoformat, parse_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS indicators (
    domain      TEXT PRIMARY KEY,
    url         TEXT,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    last_scored TEXT NOT NULL,
    score       INTEGER NOT NULL,
    tier        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',
    sources     TEXT NOT NULL DEFAULT '[]',
    packs       TEXT NOT NULL DEFAULT '[]',
    signals     TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_status_tier ON indicators(status, tier);
CREATE TABLE IF NOT EXISTS runs (
    started_at TEXT PRIMARY KEY,
    finished_at TEXT,
    report TEXT
);
"""


class State:
    def __init__(self, path: Path) -> None:
        self.path = path
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self.db:
            yield self.db

    def get(self, domain: str) -> Indicator | None:
        row = self.db.execute("SELECT * FROM indicators WHERE domain = ?", (domain,)).fetchone()
        return _row_to_indicator(row) if row else None

    def upsert(
        self,
        *,
        domain: str,
        url: str | None,
        seen: datetime,
        now: datetime,
        score: int,
        tier: Tier,
        sources: list[str],
        packs: list[str],
        signals: list[Signal],
    ) -> None:
        existing = self.get(domain)
        first_seen = min(existing.first_seen, seen) if existing else seen
        last_seen = max(existing.last_seen, seen) if existing else seen
        merged_sources = sorted(set(sources) | set(existing.sources if existing else []))
        with self.tx() as db:
            db.execute(
                """INSERT INTO indicators
                   (domain, url, first_seen, last_seen, last_scored, score, tier, status,
                    sources, packs, signals)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                   ON CONFLICT(domain) DO UPDATE SET
                     url=COALESCE(excluded.url, indicators.url), first_seen=excluded.first_seen,
                     last_seen=excluded.last_seen, last_scored=excluded.last_scored,
                     score=excluded.score, tier=excluded.tier, status='active',
                     sources=excluded.sources, packs=excluded.packs, signals=excluded.signals""",
                (
                    domain,
                    url,
                    isoformat(first_seen),
                    isoformat(last_seen),
                    isoformat(now),
                    score,
                    tier.value,
                    orjson.dumps(merged_sources).decode(),
                    orjson.dumps(packs).decode(),
                    orjson.dumps([s.model_dump(mode="json") for s in signals]).decode(),
                ),
            )

    def delete(self, domain: str) -> None:
        with self.tx() as db:
            db.execute("DELETE FROM indicators WHERE domain = ?", (domain,))

    def apply_retention(
        self,
        now: datetime,
        stale_after: int = weights.STALE_AFTER_DAYS,
        purge_after: int = weights.PURGE_AFTER_DAYS,
    ) -> tuple[int, int]:
        """Return ``(newly_stale, purged)``."""
        stale_cut = isoformat(now - timedelta(days=stale_after))
        purge_cut = isoformat(now - timedelta(days=purge_after))
        with self.tx() as db:
            stale = db.execute(
                "UPDATE indicators SET status='stale' WHERE status='active' AND last_seen < ?",
                (stale_cut,),
            ).rowcount
            purged = db.execute(
                "DELETE FROM indicators WHERE status='stale' AND last_seen < ?", (purge_cut,)
            ).rowcount
        return stale, purged

    def all(self, status: str | None = None) -> list[Indicator]:
        if status:
            rows = self.db.execute(
                "SELECT * FROM indicators WHERE status = ? ORDER BY domain", (status,)
            )
        else:
            rows = self.db.execute("SELECT * FROM indicators ORDER BY domain")
        return [_row_to_indicator(r) for r in rows]

    def record_run(self, started: datetime, finished: datetime, report: dict[str, object]) -> None:
        with self.tx() as db:
            db.execute(
                "INSERT OR REPLACE INTO runs VALUES (?, ?, ?)",
                (isoformat(started), isoformat(finished), orjson.dumps(report).decode()),
            )

    def last_runs(self, limit: int = 30) -> list[dict[str, object]]:
        rows = self.db.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,))
        return [orjson.loads(r["report"]) for r in rows]


def _row_to_indicator(row: sqlite3.Row) -> Indicator:
    return Indicator(
        domain=row["domain"],
        url=row["url"],
        tier=Tier(row["tier"]),
        score=row["score"],
        first_seen=parse_iso(row["first_seen"]),
        last_seen=parse_iso(row["last_seen"]),
        status=row["status"],
        sources=orjson.loads(row["sources"]),
        packs=orjson.loads(row["packs"]),
        signals=[Signal.model_validate(s) for s in orjson.loads(row["signals"])],
        dispute_url=false_positive_url(row["domain"]),
    )
