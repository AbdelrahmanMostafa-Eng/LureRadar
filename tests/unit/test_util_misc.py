from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import UTC, datetime, timedelta, timezone

import pytest

from lureradar.util import logging as lr_logging
from lureradar.util.ratelimit import HostRateLimiter, TokenBucket
from lureradar.util.time import age, isoformat, parse_iso, utcnow

NOW = datetime(2026, 11, 21, 12, tzinfo=UTC)


def test_time_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    assert parse_iso("2026-11-21T12:00:00Z") == NOW
    assert parse_iso("2026-11-21T12:00:00") == NOW
    assert parse_iso("2026-11-21T14:00:00+02:00") == NOW
    assert isoformat(NOW.astimezone(timezone(timedelta(hours=5)))) == "2026-11-21T12:00:00Z"
    monkeypatch.setenv("LURERADAR_NOW", "2026-11-21T12:00:00Z")
    assert utcnow() == NOW
    assert age(NOW - timedelta(days=2)) == timedelta(days=2)
    monkeypatch.delenv("LURERADAR_NOW")
    assert utcnow().tzinfo is not None


def test_json_logging(capsys: pytest.CaptureFixture[str]) -> None:
    lr_logging.configure("INFO", json_lines=True)
    log = lr_logging.get_logger("test")
    log.info("hello", extra={"stage": "collect", "count": 3})
    try:
        raise ValueError("boom")
    except ValueError:
        log.exception("failed")
    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert lines[0]["msg"] == "hello" and lines[0]["stage"] == "collect" and lines[0]["count"] == 3
    assert lines[1]["level"] == "error" and "boom" in lines[1]["exc"]
    lr_logging.configure("WARNING")
    assert logging.getLogger("lureradar").level == logging.WARNING


def test_token_bucket() -> None:
    bucket = TokenBucket(rate_per_s=10, burst=2)
    assert bucket.take() == 0 and bucket.take() == 0
    assert bucket.take() > 0
    with pytest.raises(ValueError):
        TokenBucket(0)


def test_host_rate_limiter_spaces_requests() -> None:
    async def run() -> float:
        limiter = HostRateLimiter(interval_s=0.05, concurrency=2)
        start = time.monotonic()
        for _ in range(3):
            await limiter.acquire("a.test")
            limiter.release()
        return time.monotonic() - start

    assert asyncio.run(run()) >= 0.09
    with pytest.raises(ValueError):
        HostRateLimiter(interval_s=-1)
    with pytest.raises(ValueError):
        HostRateLimiter(concurrency=0)
