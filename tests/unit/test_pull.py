from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx

from lureradar.config import feed_url
from lureradar.errors import FeedError
from lureradar.export import jsonfeed
from lureradar.export.jsonfeed import FeedDocument
from lureradar.export.signing import generate, sign
from lureradar.pipeline.pull import bundled_pubkey, pull_snapshot
from lureradar.pipeline.snapshot import FeedSnapshot, default_snapshot_path

NOW = datetime(2026, 11, 21, tzinfo=UTC)
DATA = jsonfeed.dumps(FeedDocument(generated_at=NOW))


@respx.mock
def test_pull_verifies_signature(tmp_path: Path) -> None:
    key = generate()
    pub = tmp_path / "k.pub"
    pub.write_text(key.public_file())
    respx.get(feed_url("latest.json")).mock(return_value=httpx.Response(200, content=DATA))
    respx.get(feed_url("latest.json") + ".minisig").mock(
        return_value=httpx.Response(200, text=sign(DATA, key, "latest.json"))
    )
    path, note = pull_snapshot(None, pub)
    assert path == default_snapshot_path() and note == "signature verified"
    assert FeedSnapshot.load_default() is not None


@respx.mock
def test_pull_rejects_bad_signature_and_saves_nothing(tmp_path: Path) -> None:
    good, evil = generate(), generate()
    pub = tmp_path / "k.pub"
    pub.write_text(good.public_file())
    respx.get(feed_url("latest.json")).mock(return_value=httpx.Response(200, content=DATA))
    respx.get(feed_url("latest.json") + ".minisig").mock(
        return_value=httpx.Response(200, text=sign(DATA, evil, "latest.json"))
    )
    with pytest.raises(FeedError, match="FAILED"):
        pull_snapshot(None, pub)
    assert not default_snapshot_path().exists()


@respx.mock
def test_pull_without_key_is_marked_unverified_and_errors() -> None:
    base = "https://mirror.example.org/feeds"
    respx.get(f"{base}/latest.json").mock(return_value=httpx.Response(200, content=DATA))
    respx.get(f"{base}/latest.json.minisig").mock(return_value=httpx.Response(404))
    if bundled_pubkey() is None:
        _, note = pull_snapshot(base)
        assert note.startswith("UNVERIFIED")
    respx.get(f"{base}/latest.json").mock(return_value=httpx.Response(500))
    with pytest.raises(FeedError, match="could not download"):
        pull_snapshot(base)
