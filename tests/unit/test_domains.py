from __future__ import annotations

import pytest

from lureradar.errors import InvalidTargetError
from lureradar.models import TargetKind
from lureradar.util.domains import (
    find_urls,
    has_known_suffix,
    normalise_domain,
    parse_target,
    registrable_domain,
    split_host,
    to_ascii_host,
    to_unicode_host,
    tokenize,
)


def test_demo_target_parses_offline() -> None:
    t = parse_target("https://rockstar-gta6-pc-download[.]test/free-key")
    assert t.kind is TargetKind.URL
    assert t.host == "rockstar-gta6-pc-download.test"
    assert t.registrable_domain == "rockstar-gta6-pc-download.test"
    assert t.domain_label == "rockstar-gta6-pc-download"
    assert t.suffix == "test"
    assert t.path == "/free-key"
    assert t.url == "https://rockstar-gta6-pc-download.test/free-key"


@pytest.mark.parametrize(
    ("raw", "host", "registrable", "sub"),
    [
        ("a.b.co.uk", "a.b.co.uk", "b.co.uk", "a"),
        ("foo.github.io", "foo.github.io", "foo.github.io", ""),
        ("x.y.weebly.com", "x.y.weebly.com", "y.weebly.com", "x"),
        ("http://steam.example@evil.example/", "evil.example", "evil.example", ""),
        ("WWW.Example.COM.", "www.example.com", "example.com", "www"),
        ("http://evil.test:8080/path", "evil.test", "evil.test", ""),
    ],
)
def test_parse_hosts(raw: str, host: str, registrable: str, sub: str) -> None:
    t = parse_target(raw)
    assert t.host == host
    assert t.registrable_domain == registrable
    assert t.subdomain == sub


def test_kinds() -> None:
    assert parse_target("gta6-free.test").kind is TargetKind.DOMAIN
    assert parse_target("gta6-free.test/x").kind is TargetKind.URL
    assert parse_target("free gta 6 keys").kind is TargetKind.TEXT
    assert parse_target("gta6").kind is TargetKind.TEXT


def test_ip_targets() -> None:
    t = parse_target("http://[2001:db8::1]:8080/a")
    assert t.is_ip and t.host == "2001:db8::1"
    assert t.url == "http://[2001:db8::1]:8080/a"
    assert parse_target("192.0.2.10").is_ip


def test_idn_round_trip() -> None:
    ascii_host = to_ascii_host("rоckstar.test")
    assert ascii_host.startswith("xn--")
    assert to_unicode_host(ascii_host) == "rоckstar.test"
    t = parse_target("rоckstar.test")
    assert t.host == ascii_host and t.unicode_host == "rоckstar.test"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "javascript://x.test",
        "http://",
        "http://exa mple.test/x y",
        "http://a.test:99999/",
    ],
)
def test_invalid_targets(raw: str) -> None:
    with pytest.raises(InvalidTargetError):
        t = parse_target(raw)
        if t.kind is TargetKind.TEXT:  # "exa mple" style input is text, which is fine
            raise InvalidTargetError("text")


def test_too_long() -> None:
    with pytest.raises(InvalidTargetError, match="too long"):
        parse_target("a" * 20_001)


def test_helpers() -> None:
    assert registrable_domain("https://a.b.example.com/x") == "example.com"
    assert normalise_domain("HXXPS://Evil[.]Test/") == "evil.test"
    with pytest.raises(InvalidTargetError):
        normalise_domain("not a domain")
    assert tokenize("Free-GTA6_pc.Download") == ["free", "gta6", "pc", "download"]
    assert split_host("localhost") == ("", "localhost", "", False)
    assert has_known_suffix("a.test") and has_known_suffix("a.com")
    assert not has_known_suffix("setup.exe")
    assert to_ascii_host("") == ""


def test_find_urls() -> None:
    text = "see https://a.test/x, free-key.test and setup.exe or e.g. v1.2 (b.example.com)."
    assert find_urls(text) == ["https://a.test/x", "free-key.test", "b.example.com"]
