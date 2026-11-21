"""Write every public feed file, stats, badges, checksums and signatures."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import orjson

from lureradar.config import FEED_SCHEMA_VERSION
from lureradar.export import abp, csvfeed, hosts, jsonfeed, rpz, stix
from lureradar.export.jsonfeed import FeedDocument
from lureradar.export.signing import SigningKey, sha256sums, sign
from lureradar.models import Indicator, Tier
from lureradar.theme import AMBER, DANGER, INFO, RADAR
from lureradar.util.time import isoformat

FEED_FILES = (
    "latest.json",
    "all.json",
    "hosts.txt",
    "domains.txt",
    "adguard.txt",
    "rpz.zone",
    "stix.json",
    "indicators.csv",
    "stats.json",
)


def build_document(indicators: list[Indicator], now: datetime, min_tier: Tier) -> FeedDocument:
    chosen = [i for i in indicators if i.status == "active" and i.tier >= min_tier]
    return FeedDocument(generated_at=now, min_tier=min_tier, indicators=chosen)


def _shield(label: str, message: str, color: str) -> dict[str, Any]:
    return {"schemaVersion": 1, "label": label, "message": message, "color": color.lstrip("#")}


def build_stats(
    indicators: list[Indicator],
    now: datetime,
    run: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    active = [i for i in indicators if i.status == "active"]
    listed = [i for i in active if i.tier >= Tier.LIKELY]
    day = now - timedelta(hours=24)
    week = now - timedelta(days=7)
    signal_counts: Counter[str] = Counter(s.id for i in listed for s in i.signals if s.weight > 0)
    return {
        "schema_version": FEED_SCHEMA_VERSION,
        "generated_at": isoformat(now),
        "count": len(listed),
        "active_listed": len(listed),
        "suspicious": sum(1 for i in active if i.tier is Tier.SUSPICIOUS),
        "stale": sum(1 for i in indicators if i.status == "stale"),
        "by_tier": {
            t.value: sum(1 for i in active if i.tier is t) for t in Tier if t is not Tier.CLEAR
        },
        "new_24h": sum(1 for i in listed if i.first_seen >= day),
        "new_7d": sum(1 for i in listed if i.first_seen >= week),
        "by_source": dict(Counter(s for i in listed for s in i.sources).most_common()),
        "by_pack": dict(Counter(p for i in listed for p in i.packs).most_common()),
        "top_signals": [{"id": k, "count": v} for k, v in signal_counts.most_common(8)],
        "last_run": run or {},
        "history": history or [],
    }


def publish(
    indicators: list[Indicator],
    out_dir: Path,
    now: datetime,
    *,
    signer: SigningKey | None = None,
    run: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
    fpr: float | None = None,
) -> list[Path]:
    """Write all feed files into ``out_dir``; return the written paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = build_document(indicators, now, Tier.LIKELY)
    everything = build_document(indicators, now, Tier.SUSPICIOUS)
    stats = build_stats(indicators, now, run, history)
    contents: dict[str, bytes] = {
        "latest.json": jsonfeed.dumps(doc),
        "all.json": jsonfeed.dumps(everything),
        "hosts.txt": hosts.to_hosts(doc).encode(),
        "domains.txt": hosts.to_domains(doc).encode(),
        "adguard.txt": abp.to_abp(doc).encode(),
        "rpz.zone": rpz.to_rpz(doc).encode(),
        "stix.json": stix.to_stix(doc).encode(),
        "indicators.csv": csvfeed.to_csv(doc).encode(),
        "stats.json": orjson.dumps(stats, option=orjson.OPT_INDENT_2) + b"\n",
    }
    new24 = stats["new_24h"]
    badges = {
        "shields-detections-24h.json": _shield(
            "detections (24h)", str(new24), DANGER if new24 else RADAR
        ),
        "shields-active.json": _shield("active indicators", str(stats["active_listed"]), AMBER),
        "shields-updated.json": _shield("feed updated", now.strftime("%Y-%m-%d %H:%M UTC"), INFO),
    }
    if fpr is not None:
        badges["shields-fpr.json"] = _shield(
            "FPR on benign corpus", f"{fpr:.1%}", RADAR if fpr == 0 else AMBER
        )
    for name, badge in badges.items():
        contents[name] = orjson.dumps(badge) + b"\n"

    written: list[Path] = []
    for name, data in contents.items():
        path = out_dir / name
        path.write_bytes(data)
        written.append(path)
    if signer is not None:
        ts = int(now.timestamp())
        for name in FEED_FILES:
            sig = out_dir / f"{name}.minisig"
            sig.write_text(sign(contents[name], signer, name, ts), encoding="utf-8")
            written.append(sig)
    sums = out_dir / "SHA256SUMS"
    sums.write_text(sha256sums([out_dir / n for n in contents], out_dir), encoding="utf-8")
    written.append(sums)
    if signer is not None:
        sig = out_dir / "SHA256SUMS.minisig"
        sig.write_text(sign(sums.read_bytes(), signer, "SHA256SUMS", int(now.timestamp())), "utf-8")
        written.append(sig)
    return written
