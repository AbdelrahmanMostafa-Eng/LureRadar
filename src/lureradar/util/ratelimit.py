"""Per-host politeness and a global concurrency cap for outbound requests."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict


class HostRateLimiter:
    """Ensure at least ``interval_s`` between requests to the same host.

    Also caps the number of in-flight requests across all hosts.
    """

    def __init__(self, interval_s: float = 1.0, concurrency: int = 8) -> None:
        if interval_s < 0:
            raise ValueError("interval_s must be >= 0")
        if concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        self.interval_s = interval_s
        self._global = asyncio.Semaphore(concurrency)
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._last: dict[str, float] = {}

    async def acquire(self, host: str) -> None:
        await self._global.acquire()
        lock = self._locks[host.lower()]
        async with lock:
            last = self._last.get(host.lower())
            now = time.monotonic()
            if last is not None:
                wait = self.interval_s - (now - last)
                if wait > 0:
                    await asyncio.sleep(wait)
            self._last[host.lower()] = time.monotonic()

    def release(self) -> None:
        self._global.release()


class TokenBucket:
    """Synchronous token bucket used by source adapters (e.g. crt.sh politeness)."""

    def __init__(self, rate_per_s: float, burst: int = 1) -> None:
        if rate_per_s <= 0:
            raise ValueError("rate_per_s must be > 0")
        self.rate = rate_per_s
        self.capacity = max(1, burst)
        self.tokens = float(self.capacity)
        self.updated = time.monotonic()

    def take(self) -> float:
        """Consume a token, returning how long the caller must sleep first."""
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
        self.updated = now
        if self.tokens >= 1:
            self.tokens -= 1
            return 0.0
        deficit = 1 - self.tokens
        self.tokens = 0.0
        return deficit / self.rate
