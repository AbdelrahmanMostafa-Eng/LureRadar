"""Real sockets: the hardened fetcher against a local HTTP server.

Loopback is normally refused by the SSRF guard; the test-only escape hatch
lets us exercise real redirects, streaming and size limits end to end, and a
second test proves the guard blocks the very same server without it.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from lureradar.config import FetchLimits
from lureradar.enrich.http_fetch import HardenedFetcher, StaticResolver
from lureradar.errors import FetchBlockedError

PAGE = b"<html><title>GTA 6 PC Download</title><body>Download now. Only 5 keys left.</body></html>"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:  # quiet
        pass

    def do_GET(self) -> None:
        if self.path == "/start":
            self.send_response(302)
            self.send_header("Location", "/page")
            self.end_headers()
        elif self.path == "/page":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(PAGE)))
            self.end_headers()
            self.wfile.write(PAGE)
        elif self.path == "/setup.exe":
            self.send_response(200)
            self.send_header("Content-Type", "application/x-msdownload")
            self.end_headers()
            self.wfile.write(b"MZ" * 1000)
        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture
def server() -> Iterator[int]:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv.server_address[1]
    srv.shutdown()


@pytest.mark.slow
def test_real_fetch_follows_redirect(server: int) -> None:
    fetcher = HardenedFetcher(
        FetchLimits(per_host_interval_s=0), resolver=StaticResolver({"lure.test": ["127.0.0.1"]}),
        _allow_private_for_tests=True,
    )  # fmt: skip
    res = asyncio.run(fetcher.fetch(f"http://lure.test:{server}/start"))
    assert res.status == 200 and res.body == PAGE
    assert [h.status for h in res.hops] == [302]
    with pytest.raises(FetchBlockedError, match="never binaries"):
        asyncio.run(fetcher.fetch(f"http://lure.test:{server}/setup.exe"))


@pytest.mark.slow
def test_guard_blocks_loopback_server(server: int) -> None:
    fetcher = HardenedFetcher(resolver=StaticResolver({"lure.test": ["127.0.0.1"]}))
    with pytest.raises(FetchBlockedError):
        asyncio.run(fetcher.fetch("http://lure.test/start"))
    with pytest.raises(FetchBlockedError):
        asyncio.run(fetcher.fetch(f"http://127.0.0.1:{server}/start"))
