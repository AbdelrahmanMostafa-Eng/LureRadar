"""Shared fixtures. Tests never touch the network unless marked ``network``."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("LURERADAR_NETWORK_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="network test (set LURERADAR_NETWORK_TESTS=1)")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    for var in (
        "LURERADAR_BASE_URL",
        "LURERADAR_SAFEBROWSING_KEY",
        "LURERADAR_URLHAUS_KEY",
        "LURERADAR_URLSCAN_KEY",
        "LURERADAR_SIGNING_KEY",
        "LURERADAR_NOW",
        "LURERADAR_PACKS_DIR",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LURERADAR_CACHE_DIR", str(tmp_path / "cache"))
    yield


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def now() -> datetime:
    return NOW
