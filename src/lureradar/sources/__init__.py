"""Source adapters: Certificate Transparency, public feeds, reputation APIs, community reports."""

from __future__ import annotations

from pathlib import Path

from lureradar.config import Settings
from lureradar.sources.base import HttpSource, ReputationLookup, Source, SourceInfo


def build_sources(
    settings: Settings | None = None,
    *,
    fixtures: Path | None = None,
    keywords: list[str] | None = None,
    reports_dir: Path | None = None,
) -> list[HttpSource]:
    """Every adapter, in pipeline order. Unusable ones report it via health()."""
    from lureradar.sources.community_reports import CommunityReportsSource
    from lureradar.sources.ct_certstream import CertStreamSource
    from lureradar.sources.ct_crtsh import CrtShSource
    from lureradar.sources.openphish import OpenPhishSource
    from lureradar.sources.safebrowsing import SafeBrowsingSource
    from lureradar.sources.urlhaus import UrlhausSource
    from lureradar.sources.urlscan import UrlscanSource

    s = settings or Settings.from_env()
    return [
        CrtShSource(s, fixtures=fixtures, keywords=keywords),
        OpenPhishSource(s, fixtures=fixtures),
        UrlhausSource(s, fixtures=fixtures),
        UrlscanSource(s, fixtures=fixtures, keywords=keywords),
        SafeBrowsingSource(s, fixtures=fixtures),
        CommunityReportsSource(s, fixtures=fixtures, reports_dir=reports_dir),
        CertStreamSource(s, fixtures=fixtures),
    ]


__all__ = ["HttpSource", "ReputationLookup", "Source", "SourceInfo", "build_sources"]
