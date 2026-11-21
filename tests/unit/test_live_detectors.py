"""Live-only detectors, driven by Enrichment objects (no network)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lureradar.detectors.age import detect_domain_age, detect_established_domain, detect_fresh_cert
from lureradar.detectors.base import Context, allow_state, build_indexes
from lureradar.detectors.content import (
    detect_content_lure_patterns,
    extract_features,
    score_features,
)
from lureradar.detectors.hosting import detect_hosting_reputation, reputation_list
from lureradar.detectors.redirects import detect_redirect_chain
from lureradar.detectors.reputation import detect_external_reputation
from lureradar.enrich.types import (
    ContentFeatures,
    Enrichment,
    HttpInfo,
    RdapInfo,
    RedirectHop,
    ReputationHit,
    TlsInfo,
)
from lureradar.models import Signal
from lureradar.packs import load_packs
from lureradar.util.domains import parse_target

NOW = datetime(2026, 11, 21, 12, tzinfo=UTC)
INDEXES = build_indexes(load_packs(["gta6"]))


def ctx(raw: str, e: Enrichment | None) -> Context:
    t = parse_target(raw)
    return Context(target=t, indexes=INDEXES, now=NOW, allow=allow_state(t, INDEXES), enrichment=e)


def rdap(days: float) -> Enrichment:
    return Enrichment(rdap=RdapInfo(registered=NOW - timedelta(days=days)))


def test_domain_age_bands() -> None:
    assert detect_domain_age(ctx("a.test", rdap(1)))[0].weight == 20
    assert detect_domain_age(ctx("a.test", rdap(10)))[0].weight == 15
    assert detect_domain_age(ctx("a.test", rdap(20)))[0].weight == 8
    assert detect_domain_age(ctx("a.test", rdap(400))) == []
    assert detect_domain_age(ctx("a.test", Enrichment())) == []
    assert detect_domain_age(ctx("a.test", None)) == []


def test_fresh_cert() -> None:
    e = Enrichment(first_ct_seen=NOW - timedelta(hours=3))
    assert detect_fresh_cert(ctx("a.test", e))[0].id == "fresh_cert"
    e = Enrichment(tls=TlsInfo(not_before=NOW - timedelta(days=5)))
    assert detect_fresh_cert(ctx("a.test", e)) == []
    assert detect_fresh_cert(ctx("a.test", Enrichment())) == []


def test_established_domain_only_without_strong_signals() -> None:
    old = rdap(800)
    assert detect_established_domain(ctx("a.test", old), [])[0].weight == -15
    strong = [Signal(id="x", weight=20, explanation="x")]
    assert detect_established_domain(ctx("a.test", old), strong) == []
    assert detect_established_domain(ctx("a.test", rdap(10)), []) == []
    assert detect_established_domain(ctx("www.ign.com", old), []) == []


LURE_HTML = """
<html><head><title>GTA 6 PC Download - Free Full Version</title>
<script>alert('never executed')</script></head>
<body>
 <h1>GTA 6 for PC - Download Now</h1>
 <p>Only 37 keys left! Offer ends in 00:14:59</p>
 <p>124,532 downloads today</p>
 <button>Generate your key</button>
 <p>Complete a short survey to unlock the download.</p>
 <p>Please disable your antivirus, it's a false positive.</p>
 <a href="/files/GTA6_Setup.exe">Download</a>
</body></html>
"""


def test_extract_features_from_lure_page() -> None:
    f = extract_features(LURE_HTML, "https://gta6-pc.test/", INDEXES)
    assert f.title and "GTA 6" in f.title
    assert f.campaign_mentions >= 2
    assert f.download_cta and f.survey_gate and f.keygen_ui and f.disable_av
    assert f.social_proof and "countdown timer" in f.scarcity
    assert f.installer_links == ["https://gta6-pc.test/files/GTA6_Setup.exe"]
    assert f.unreleased_claim
    weight, found = score_features(f)
    assert weight == 25 and len(found) >= 5


def test_benign_page_has_no_content_signal() -> None:
    html = "<html><title>GTA 6 review</title><body><p>A great game on PS5.</p></body></html>"
    f = extract_features(html, "https://news.test/", INDEXES)
    assert score_features(f) == (0, [])


def test_generic_download_page_without_campaign_scores_little() -> None:
    html = "<html><body><a href='/vlc.exe'>Download now</a></body></html>"
    weight, _ = score_features(extract_features(html, "https://x.test/", INDEXES))
    assert weight == 0


def test_content_detector() -> None:
    features = extract_features(LURE_HTML, "https://gta6-pc.test/", INDEXES)
    e = Enrichment(http=HttpInfo(final_url="https://gta6-pc.test/", status=200, features=features))
    sig = detect_content_lure_patterns(ctx("gta6-pc.test", e))
    assert sig and sig[0].weight == 25 and sig[0].live
    assert detect_content_lure_patterns(ctx("www.ign.com", e)) == []
    empty = Enrichment(http=HttpInfo(final_url="x", status=200, features=ContentFeatures()))
    assert detect_content_lure_patterns(ctx("a.test", empty)) == []


def test_redirect_chain() -> None:
    hops = [RedirectHop(url="https://bit.ly/x", status=301)]
    e = Enrichment(http=HttpInfo(final_url="https://gta6.test/", status=200, hops=hops))
    sig = detect_redirect_chain(ctx("bit.ly/x", e))
    assert sig and "shortener" in sig[0].explanation
    many = [RedirectHop(url=f"https://a{i}.test/", status=302) for i in range(3)]
    e = Enrichment(http=HttpInfo(final_url="https://z.test/", status=200, hops=many))
    assert detect_redirect_chain(ctx("a0.test", e))[0].weight == 10
    one = [RedirectHop(url="http://a.test/", status=301)]
    e = Enrichment(http=HttpInfo(final_url="https://a.test/", status=200, hops=one))
    assert detect_redirect_chain(ctx("a.test", e)) == []
    assert detect_redirect_chain(ctx("a.test", Enrichment())) == []


def test_external_reputation() -> None:
    e = Enrichment(reputation=[ReputationHit(source="urlhaus", detail="malware_download")])
    sig = detect_external_reputation(ctx("a.test", e))
    assert sig[0].weight == 40 and sig[0].evidence[0].startswith("urlhaus:")
    assert detect_external_reputation(ctx("a.test", Enrichment())) == []


def test_hosting_reputation_list_ships_empty_and_ignores_unsourced() -> None:
    assert reputation_list() == {}
    assert detect_hosting_reputation(ctx("a.test", Enrichment(asn=64496))) == []
