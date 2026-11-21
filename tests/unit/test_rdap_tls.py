from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from lureradar.config import FetchLimits
from lureradar.enrich.http_fetch import JSON_TYPES, HardenedFetcher, StaticResolver
from lureradar.enrich.rdap import RdapClient, parse_rdap
from lureradar.enrich.tls import parse_certificate
from lureradar.errors import FetchBlockedError

FIX = Path(__file__).parents[1] / "fixtures" / "sources"


def test_parse_rdap() -> None:
    info = parse_rdap(
        json.loads((FIX / "rdap_domain.json").read_text()), server="https://rdap.test"
    )
    assert info.registered == datetime(2026, 11, 20, 9, tzinfo=UTC)
    assert info.expires == datetime(2027, 11, 20, 9, tzinfo=UTC)
    assert info.registrar == "Example Registrar LLC"
    assert info.abuse_email == "abuse@registrar.example"
    assert info.status == ["client transfer prohibited"]
    assert parse_rdap({}).registered is None


def _client(tmp_path: Path, handler) -> RdapClient:  # type: ignore[no-untyped-def]
    table = {"data.iana.org": ["8.8.8.8"], "rdap.test": ["8.8.4.4"], "rdap.org": ["1.1.1.1"]}
    fetcher = HardenedFetcher(
        FetchLimits(per_host_interval_s=0), resolver=StaticResolver(table),
        transport=httpx.MockTransport(handler), allowed_types=JSON_TYPES,
    )  # fmt: skip
    return RdapClient(fetcher, cache=tmp_path / "bootstrap.json")


def test_rdap_client_uses_bootstrap_and_caches(tmp_path: Path) -> None:
    calls: list[str] = []
    bootstrap = {"services": [[["test"], ["https://rdap.test/"]]]}
    domain = (FIX / "rdap_domain.json").read_bytes()

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req.headers["host"] + req.url.path)
        body = json.dumps(bootstrap).encode() if req.headers["host"] == "data.iana.org" else domain
        return httpx.Response(200, headers={"content-type": "application/rdap+json"}, content=body)

    client = _client(tmp_path, handler)
    info = asyncio.run(client.lookup("gta6-pc-download.test"))
    assert info.registrar == "Example Registrar LLC" and info.server == "https://rdap.test"
    assert calls == ["data.iana.org/rdap/dns.json", "rdap.test/domain/gta6-pc-download.test"]
    asyncio.run(client.lookup("gta6-pc-download.test"))
    assert calls.count("data.iana.org/rdap/dns.json") == 1  # cached


def test_rdap_falls_back_to_rdap_org(tmp_path: Path) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.headers["host"] == "data.iana.org":
            return httpx.Response(500, headers={"content-type": "text/html"}, content=b"no")
        return httpx.Response(404, headers={"content-type": "application/rdap+json"}, content=b"{}")

    with pytest.raises(FetchBlockedError, match="RDAP 404"):
        asyncio.run(_client(tmp_path, handler).lookup("unknown.test"))


def _self_signed(sans: list[str]) -> bytes:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, sans[0])])
    now = datetime(2026, 11, 21, tzinfo=UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Example CA")]))
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(now - timedelta(hours=2))
        .not_valid_after(now + timedelta(days=90))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(s) for s in sans]), critical=False)
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.DER)


def test_parse_certificate() -> None:
    info = parse_certificate(_self_signed(["gta6-pc.test", "www.gta6-pc.test"]))
    assert info.sans == ["gta6-pc.test", "www.gta6-pc.test"]
    assert info.issuer == "O=Example CA"
    assert info.not_before == datetime(2026, 11, 20, 22, tzinfo=UTC)
