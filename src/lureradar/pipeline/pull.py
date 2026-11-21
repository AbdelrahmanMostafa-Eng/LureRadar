"""``lureradar feed pull``: fetch the published snapshot for offline checks."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import httpx

from lureradar.config import feed_url, user_agent
from lureradar.errors import FeedError, SignatureError
from lureradar.export import jsonfeed
from lureradar.export.signing import load_public, verify
from lureradar.pipeline.snapshot import default_snapshot_path


def bundled_pubkey() -> str | None:
    try:
        text = resources.files("lureradar.data").joinpath("lureradar-feed.pub").read_text("utf-8")
    except FileNotFoundError:
        return None
    return text if "minisign public key" in text else None


def pull_snapshot(base: str | None = None, pubkey: Path | None = None) -> tuple[Path, str]:
    url = (base.rstrip("/") + "/latest.json") if base else feed_url("latest.json")
    headers = {"User-Agent": user_agent()}
    try:
        with httpx.Client(timeout=30.0, headers=headers, follow_redirects=True) as client:
            data = client.get(url).raise_for_status().content
            sig_resp = client.get(url + ".minisig")
    except httpx.HTTPError as exc:
        raise FeedError(f"could not download {url}: {exc}") from exc
    jsonfeed.loads(data)  # schema validation before anything is saved
    key_text = pubkey.read_text(encoding="utf-8") if pubkey else bundled_pubkey()
    if sig_resp.status_code == 200 and key_text:
        try:
            verify(data, sig_resp.text, load_public(key_text))
        except SignatureError as exc:
            raise FeedError(f"signature verification FAILED: {exc}; snapshot not saved") from exc
        note = "signature verified"
    elif key_text:
        raise FeedError("no signature published next to the feed; snapshot not saved")
    else:
        note = "UNVERIFIED: no public key available (pass --pubkey)"
    path = default_snapshot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path, note
