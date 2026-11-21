"""Time helpers. LureRadar is UTC-only and timezone-aware everywhere."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta


def utcnow() -> datetime:
    """Current time in UTC. ``LURERADAR_NOW`` (ISO 8601) pins it for reproducible runs."""
    pinned = os.environ.get("LURERADAR_NOW")
    if pinned:
        return parse_iso(pinned)
    return datetime.now(UTC)


def parse_iso(value: str) -> datetime:
    """Parse an ISO 8601 timestamp, assuming UTC when no offset is given."""
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def isoformat(dt: datetime) -> str:
    """Render as ``YYYY-MM-DDTHH:MM:SSZ``."""
    return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def age(then: datetime, now: datetime | None = None) -> timedelta:
    return (now or utcnow()) - then
