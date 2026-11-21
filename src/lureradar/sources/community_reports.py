"""Community lure reports: validated YAML files under ``data/reports/``.

Flow: "Report a lure" issue form -> `community-report.yml` Action validates and
defangs the submission -> opens a PR adding ``data/reports/<id>.yaml`` ->
maintainer merges -> next pipeline run scores it like any other candidate.
Reports never bypass scoring: a report alone cannot reach the feeds.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from lureradar.config import Settings
from lureradar.errors import InvalidTargetError
from lureradar.models import Candidate, SourceHealth, TargetKind
from lureradar.sources.base import HttpSource, SourceInfo
from lureradar.util.defang import is_defanged
from lureradar.util.domains import parse_target
from lureradar.util.time import utcnow

DEFAULT_DIR = Path("data") / "reports"


class Report(BaseModel):
    model_config = ConfigDict(extra="forbid")

    indicator: str = Field(description="Defanged URL or domain, e.g. hxxps://evil[.]test/x")
    reported: date
    pack: str = "gta6"
    where_seen: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=500)

    @field_validator("indicator")
    @classmethod
    def _defanged(cls, v: str) -> str:
        v = v.strip()
        if not is_defanged(v):
            raise ValueError("indicator must be defanged (hxxps://, [.])")
        target = parse_target(v)
        if target.kind is TargetKind.TEXT:
            raise ValueError("indicator must be a URL or domain")
        return v


def load_reports(directory: Path) -> tuple[list[Report], list[str]]:
    reports: list[Report] = []
    errors: list[str] = []
    for path in sorted(directory.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            reports.append(Report.model_validate(data))
        except ValidationError as exc:
            first = exc.errors()[0]
            loc = ".".join(str(p) for p in first["loc"])
            errors.append(f"{path.name}: {loc}: {first['msg']}")
        except (yaml.YAMLError, InvalidTargetError) as exc:
            errors.append(f"{path.name}: {str(exc).splitlines()[0]}")
    return reports, errors


class CommunityReportsSource(HttpSource):
    info = SourceInfo(
        name="community",
        title="Community lure reports (data/reports/)",
        kind="candidates",
        endpoint="data/reports/",
        terms_url="https://creativecommons.org/publicdomain/zero/1.0/",
        requires_key=False,
        rate_limit="local files",
        redistribution="CC0 (contributors agree in the issue form)",
    )

    def __init__(
        self, settings: Settings | None = None, *, reports_dir: Path | None = None, **kw: object
    ) -> None:
        super().__init__(settings, **kw)  # type: ignore[arg-type]
        if reports_dir is not None:
            self.directory = reports_dir
        elif self.fixtures is not None:
            self.directory = self.fixtures / "reports"
        else:
            self.directory = DEFAULT_DIR

    def fetch(self, since: datetime) -> Iterable[Candidate]:
        reports, _ = load_reports(self.directory)
        for r in reports:
            target = parse_target(r.indicator)
            yield Candidate(
                domain=target.host,
                url=target.url,
                source="community",
                first_seen=datetime(
                    r.reported.year, r.reported.month, r.reported.day, tzinfo=utcnow().tzinfo
                ),
                metadata={"pack": r.pack},
            )

    def health(self) -> SourceHealth:
        if not self.directory.is_dir():
            return self._health(
                "disabled", f"{self.directory} not present (run from the repository)"
            )
        reports, errors = load_reports(self.directory)
        if errors:
            return self._health("degraded", f"{len(errors)} invalid report(s): {errors[0]}")
        return self._health("ok", f"{len(reports)} report(s) in {self.directory}")
