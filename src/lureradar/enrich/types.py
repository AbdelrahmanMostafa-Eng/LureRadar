"""Enrichment results. Serialisable so fixtures can stand in for live lookups.

We store *features and hashes*, never page copies or binaries.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DnsInfo(BaseModel):
    resolved: bool = False
    a: list[str] = Field(default_factory=list)
    aaaa: list[str] = Field(default_factory=list)
    ns: list[str] = Field(default_factory=list)
    mx: list[str] = Field(default_factory=list)


class RdapInfo(BaseModel):
    registered: datetime | None = None
    expires: datetime | None = None
    registrar: str | None = None
    abuse_email: str | None = None
    status: list[str] = Field(default_factory=list)
    server: str | None = None


class TlsInfo(BaseModel):
    issuer: str | None = None
    not_before: datetime | None = None
    not_after: datetime | None = None
    sans: list[str] = Field(default_factory=list)


class RedirectHop(BaseModel):
    url: str
    status: int


class ContentFeatures(BaseModel):
    """Lure patterns extracted from a page. Values are short, trimmed snippets."""

    title: str | None = None
    campaign_mentions: int = 0
    download_cta: list[str] = Field(default_factory=list)
    survey_gate: list[str] = Field(default_factory=list)
    keygen_ui: list[str] = Field(default_factory=list)
    scarcity: list[str] = Field(default_factory=list)
    installer_links: list[str] = Field(default_factory=list)
    social_proof: list[str] = Field(default_factory=list)
    disable_av: list[str] = Field(default_factory=list)
    unreleased_claim: str | None = None


class HttpInfo(BaseModel):
    final_url: str
    status: int
    hops: list[RedirectHop] = Field(default_factory=list)
    content_type: str | None = None
    body_sha256: str | None = None
    bytes_read: int = 0
    truncated: bool = False
    features: ContentFeatures | None = None
    blocked_reason: str | None = None


class ReputationHit(BaseModel):
    source: str
    detail: str
    url: str | None = None


class Enrichment(BaseModel):
    dns: DnsInfo | None = None
    rdap: RdapInfo | None = None
    tls: TlsInfo | None = None
    http: HttpInfo | None = None
    first_ct_seen: datetime | None = None
    asn: int | None = None
    asn_name: str | None = None
    reputation: list[ReputationHit] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    contacted: list[str] = Field(
        default_factory=list, description="Hosts/services contacted (privacy transparency)"
    )
