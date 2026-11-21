"""PC Watch outputs: pc-watch.json, pc-watch.atom (Atom 1.0) and the badge."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from xml.sax.saxutils import escape

import orjson

from lureradar.config import feed_url, site_url
from lureradar.pcwatch.status import PcWatchState, Status, honest_sentence
from lureradar.theme import AMBER, INFO, MUTED, RADAR
from lureradar.util.time import isoformat

BADGE_COLORS = {
    Status.NOT_ANNOUNCED: RADAR,
    Status.ANNOUNCED_UNDATED: AMBER,
    Status.ANNOUNCED_DATED: AMBER,
    Status.RELEASED: INFO,
    Status.UNKNOWN: MUTED,
}
BADGE_TEXT = {
    Status.NOT_ANNOUNCED: "not announced",
    Status.ANNOUNCED_UNDATED: "announced",
    Status.ANNOUNCED_DATED: "announced (dated)",
    Status.RELEASED: "released",
    Status.UNKNOWN: "unknown",
}


def to_json(state: PcWatchState) -> bytes:
    data = state.model_dump(mode="json")
    data["answer"] = honest_sentence(state)
    return orjson.dumps(data, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS) + b"\n"


def badge(state: PcWatchState) -> bytes:
    checked = state.last_checked.strftime("%Y-%m-%d %H:%M UTC") if state.last_checked else "never"
    message = f"{BADGE_TEXT[state.status]} · checked {checked}"
    payload = {
        "schemaVersion": 1,
        "label": "PC version",
        "message": message,
        "color": BADGE_COLORS[state.status].lstrip("#"),
    }
    return orjson.dumps(payload) + b"\n"


def _iso(dt: datetime) -> str:
    return isoformat(dt)


def to_atom(state: PcWatchState) -> str:
    page = site_url("pc-watch/")
    updated = state.last_changed or state.generated_at
    entries = []
    status_id = f"tag:lureradar,2026:pc-watch:status:{state.confirmed_status.value}:{_iso(updated)}"
    entries.append(
        f"""  <entry>
    <id>{escape(status_id)}</id>
    <title>{escape(state.headline)}</title>
    <updated>{_iso(updated)}</updated>
    <link rel="alternate" href="{escape(page)}"/>
    <summary>{escape(honest_sentence(state))}</summary>
  </entry>"""
    )
    for e in state.timeline:
        when = datetime(e.date.year, e.date.month, e.date.day, tzinfo=UTC)
        entries.append(
            f"""  <entry>
    <id>{escape(str(e.url))}</id>
    <title>{escape(e.title)}</title>
    <updated>{_iso(when)}</updated>
    <link rel="alternate" href="{escape(str(e.url))}"/>
    <summary>{escape(e.paraphrase + " " + e.meaning)}</summary>
  </entry>"""
        )
    feed_updated = max(
        [updated]
        + [datetime(e.date.year, e.date.month, e.date.day, tzinfo=UTC) for e in state.timeline]
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom">\n'
        f"  <id>tag:lureradar,2026:pc-watch</id>\n"
        f"  <title>LureRadar PC Watch: is {escape(state.subject)} coming to PC?</title>\n"
        f"  <subtitle>{escape(state.disclaimer)}</subtitle>\n"
        f"  <updated>{_iso(feed_updated)}</updated>\n"
        f'  <link rel="self" href="{escape(feed_url("pc-watch.atom"))}"/>\n'
        f'  <link rel="alternate" href="{escape(page)}"/>\n'
        "  <author><name>LureRadar</name></author>\n" + "\n".join(entries) + "\n</feed>\n"
    )


def write_outputs(state: PcWatchState, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "pc-watch.json": to_json(state),
        "pc-watch.atom": to_atom(state).encode(),
        "shields-pc-watch.json": badge(state),
    }
    paths = []
    for name, data in files.items():
        path = out_dir / name
        path.write_bytes(data)
        paths.append(path)
    return paths


def load_state(path: Path) -> PcWatchState | None:
    if not path.is_file():
        return None
    data = orjson.loads(path.read_bytes())
    data.pop("answer", None)
    return PcWatchState.model_validate(data)
