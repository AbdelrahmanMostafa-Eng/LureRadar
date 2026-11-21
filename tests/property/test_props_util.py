"""Property tests: defang/refang round-trip and domain normalisation."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from lureradar.models import TargetKind
from lureradar.util.defang import defang, refang
from lureradar.util.domains import parse_target, to_ascii_host

label = st.from_regex(r"[a-z0-9](?:[a-z0-9-]{0,20}[a-z0-9])?", fullmatch=True)
tld = st.sampled_from(
    ["test", "example", "invalid", "com", "net", "org", "xyz", "co.uk", "github.io"]
)
domain = st.builds(
    lambda labels, t: ".".join([*labels, t]), st.lists(label, min_size=1, max_size=3), tld
)
path = st.from_regex(r"(/[A-Za-z0-9._~-]{0,12}){0,4}", fullmatch=True)
url = st.builds(lambda s, d, p: f"{s}://{d}{p}", st.sampled_from(["http", "https"]), domain, path)


@given(domain)
def test_domain_defang_round_trip(d: str) -> None:
    assert refang(defang(d)) == d
    assert "." not in defang(d).replace("[.]", "")


@given(url)
def test_url_defang_round_trip(u: str) -> None:
    fanged = defang(u)
    assert fanged.startswith(("hxxp://", "hxxps://"))
    assert refang(fanged) == u
    assert defang(fanged) == fanged


@given(domain)
@settings(max_examples=200)
def test_normalisation_is_idempotent_and_case_insensitive(d: str) -> None:
    t = parse_target(d.upper())
    assert t.kind is TargetKind.DOMAIN
    assert t.host == d.lower()
    again = parse_target(t.host)
    assert again.registrable_domain == t.registrable_domain
    assert t.host.endswith(t.registrable_domain)


@given(st.text(alphabet=st.characters(categories=["Ll", "Nd"]), min_size=1, max_size=15))
def test_idna_never_crashes(s: str) -> None:
    host = to_ascii_host(f"{s}.test")
    assert host == "" or host.isascii()
