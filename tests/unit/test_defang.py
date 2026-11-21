from __future__ import annotations

import pytest

from lureradar.util.defang import defang, defang_text, is_defanged, refang


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://evil.example.com/x", "hxxps://evil[.]example[.]com/x"),
        ("http://a.test", "hxxp://a[.]test"),
        ("HTTPS://A.TEST/", "HXXPS://A[.]TEST/"),
        ("ftp://files.example.org/a", "fxp://files[.]example[.]org/a"),
        ("evil.example.com", "evil[.]example[.]com"),
        ("evil.example.com/a.b", "evil[.]example[.]com/a.b"),
        ("https://user@evil.example/a?b=c.d#e", "hxxps://user[@]evil[.]example/a?b=c.d#e"),
        ("", ""),
    ],
)
def test_defang(raw: str, expected: str) -> None:
    assert defang(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("hxxps://evil[.]example[.]com/x", "https://evil.example.com/x"),
        ("hXXp://evil(.)test", "http://evil.test"),
        ("evil[dot]example{.}com", "evil.example.com"),
        ("hxxps[:]//evil[.]test", "https://evil.test"),
        ("https[://]evil[.]test", "https://evil.test"),
        ("user[@]evil[.]test", "user@evil.test"),
        ("evil\\.test", "evil.test"),
        ("  rockstar-gta6-pc-download[.]test/free-key ", "rockstar-gta6-pc-download.test/free-key"),
        ("fxp://files[.]example[.]org", "ftp://files.example.org"),
    ],
)
def test_refang(raw: str, expected: str) -> None:
    assert refang(raw) == expected


def test_defang_is_idempotent() -> None:
    once = defang("https://a.b.example/c")
    assert defang(once) == once


def test_defang_text_only_touches_real_hosts() -> None:
    text = "get it at free-key.test, or https://x.example.com/a. setup.exe e.g. v1.2.3"
    out = defang_text(text)
    assert "free-key[.]test," in out
    assert "hxxps://x[.]example[.]com/a." in out
    assert "setup.exe" in out and "e.g." in out and "v1.2.3" in out


def test_is_defanged() -> None:
    assert is_defanged("evil[.]test")
    assert is_defanged("hxxps://x")
    assert not is_defanged("https://evil.test")
