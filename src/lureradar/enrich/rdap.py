"""RDAP enrichment: registration date, registrar and abuse contact.

Server discovery uses the IANA bootstrap file (cached for 7 days) and falls
back to the rdap.org redirector. All requests go through the hardened fetcher.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

import orjson

from lureradar.config import cache_dir
from lureradar.enrich.http_fetch import JSON_TYPES, HardenedFetcher
from lureradar.enrich.types import RdapInfo
from lureradar.errors import FetchBlockedError
from lureradar.util.time import parse_iso

BOOTSTRAP_URL = "https://data.iana.org/rdap/dns.json"
FALLBACK = "https://rdap.org/domain/"
BOOTSTRAP_TTL_S = 7 * 24 * 3600


def _vcard_value(entity: dict[str, Any], field: str) -> str | None:
    card = entity.get("vcardArray")
    if not (isinstance(card, list) and len(card) == 2 and isinstance(card[1], list)):
        return None
    for prop in card[1]:
        if isinstance(prop, list) and len(prop) >= 4 and prop[0] == field:
            value = prop[3]
            return str(value[0] if isinstance(value, list) and value else value) or None
    return None


def _walk_entities(entities: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ent in entities or []:
        if isinstance(ent, dict):
            out.append(ent)
            out.extend(_walk_entities(ent.get("entities") or []))
    return out


def parse_rdap(data: dict[str, Any], server: str | None = None) -> RdapInfo:
    """Extract the fields LureRadar uses from an RDAP domain response."""
    info = RdapInfo(server=server)
    for event in data.get("events") or []:
        action = str(event.get("eventAction", "")).lower()
        try:
            when: datetime | None = parse_iso(str(event.get("eventDate", "")))
        except ValueError:
            when = None
        if action == "registration":
            info.registered = when
        elif action == "expiration":
            info.expires = when
    info.status = [str(s) for s in data.get("status") or []]
    for ent in _walk_entities(data.get("entities") or []):
        roles = [str(r).lower() for r in ent.get("roles") or []]
        if "registrar" in roles and not info.registrar:
            info.registrar = _vcard_value(ent, "fn")
        if "abuse" in roles and not info.abuse_email:
            email = _vcard_value(ent, "email")
            if email and "@" in email:
                info.abuse_email = email
    return info


class RdapClient:
    def __init__(self, fetcher: HardenedFetcher | None = None, cache: Path | None = None) -> None:
        self.fetcher = fetcher or HardenedFetcher(allowed_types=JSON_TYPES)
        self.cache = cache or cache_dir() / "rdap-bootstrap.json"

    async def _bootstrap(self) -> dict[str, str]:
        data: dict[str, Any] | None = None
        if self.cache.is_file() and time.time() - self.cache.stat().st_mtime < BOOTSTRAP_TTL_S:
            data = orjson.loads(self.cache.read_bytes())
        else:
            try:
                res = await self.fetcher.fetch(BOOTSTRAP_URL)
                data = orjson.loads(res.body)
                self.cache.parent.mkdir(parents=True, exist_ok=True)
                self.cache.write_bytes(res.body)
            except (FetchBlockedError, orjson.JSONDecodeError):
                data = None
        table: dict[str, str] = {}
        for entry in (data or {}).get("services", []):
            if isinstance(entry, list) and len(entry) == 2 and entry[1]:
                for tld in entry[0]:
                    table[str(tld).lower()] = str(entry[1][0])
        return table

    async def lookup(self, registrable: str) -> RdapInfo:
        tld = registrable.rsplit(".", 1)[-1].lower()
        base = (await self._bootstrap()).get(tld)
        url = (base.rstrip("/") + "/domain/" + registrable) if base else FALLBACK + registrable
        res = await self.fetcher.fetch(url)
        if res.status != 200:
            raise FetchBlockedError(f"RDAP {res.status} for {registrable}")
        try:
            data = orjson.loads(res.body)
        except orjson.JSONDecodeError as exc:
            raise FetchBlockedError("RDAP response is not JSON") from exc
        return parse_rdap(data, server=res.final_url.split("/domain/")[0])
