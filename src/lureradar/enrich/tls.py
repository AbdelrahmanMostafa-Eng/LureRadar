"""TLS enrichment: certificate issuer, validity window and SANs.

Connects only to an address that passed the SSRF guard. If the certificate
does not verify, it is still inspected (without trusting it) and marked so.
"""

from __future__ import annotations

import asyncio
import contextlib
import ssl

from cryptography import x509
from cryptography.x509.oid import ExtensionOID

from lureradar.enrich.types import TlsInfo

TIMEOUT_S = 5.0


def parse_certificate(der: bytes) -> TlsInfo:
    cert = x509.load_der_x509_certificate(der)
    try:
        san = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        names = san.value.get_values_for_type(x509.DNSName)  # type: ignore[attr-defined]
    except x509.ExtensionNotFound:
        names = []
    return TlsInfo(
        issuer=cert.issuer.rfc4514_string()[:200],
        not_before=cert.not_valid_before_utc,
        not_after=cert.not_valid_after_utc,
        sans=[str(n) for n in names][:50],
    )


async def _peer_der(ip: str, host: str, verify: bool, port: int) -> bytes:
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(ip, port, ssl=ctx, server_hostname=host), TIMEOUT_S
    )
    try:
        obj = writer.get_extra_info("ssl_object")
        der = obj.getpeercert(binary_form=True) if obj else None
        if not der:
            raise ssl.SSLError("no peer certificate")
        return bytes(der)
    finally:
        writer.close()
        with contextlib.suppress(OSError, ssl.SSLError):
            await writer.wait_closed()
        del reader


async def inspect_tls(ip: str, host: str, port: int = 443) -> tuple[TlsInfo, bool]:
    """Return ``(info, verified)``. ``ip`` must already be vetted by the SSRF guard."""
    try:
        return parse_certificate(await _peer_der(ip, host, True, port)), True
    except ssl.SSLCertVerificationError:
        return parse_certificate(await _peer_der(ip, host, False, port)), False
