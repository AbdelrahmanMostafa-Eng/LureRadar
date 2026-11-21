"""Property tests for scoring: monotonicity and the precision guarantees."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from lureradar.models import Signal, Tier
from lureradar.scoring import tiers
from lureradar.scoring.engine import Engine

ENGINE = Engine(pack_ids=["gta6"])
CATS = ["lexical", "brand", "platform", "infrastructure", "content", "reputation", "text"]


def signals_strategy(min_w: int = -40, max_w: int = 40) -> st.SearchStrategy[list[Signal]]:
    one = st.builds(
        lambda i, w, c: Signal(id=f"s{i}", weight=w, explanation="x", category=c),
        st.integers(0, 50),
        st.integers(min_w, max_w),
        st.sampled_from(CATS),
    )
    return st.lists(one, max_size=8)


@given(signals_strategy(), st.integers(1, 40), st.sampled_from(CATS), st.booleans())
def test_adding_a_malicious_signal_never_lowers_score_or_tier(
    signals: list[Signal], w: int, cat: str, platform: bool
) -> None:
    extra = Signal(id="extra", weight=w, explanation="x", category=cat)  # type: ignore[arg-type]
    before = tiers.total(signals)
    after = tiers.total([*signals, extra])
    assert after >= before
    t0, _ = tiers.decide(before, signals, platform=platform)
    t1, _ = tiers.decide(after, [*signals, extra], platform=platform)
    assert t1 >= t0


@given(st.integers(0, 100))
def test_outlets_are_always_clear(score: int) -> None:
    assert tiers.decide(score, [], outlet=True)[0] is Tier.CLEAR


words = st.sampled_from(
    ["news", "fans", "wiki", "tips", "guide", "map", "music", "art", "photo", "club"]
)
keywords = st.sampled_from(["gta6", "gta-6", "gtavi", "grand-theft-auto-6", "gta-vi"])
tlds = st.sampled_from(["test", "com", "net", "xyz", "top", "online"])


@given(keywords, st.lists(words, max_size=3), tlds)
def test_keyword_without_intent_never_reaches_likely(kw: str, extra: list[str], tld: str) -> None:
    host = "-".join([kw, *extra]) + "." + tld
    v = ENGINE.check(host)
    assert v.tier < Tier.LIKELY, (host, [(s.id, s.weight) for s in v.signals])
    assert not {"keyword_intent_combo", "claims_unreleased_platform"} & {s.id for s in v.signals}


intents = st.sampled_from(["download", "free", "key", "crack", "torrent", "beta", "leak"])


@given(keywords, intents, tlds)
def test_keyword_plus_intent_alone_is_never_likely(kw: str, intent: str, tld: str) -> None:
    v = ENGINE.check(f"{kw}-{intent}.{tld}")
    assert v.tier < Tier.LIKELY
