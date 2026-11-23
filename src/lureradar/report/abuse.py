"""Ready-to-send abuse report drafts (never sent automatically)."""

from __future__ import annotations

from dataclasses import dataclass

from lureradar import __version__
from lureradar.config import REPO_URL
from lureradar.enrich.types import RdapInfo
from lureradar.models import Verdict
from lureradar.util.defang import defang
from lureradar.util.time import isoformat, utcnow


@dataclass
class AbuseReport:
    to: list[str]
    subject: str
    body: str


def build_abuse_report(verdict: Verdict, rdap: RdapInfo | None = None) -> AbuseReport:
    host = verdict.host or verdict.target
    recipients = [rdap.abuse_email] if rdap and rdap.abuse_email else []
    registrar = rdap.registrar if rdap and rdap.registrar else "unknown (run with --live for RDAP)"
    evidence = "\n".join(
        f"  - {s.id} ({s.weight:+d}): {s.explanation}" for s in verdict.signals if s.weight > 0
    )
    registered = isoformat(rdap.registered) if rdap and rdap.registered else "unknown"
    verdict_line = (
        f"{verdict.tier.value.upper()} (score {verdict.score}/100) "
        f"at {isoformat(verdict.generated_at)}"
    )
    body = f"""Hello,

I am reporting a domain that appears to be used to lure gamers with fake
downloads, keys or account phishing. Indicators are defanged for safety.

Domain:            {host}
Target observed:   {verdict.target}
Registrar:         {registrar}
Registered:        {registered}
LureRadar verdict: {verdict_line}

Evidence (automated, explainable signals):
{evidence or "  - (none)"}

Please review the domain under your acceptable-use / abuse policy. This
report was drafted with LureRadar {__version__} ({REPO_URL}), an open-source
defensive tool; the assessment is automated and may contain errors.

Regards,
"""
    return AbuseReport(
        to=recipients,
        subject=f"Abuse report: suspected lure domain {host} ({utcnow().date().isoformat()})",
        body=body,
    )


def defanged(value: str) -> str:
    return defang(value)
