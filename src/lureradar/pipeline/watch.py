"""``lureradar watch``: long-running Certificate Transparency stream consumer.

For self-hosters (see docker-compose.yml). Each certificate from a
CertStream-compatible websocket is parsed, run through the same offline
prefilter and scoring as the batch pipeline, stored in the SQLite state, and
reported as a JSON line when it reaches the alert tier. Feeds can be
re-published periodically. ``--replay`` reads recorded messages instead of the
network (tests, demos).
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import AsyncIterator, Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import orjson

from lureradar.errors import InvalidTargetError
from lureradar.export.signing import SigningKey
from lureradar.models import Candidate, Tier
from lureradar.pipeline.publish import publish
from lureradar.pipeline.state import State
from lureradar.scoring.engine import Engine
from lureradar.sources.ct_certstream import parse_message
from lureradar.util.domains import parse_target
from lureradar.util.logging import get_logger
from lureradar.util.time import isoformat, utcnow

log = get_logger("watch")
RELEVANT = frozenset({"lexical", "platform", "brand"})


@dataclass
class WatchConfig:
    url: str
    state_path: Path
    alert_tier: Tier = Tier.SUSPICIOUS
    feeds_out: Path | None = None
    publish_every_s: float = 3600.0
    replay: Path | None = None
    max_messages: int | None = None
    signer: SigningKey | None = None
    stats: dict[str, int] = field(default_factory=lambda: {"messages": 0, "names": 0, "alerts": 0})


async def _websocket_messages(url: str) -> AsyncIterator[bytes | str]:
    try:
        import websockets
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise RuntimeError("`lureradar watch` needs: pip install 'lureradar[watch]'") from exc
    backoff = 1.0
    while True:
        try:
            async with websockets.connect(url, max_size=2**20, ping_interval=30) as ws:
                backoff = 1.0
                async for message in ws:
                    yield message
        except (OSError, websockets.WebSocketException) as exc:
            log.warning("stream disconnected", extra={"error": str(exc)[:200]})
        await asyncio.sleep(backoff + random.random())  # noqa: S311 - jitter only
        backoff = min(backoff * 2, 300.0)


async def _replay_messages(path: Path) -> AsyncIterator[bytes]:
    for line in path.read_bytes().splitlines():
        if line.strip():
            yield line


def process(
    candidates: Iterable[Candidate], engine: Engine, state: State, cfg: WatchConfig
) -> list[dict[str, Any]]:
    """Score candidates; store SUSPICIOUS+ in state; return alerts."""
    alerts: list[dict[str, Any]] = []
    now = utcnow()
    for cand in candidates:
        cfg.stats["names"] += 1
        try:
            target = parse_target(cand.domain)
        except InvalidTargetError:
            continue
        verdict = engine.assess(target)
        if verdict.allowlisted or not any(
            s.weight > 0 and s.category in RELEVANT for s in verdict.signals
        ):
            continue
        if verdict.tier >= Tier.SUSPICIOUS:
            state.upsert(
                domain=target.registrable_domain, url=None, seen=cand.first_seen, now=now,
                score=verdict.score, tier=verdict.tier, sources=["certstream"],
                packs=verdict.packs, signals=verdict.signals,
            )  # fmt: skip
        if verdict.tier >= cfg.alert_tier:
            cfg.stats["alerts"] += 1
            alerts.append(
                {
                    "at": isoformat(now),
                    "indicator": verdict.host,
                    "tier": verdict.tier.value,
                    "score": verdict.score,
                    "signals": [s.id for s in verdict.signals if s.weight > 0],
                }
            )
    return alerts


async def run_watch(cfg: WatchConfig, emit: Callable[[dict[str, Any]], None]) -> dict[str, int]:
    engine = Engine()
    state = State(cfg.state_path)
    source = _replay_messages(cfg.replay) if cfg.replay else _websocket_messages(cfg.url)
    last_publish = time.monotonic()
    try:
        async for message in source:
            cfg.stats["messages"] += 1
            try:
                candidates = list(parse_message(message))
            except (orjson.JSONDecodeError, TypeError, ValueError):
                continue
            for alert in process(candidates, engine, state, cfg):
                emit(alert)
            if cfg.feeds_out and time.monotonic() - last_publish >= cfg.publish_every_s:
                state.apply_retention(utcnow())
                publish(state.all(), cfg.feeds_out, utcnow(), signer=cfg.signer)
                last_publish = time.monotonic()
            if cfg.max_messages and cfg.stats["messages"] >= cfg.max_messages:
                break
        if cfg.feeds_out:
            publish(state.all(), cfg.feeds_out, utcnow(), signer=cfg.signer)
    finally:
        state.close()
    return cfg.stats
