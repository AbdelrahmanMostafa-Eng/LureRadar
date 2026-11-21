"""Exporter outputs always parse back to exactly the safe input domains."""

from __future__ import annotations

from datetime import UTC, datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from lureradar.export import abp, hosts, rpz
from lureradar.export.common import safe_host
from lureradar.export.jsonfeed import FeedDocument
from lureradar.models import Indicator, Tier

NOW = datetime(2026, 11, 21, tzinfo=UTC)
label = st.from_regex(r"[a-z0-9](?:[a-z0-9-]{0,15}[a-z0-9])?", fullmatch=True)
domain = st.builds(lambda ls, t: ".".join([*ls, t]), st.lists(label, min_size=1, max_size=3),
                   st.sampled_from(["test", "example", "xyz", "co.uk"]))  # fmt: skip
junk = st.text(min_size=1, max_size=30)


@given(st.lists(st.one_of(domain, junk), max_size=25))
@settings(max_examples=150)
def test_exporters_parse_back(domains: list[str]) -> None:
    doc = FeedDocument(
        generated_at=NOW,
        indicators=[
            Indicator(domain=d, tier=Tier.LIKELY, score=80, first_seen=NOW, last_seen=NOW)
            for d in domains
        ],
    )
    expected = sorted({h for d in domains if (h := safe_host(d))})
    assert hosts.parse_hosts(hosts.to_hosts(doc)) == expected
    assert hosts.parse_domains(hosts.to_domains(doc)) == expected
    assert abp.parse_abp(abp.to_abp(doc)) == expected
    assert rpz.parse_rpz(rpz.to_rpz(doc)) == expected
