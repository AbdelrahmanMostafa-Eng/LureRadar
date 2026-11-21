"""Smoke tests for the benchmark harness (the full run is `make bench` in CI)."""

from __future__ import annotations

from bench.generators import lure_domains
from bench.harness import read_list
from bench.text_generators import messages

from lureradar.util.domains import parse_target


def test_generators_are_deterministic_and_parseable() -> None:
    a, b = lure_domains(5, seed=7), lure_domains(5, seed=7)
    assert [s.value for s in a] == [s.value for s in b]
    assert {s.pattern for s in a} >= {"typosquat", "homoglyph_idn", "unreleased_platform"}
    for s in a:
        assert parse_target(s.value).host
    assert len(messages(10, seed=1)) == 20


def test_benign_corpus_is_large_and_unique() -> None:
    domains = read_list("benign_domains.txt")
    assert len(domains) >= 500
    assert len(domains) == len(set(domains))
    for d in domains:
        assert parse_target(d).registrable_domain == d, d
    assert all(h.endswith(".test") for h in read_list("benign_hard_negatives.txt"))
