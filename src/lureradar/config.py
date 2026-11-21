"""Central configuration.

Every public URL LureRadar emits is derived from :data:`BASE_URL`. To move the
project to a custom domain, change ``DEFAULT_BASE_URL`` here, ``site``/``base``
in ``web/astro.config.mjs`` (a test keeps both in sync), and add a ``CNAME``.
The value can also be overridden at runtime with ``LURERADAR_BASE_URL``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from lureradar import __version__

#: The canonical public site. Sub-path deployments (GitHub Pages project sites)
#: are supported: keep the trailing slash.
DEFAULT_BASE_URL = "https://abdelrahmanmostafa-eng.github.io/LureRadar/"

#: GitHub ``owner/name`` of the canonical repository.
REPO = "AbdelrahmanMostafa-Eng/LureRadar"
REPO_URL = f"https://github.com/{REPO}"

#: Version of the JSON emitted by ``lureradar check --json``.
VERDICT_SCHEMA_VERSION = "1.0"
#: Version of the public feed documents (``latest.json`` and friends).
FEED_SCHEMA_VERSION = "1.0"


def _normalise_base(url: str) -> str:
    url = url.strip()
    if not url.startswith(("https://", "http://")):
        raise ValueError(f"BASE_URL must be an absolute http(s) URL, got {url!r}")
    return url if url.endswith("/") else url + "/"


def base_url() -> str:
    """Return the configured base URL (always ends with ``/``)."""
    return _normalise_base(os.environ.get("LURERADAR_BASE_URL", DEFAULT_BASE_URL))


def site_url(path: str = "") -> str:
    """Join a site-relative path onto :func:`base_url`."""
    return base_url() + path.lstrip("/")


def feed_url(name: str) -> str:
    """URL of a published feed file, e.g. ``feed_url("hosts.txt")``."""
    return site_url(f"feeds/{name}")


def bot_info_url() -> str:
    return site_url("bot/")


def user_agent() -> str:
    """Honest, identifiable User-Agent for every outbound request."""
    return f"LureRadar/{__version__} (+{bot_info_url()})"


def issue_url(template: str, title: str | None = None) -> str:
    """Link to a GitHub issue form, optionally pre-filling the title."""
    from urllib.parse import quote

    url = f"{REPO_URL}/issues/new?template={template}"
    if title:
        url += f"&title={quote(title)}"
    return url


def false_positive_url(indicator: str) -> str:
    """Dispute link attached to every feed entry (indicator is shown defanged)."""
    from lureradar.util.defang import defang

    return issue_url("false-positive-review.yml", f"[FP] {defang(indicator)}")


def cache_dir() -> Path:
    """Per-user cache directory (feed snapshots, RDAP bootstrap)."""
    env = os.environ.get("LURERADAR_CACHE_DIR")
    if env:
        return Path(env)
    if os.name == "nt":  # pragma: no cover - exercised on Windows CI
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return root / "lureradar" / "cache"
    xdg = os.environ.get("XDG_CACHE_HOME")
    return (Path(xdg) if xdg else Path.home() / ".cache") / "lureradar"


@dataclass(frozen=True, slots=True)
class FetchLimits:
    """Hard limits for the hardened HTTP fetcher (see docs/THREAT_MODEL.md)."""

    timeout_s: float = 10.0
    max_redirects: int = 5
    max_body_bytes: int = 1_000_000
    per_host_interval_s: float = 1.0
    global_concurrency: int = 8


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings resolved from the environment."""

    base_url: str = field(default_factory=base_url)
    safebrowsing_key: str | None = field(
        default_factory=lambda: os.environ.get("LURERADAR_SAFEBROWSING_KEY") or None
    )
    urlhaus_key: str | None = field(
        default_factory=lambda: os.environ.get("LURERADAR_URLHAUS_KEY") or None
    )
    urlscan_key: str | None = field(
        default_factory=lambda: os.environ.get("LURERADAR_URLSCAN_KEY") or None
    )
    certstream_url: str = field(
        default_factory=lambda: os.environ.get(
            "LURERADAR_CERTSTREAM_URL", "wss://certstream.calidog.io/"
        )
    )
    limits: FetchLimits = field(default_factory=FetchLimits)

    @classmethod
    def from_env(cls) -> Settings:
        return cls()
