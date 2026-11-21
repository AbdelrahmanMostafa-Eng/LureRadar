"""Local feed snapshot used by offline ``check`` (populated by ``feed pull``)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from lureradar.config import cache_dir
from lureradar.errors import FeedError
from lureradar.export.jsonfeed import FeedDocument, load
from lureradar.models import Indicator

SNAPSHOT_NAME = "latest.json"


def default_snapshot_path() -> Path:
    return cache_dir() / SNAPSHOT_NAME


@dataclass
class FeedSnapshot:
    generated_at: datetime
    by_domain: dict[str, Indicator]
    path: Path | None = None

    @classmethod
    def from_document(cls, doc: FeedDocument, path: Path | None = None) -> FeedSnapshot:
        return cls(
            generated_at=doc.generated_at,
            by_domain={i.domain.lower(): i for i in doc.indicators if i.status == "active"},
            path=path,
        )

    @classmethod
    def load_default(cls, path: Path | None = None) -> FeedSnapshot | None:
        """Load the cached snapshot if present; never raises for a missing file."""
        target = path or default_snapshot_path()
        if not target.is_file():
            return None
        try:
            return cls.from_document(load(target), target)
        except FeedError:
            return None

    def lookup(self, domain: str) -> Indicator | None:
        return self.by_domain.get(domain.lower()) if domain else None

    def __len__(self) -> int:
        return len(self.by_domain)
