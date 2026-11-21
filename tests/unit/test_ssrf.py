from __future__ import annotations

import ipaddress

import pytest
from hypothesis import given
from hypothesis import strategies as st

from lureradar.errors import FetchBlockedError
from lureradar.util.ssrf import is_public_ip, validate_url, vet_addresses

BLOCKED = [
    "127.0.0.1", "10.1.2.3", "172.16.5.4", "192.168.1.1", "169.254.169.254", "100.100.100.200",
    "0.0.0.0", "100.64.0.1", "192.0.2.1", "198.51.100.2", "203.0.113.3", "224.0.0.1",
    "240.0.0.1", "255.255.255.255", "198.18.0.1", "::1", "::", "fe80::1", "fc00::1",
    "fd00:ec2::254",
    "::ffff:127.0.0.1", "::ffff:10.0.0.1", "64:ff9b::a9fe:a9fe", "2002:7f00:1::", "2001:db8::1",
    "fe80::1%eth0", "not-an-ip",
]  # fmt: skip
ALLOWED = ["8.8.8.8", "1.1.1.1", "93.184.215.14", "2606:4700:4700::1111", "::ffff:8.8.8.8"]


@pytest.mark.parametrize("ip", BLOCKED)
def test_blocked_addresses(ip: str) -> None:
    assert not is_public_ip(ip)


@pytest.mark.parametrize("ip", ALLOWED)
def test_public_addresses(ip: str) -> None:
    assert is_public_ip(ip)


PRIVATE_NETS = [ipaddress.ip_network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "169.254.0.0/16",
    "100.64.0.0/10", "fc00::/7", "fe80::/10", "::ffff:10.0.0.0/104",
)]  # fmt: skip


@given(st.sampled_from(PRIVATE_NETS), st.integers(min_value=0))
def test_fuzz_private_ranges_never_public(net, offset: int) -> None:  # type: ignore[no-untyped-def]
    ip = net[offset % net.num_addresses]
    assert not is_public_ip(ip)
    assert not is_public_ip(str(ip))


@given(st.ip_addresses(v=4))
def test_fuzz_ipv4_mapped_agrees_with_ipv4(ip: ipaddress.IPv4Address) -> None:
    mapped = ipaddress.IPv6Address(f"::ffff:{ip}")
    assert is_public_ip(mapped) == is_public_ip(ip)


@given(st.ip_addresses())
def test_fuzz_public_implies_global(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if is_public_ip(ip):
        assert ip.is_global and not ip.is_private and not ip.is_loopback


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd", "gopher://a.test/", "ftp://a.test/", "http://user:pw@a.test/",
        "http://a.test:22/", "http://a.test:6379/", "http://localhost/", "http://x.localhost/",
        "http://printer.local/", "http://db.internal/", "http://127.0.0.1/", "http://[::1]/",
        "http://169.254.169.254/latest/meta-data/", "http://0x7f000001/", "http://", "http://a.test:99999/",
    ],
)  # fmt: skip
def test_validate_url_blocks(url: str) -> None:
    with pytest.raises(FetchBlockedError):
        validate_url(url)


def test_validate_url_accepts_and_normalises() -> None:
    safe = validate_url("HTTPS://Example.COM/a/b?c=d")
    assert (safe.scheme, safe.host, safe.port, safe.path) == (
        "https",
        "example.com",
        443,
        "/a/b?c=d",
    )
    assert safe.default_port
    assert validate_url("http://example.com:8080").port == 8080
    assert not validate_url("http://example.com:8443/").default_port


def test_vet_addresses_rejects_any_private() -> None:
    assert vet_addresses("a.test", ["8.8.8.8"]) == ["8.8.8.8"]
    with pytest.raises(FetchBlockedError, match="non-public"):
        vet_addresses("a.test", ["8.8.8.8", "10.0.0.1"])
    with pytest.raises(FetchBlockedError, match="no addresses"):
        vet_addresses("a.test", [])
