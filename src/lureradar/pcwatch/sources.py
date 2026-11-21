"""PC Watch source adapters: official pages/feeds -> statements -> findings.

All fetches go through the hardened fetcher. A source that returns fewer
game-related items than ``expect_min_items`` is treated as FAILED (the page
structure probably changed): a broken parser must never look like "nothing
announced".
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from urllib.parse import urljoin

import orjson
from selectolax.lexbor import LexborHTMLParser

from lureradar.enrich.http_fetch import FEED_TYPES, JSON_TYPES, TEXT_TYPES, HardenedFetcher
from lureradar.errors import FetchBlockedError
from lureradar.pcwatch.config import PcWatchConfig, WatchSource
from lureradar.pcwatch.evaluate import Statement, _terms_re, evaluate
from lureradar.pcwatch.status import CheckResult, Finding, SourceCheck, Status
from lureradar.util.time import utcnow

MAX_ITEMS = 80
_DOCTYPE = re.compile(rb"<!(?:DOCTYPE|ENTITY)", re.IGNORECASE)


def parse_html_listing(html: str, base_url: str) -> list[Statement]:
    tree = LexborHTMLParser(html)
    out: list[Statement] = []
    for a in tree.css("a[href]"):
        title = " ".join(a.text(separator=" ").split())
        href = (a.attributes.get("href") or "").strip()
        if not title or not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        out.append(Statement(source="", title=title[:300], url=urljoin(base_url, href)))
        if len(out) >= MAX_ITEMS * 4:
            break
    return out


def parse_atom(data: bytes, base_url: str) -> list[Statement]:
    import xml.etree.ElementTree as ET

    if _DOCTYPE.search(data[:4096]):
        raise ValueError("feed declares a DTD/entities: refused")
    root = ET.fromstring(data)  # noqa: S314
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out: list[Statement] = []
    for entry in root.findall("a:entry", ns)[:MAX_ITEMS]:
        title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
        link = entry.find("a:link", ns)
        href = link.get("href", "") if link is not None else ""
        summary = (entry.findtext("a:summary", default="", namespaces=ns) or "").strip()
        out.append(
            Statement(source="", title=title, url=urljoin(base_url, href), text=summary[:2000])
        )
    for item in root.iter("item"):  # RSS 2.0 fallback
        out.append(
            Statement(
                source="",
                title=(item.findtext("title") or "").strip(),
                url=urljoin(base_url, (item.findtext("link") or "").strip()),
                text=(item.findtext("description") or "")[:2000],
            )
        )
    return out


def steam_findings(
    data: bytes, source: WatchSource, config: PcWatchConfig
) -> tuple[int, list[Finding]]:
    payload = orjson.loads(data)
    if not isinstance(payload, dict) or "items" not in payload:
        raise ValueError("unexpected Steam search response (no 'items')")
    names = [n.lower() for n in config.game_terms]
    subject = config.subject.lower()
    findings: list[Finding] = []
    for item in payload["items"]:
        name = " ".join(str(item.get("name", "")).lower().split())
        exact = name == subject or re.match(rf"^{re.escape(subject)}(?:\s*[:\-–].*)?$", name)
        if not exact and name not in names:
            continue
        app_id = item.get("id")
        released = bool(item.get("price"))
        findings.append(
            Finding(
                source=source.id,
                status=Status.RELEASED if released else Status.ANNOUNCED_UNDATED,
                url=f"https://store.steampowered.com/app/{app_id}/",
                title=str(item.get("name", ""))[:200],
                snippet=f"Steam store listing: {item.get('name', '')}"[:120],
            )
        )
    return len(payload["items"]), findings


class PcWatchChecker:
    def __init__(
        self,
        config: PcWatchConfig,
        *,
        fetcher: HardenedFetcher | None = None,
        fixtures: Path | None = None,
    ) -> None:
        self.config = config
        self.fixtures = fixtures
        self.fetcher = fetcher or HardenedFetcher(
            allowed_types=TEXT_TYPES | JSON_TYPES | FEED_TYPES
        )

    async def _body(self, source: WatchSource) -> bytes:
        if self.fixtures is not None:
            ext = {"html": "html", "atom": "atom", "steam_search_json": "json"}[source.format]
            path = self.fixtures / f"{source.id}.{ext}"
            if not path.is_file():
                raise FetchBlockedError(f"fixture {path.name} missing (simulated outage)")
            return path.read_bytes()
        res = await self.fetcher.fetch(str(source.url))
        if res.status != 200:
            raise FetchBlockedError(f"HTTP {res.status}")
        if res.truncated:
            raise FetchBlockedError("response truncated at the size cap")
        return res.body

    async def check_source(self, source: WatchSource) -> SourceCheck:
        base = SourceCheck(id=source.id, name=source.name, kind=source.kind, status="failed",
                           required=source.required)  # fmt: skip
        if source.format == "unsupported":
            base.status = "unsupported"
            base.detail = source.notes or "no stable machine-readable endpoint"
            return base
        try:
            body = await self._body(source)
            if source.format == "steam_search_json":
                seen, findings = steam_findings(body, source, self.config)
            else:
                text = body.decode("utf-8", "replace")
                statements = (
                    parse_html_listing(text, str(source.url))
                    if source.format == "html"
                    else parse_atom(body, str(source.url))
                )
                game_re = _terms_re(self.config.game_terms)
                relevant = [s for s in statements if game_re.search(f"{s.title} {s.text}")]
                seen = len(relevant) if source.format == "html" else len(statements)
                findings = [
                    f for s in relevant if (f := evaluate(s, source, self.config)) is not None
                ]
        except (FetchBlockedError, ValueError, orjson.JSONDecodeError) as exc:
            base.detail = str(exc)[:200]
            return base
        except Exception as exc:
            base.detail = f"{type(exc).__name__}: {str(exc)[:160]}"
            return base
        base.items_seen = seen
        if seen < source.expect_min_items:
            base.detail = (
                f"structure changed? found {seen} relevant item(s), expected >= "
                f"{source.expect_min_items}"
            )
            return base
        base.status = "ok"
        base.findings = findings
        base.detail = f"{seen} relevant item(s), {len(findings)} PC finding(s)"
        return base

    async def run_async(self) -> CheckResult:
        checks = await asyncio.gather(*(self.check_source(s) for s in self.config.sources))
        return CheckResult(checked_at=utcnow(), sources=list(checks))

    def run(self) -> CheckResult:
        return asyncio.run(self.run_async())
