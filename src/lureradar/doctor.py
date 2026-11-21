"""``lureradar doctor``: environment checks and live source health."""

from __future__ import annotations

import asyncio
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from lureradar import __version__
from lureradar.config import base_url, cache_dir
from lureradar.util.time import isoformat, utcnow


def _row(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def environment_checks(offline: bool) -> list[dict[str, str]]:
    from lureradar.packs.loader import list_pack_dirs
    from lureradar.packs.validator import validate_pack_dir
    from lureradar.pipeline.snapshot import default_snapshot_path

    rows = [
        _row(
            "python",
            "ok" if sys.version_info >= (3, 11) else "down",
            sys.version.split()[0],
        ),
        _row("lureradar", "ok", __version__),
        _row("base url", "ok", base_url()),
    ]
    packs = list_pack_dirs()
    bad = [p.name for p in packs if not validate_pack_dir(p).ok]
    rows.append(
        _row(
            "packs",
            "ok" if packs and not bad else "down",
            f"{len(packs)} pack(s)" + (f", invalid: {', '.join(bad)}" if bad else ""),
        )
    )
    import tldextract

    rows.append(
        _row("public suffix list", "ok", f"offline snapshot (tldextract {tldextract.__version__})")
    )
    cdir = cache_dir()
    try:
        cdir.mkdir(parents=True, exist_ok=True)
        probe = cdir / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        rows.append(_row("cache dir", "ok", str(cdir)))
    except OSError as exc:
        rows.append(_row("cache dir", "warn", f"{cdir}: {exc}"))
    snap = default_snapshot_path()
    rows.append(
        _row(
            "feed snapshot",
            "ok" if snap.is_file() else "warn",
            str(snap) if snap.is_file() else "none yet: run `lureradar feed pull`",
        )
    )
    rows.append(
        _row(
            "feed signing key",
            "ok" if os.environ.get("LURERADAR_SIGNING_KEY") else "skipped",
            "present" if os.environ.get("LURERADAR_SIGNING_KEY") else "not set (only needed in CI)",
        )
    )
    for mod, purpose in (("resvg_py", "PNG report cards"), ("websockets", "`watch` streaming")):
        present = find_spec(mod) is not None
        rows.append(_row(f"optional: {mod}", "ok" if present else "skipped", purpose))
    if offline:
        rows.append(_row("dns", "skipped", "--offline"))
    else:
        from lureradar.enrich.dns import DnsResolver

        try:
            info = asyncio.run(DnsResolver(lifetime=3).lookup("example.com"))
            rows.append(
                _row(
                    "dns",
                    "ok" if info.resolved else "down",
                    "example.com resolved" if info.resolved else "no answer",
                )
            )
        except Exception as exc:
            rows.append(_row("dns", "down", str(exc)[:120]))
    return rows


def source_checks(offline: bool, fixtures: Path | None) -> list[dict[str, str]]:
    from lureradar.sources import build_sources

    sources = build_sources(fixtures=fixtures)
    if offline and fixtures is None:
        return [_row(s.info.name, "skipped", "--offline") for s in sources]

    def check(src: Any) -> dict[str, str]:
        try:
            h = src.health()
            return _row(src.info.name, h.status, h.detail)
        except Exception as exc:
            return _row(src.info.name, "down", f"{type(exc).__name__}: {str(exc)[:100]}")
        finally:
            src.close()

    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        return list(pool.map(check, sources))


def run_doctor(offline: bool = False, fixtures: Path | None = None) -> dict[str, Any]:
    return {
        "checked_at": isoformat(utcnow()),
        "environment": environment_checks(offline),
        "sources": source_checks(offline, fixtures),
    }
