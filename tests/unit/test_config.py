from __future__ import annotations

import re
from pathlib import Path

import pytest

from lureradar import __version__, config

ROOT = Path(__file__).resolve().parents[2]


def test_base_url_default_has_trailing_slash() -> None:
    assert config.base_url() == config.DEFAULT_BASE_URL
    assert config.base_url().endswith("/")


def test_base_url_env_override_and_normalisation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LURERADAR_BASE_URL", "https://lures.example.org/sub")
    assert config.base_url() == "https://lures.example.org/sub/"
    assert config.feed_url("hosts.txt") == "https://lures.example.org/sub/feeds/hosts.txt"
    assert config.site_url("/bot/") == "https://lures.example.org/sub/bot/"


def test_base_url_rejects_relative(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LURERADAR_BASE_URL", "lures.example.org")
    with pytest.raises(ValueError, match="absolute"):
        config.base_url()


def test_user_agent_is_honest() -> None:
    ua = config.user_agent()
    assert ua.startswith(f"LureRadar/{__version__} (+")
    assert ua.endswith("bot/)")


def test_issue_and_dispute_urls_are_defanged() -> None:
    url = config.false_positive_url("https://evil.example.com/x")
    assert url.startswith(config.REPO_URL + "/issues/new?template=false-positive-review.yml")
    assert "evil%5B.%5Dexample" in url  # defanged + percent-encoded


def test_cache_dir_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LURERADAR_CACHE_DIR", str(tmp_path))
    assert config.cache_dir() == tmp_path
    monkeypatch.delenv("LURERADAR_CACHE_DIR")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    if config.os.name != "nt":
        assert config.cache_dir() == tmp_path / "xdg" / "lureradar"


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LURERADAR_URLHAUS_KEY", "k")
    s = config.Settings.from_env()
    assert s.urlhaus_key == "k"
    assert s.safebrowsing_key is None
    assert s.limits.max_redirects == 5
    assert s.limits.max_body_bytes == 1_000_000


def test_astro_config_matches_base_url() -> None:
    """The site's `site` + `base` must equal config.DEFAULT_BASE_URL (single source of truth)."""
    astro = ROOT / "web" / "astro.config.mjs"
    if not astro.exists():
        pytest.skip("web/ not built in this checkout")
    text = astro.read_text(encoding="utf-8")
    m = re.search(r'DEFAULT_BASE_URL\s*=\s*["\']([^"\']+)["\']', text)
    assert m, "web/astro.config.mjs must define DEFAULT_BASE_URL"
    assert m.group(1) == config.DEFAULT_BASE_URL
