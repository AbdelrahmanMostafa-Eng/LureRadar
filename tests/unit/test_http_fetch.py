"""Hardened fetcher: SSRF on every hop, limits, content types, cookies."""

from __future__ import annotations

import asyncio
import gzip
import ipaddress

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from lureradar.config import FetchLimits
from lureradar.enrich.http_fetch import JSON_TYPES, HardenedFetcher, StaticResolver
from lureradar.errors import FetchBlockedError

PUBLIC = "93.184.215.14"
TABLE = {
    "lure.test": [PUBLIC],
    "other.test": ["8.8.8.8"],
    "rebind.test": ["10.0.0.5"],
    "mixed.test": [PUBLIC, "127.0.0.1"],
}


def fetcher(handler, **kw) -> HardenedFetcher:  # type: ignore[no-untyped-def]
    limits = kw.pop("limits", FetchLimits(per_host_interval_s=0))
    return HardenedFetcher(
        limits, resolver=StaticResolver(TABLE), transport=httpx.MockTransport(handler), **kw
    )


def run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


def html(body: str = "<html><title>t</title></html>", **headers: str) -> httpx.Response:
    return httpx.Response(
        200, headers={"content-type": "text/html; charset=utf-8", **headers}, text=body
    )


def test_connection_is_pinned_to_vetted_ip_with_sni_and_ua() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return html()

    res = run(fetcher(handler).fetch("https://lure.test/path?q=1"))
    req = seen[0]
    assert req.url.host == PUBLIC and req.url.path == "/path"
    assert req.headers["host"] == "lure.test"
    assert req.extensions["sni_hostname"] == "lure.test"
    assert req.headers["user-agent"].startswith("LureRadar/")
    assert res.status == 200 and res.final_url == "https://lure.test/path?q=1"
    assert res.peer_ip == PUBLIC and len(res.sha256) == 64


def test_non_default_port_in_host_header() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return html()

    run(fetcher(handler).fetch("http://lure.test:8080/"))
    assert seen[0].headers["host"] == "lure.test:8080" and seen[0].url.port == 8080


def redirect(location: str, code: int = 302) -> httpx.Response:
    return httpx.Response(code, headers={"location": location})


@pytest.mark.parametrize(
    "location",
    [
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://rebind.test/",
        "http://mixed.test/",
        "http://localhost/",
        "gopher://lure.test/",
        "http://lure.test:6379/",
        "file:///etc/passwd",
    ],
)
def test_every_redirect_hop_is_revalidated(location: str) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return redirect(location)

    with pytest.raises(FetchBlockedError):
        run(fetcher(handler).fetch("https://lure.test/"))


@given(st.ip_addresses(v=4).filter(lambda ip: ip.is_private or ip.is_loopback or ip.is_link_local))
@settings(max_examples=40, deadline=None)
def test_fuzz_redirects_to_private_ips_are_blocked(ip: ipaddress.IPv4Address) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return redirect(f"http://{ip}/")

    with pytest.raises(FetchBlockedError):
        run(fetcher(handler).fetch("https://lure.test/"))


def test_redirects_are_followed_and_recorded() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.headers["host"] == "lure.test":
            return redirect("/step2" if req.url.path == "/" else "https://other.test/final", 301)
        return html()

    res = run(fetcher(handler).fetch("https://lure.test/"))
    assert [h.url for h in res.hops] == ["https://lure.test/", "https://lure.test/step2"]
    assert res.final_url == "https://other.test/final"


def test_too_many_redirects() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return redirect(f"/r{len(req.url.path)}")

    with pytest.raises(FetchBlockedError, match="more than 5 redirects"):
        run(fetcher(handler).fetch("https://lure.test/"))


@pytest.mark.parametrize(
    "ctype", ["application/octet-stream", "application/x-msdownload", "application/zip",
              "application/vnd.android.package-archive", "image/png", ""],
)  # fmt: skip
def test_binaries_are_never_downloaded(ctype: str) -> None:
    reads = []

    def handler(req: httpx.Request) -> httpx.Response:
        async def stream():  # type: ignore[no-untyped-def]
            reads.append(1)
            yield b"MZ\x90\x00"

        headers = {"content-type": ctype} if ctype else {}
        return httpx.Response(200, headers=headers, content=stream())

    with pytest.raises(FetchBlockedError, match="never binaries"):
        run(fetcher(handler).fetch("https://lure.test/GTA6_Setup.exe"))
    assert reads == []  # refused before reading a single body byte


def test_attachment_refused_even_if_text() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return html(**{"content-disposition": "attachment; filename=setup.txt"})

    with pytest.raises(FetchBlockedError, match="attachment"):
        run(fetcher(handler).fetch("https://lure.test/"))


def test_body_is_capped() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return html("x" * 3_000_000)

    res = run(fetcher(handler).fetch("https://lure.test/"))
    assert len(res.body) == 1_000_000 and res.truncated


def test_decompression_bomb_is_capped_after_decoding() -> None:
    bomb = gzip.compress(b"A" * 20_000_000)

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, headers={"content-type": "text/html", "content-encoding": "gzip"}, content=bomb
        )

    res = run(fetcher(handler).fetch("https://lure.test/"))
    assert len(res.body) == 1_000_000 and res.truncated


def test_huge_declared_length_refused() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, headers={"content-type": "text/html", "content-length": str(10**9)}, content=b"x"
        )

    with pytest.raises(FetchBlockedError, match="declared size"):
        run(fetcher(handler).fetch("https://lure.test/"))


def test_overall_deadline() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        await asyncio.sleep(2)
        return html()

    f = fetcher(handler, limits=FetchLimits(timeout_s=0.2, per_host_interval_s=0))
    with pytest.raises(FetchBlockedError, match="timed out"):
        run(f.fetch("https://lure.test/"))


def test_cookies_are_never_sent() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.url.path == "/":
            return httpx.Response(
                302, headers={"location": "/next", "set-cookie": "sid=abc; Path=/"}
            )
        return html()

    run(fetcher(handler).fetch("https://lure.test/"))
    assert "cookie" not in seen[1].headers


def test_dns_failure_and_unknown_host() -> None:
    with pytest.raises(FetchBlockedError, match="DNS"):
        run(fetcher(lambda r: html()).fetch("https://unknown.test/"))


def test_http_errors_become_blocked() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(FetchBlockedError, match="ConnectError"):
        run(fetcher(handler).fetch("https://lure.test/"))


def test_json_types_for_rdap() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/rdap+json"}, content=b"{}")

    res = run(fetcher(handler, allowed_types=JSON_TYPES).fetch("https://lure.test/domain/x"))
    assert res.content_type == "application/rdap+json"
    with pytest.raises(FetchBlockedError):
        run(fetcher(handler).fetch("https://lure.test/domain/x"))


def test_ip_literal_targets() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return html()

    assert run(fetcher(handler).fetch(f"http://{PUBLIC}/")).peer_ip == PUBLIC
    with pytest.raises(FetchBlockedError):
        run(fetcher(handler).fetch("http://10.0.0.1/"))


def test_text_decoding() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/plain"}, content="hé".encode())

    assert run(fetcher(handler).fetch("https://lure.test/")).text() == "hé"
