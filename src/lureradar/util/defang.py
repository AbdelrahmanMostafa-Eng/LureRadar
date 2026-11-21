"""Defang and refang indicators.

Defanging makes an indicator safe to display: it can no longer be clicked or
auto-linked. LureRadar defangs everything it shows (CLI, feeds metadata,
dashboard, issues) and accepts defanged input everywhere.

    >>> defang("https://evil.example.com/x")
    'hxxps://evil[.]example[.]com/x'
    >>> refang("hxxps://evil[.]example[.]com/x")
    'https://evil.example.com/x'
"""

from __future__ import annotations

import re

_SCHEME_RE = re.compile(r"^(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*)://", re.ASCII)

# Order matters: longer, more specific tokens first.
_REFANG_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\[\s*:\s*/\s*/\s*\]"), "://"),
    (re.compile(r"\[\s*://\s*\]"), "://"),
    (re.compile(r"\b(h)xx(ps?)(?=(?:\[:\]|:)//|\[://\])", re.IGNORECASE), r"\1tt\2"),
    (re.compile(r"\b(h)xx(ps?)\b", re.IGNORECASE), r"\1tt\2"),
    (re.compile(r"\bfxp(?=://)", re.IGNORECASE), "ftp"),
    (re.compile(r"[\[\(\{]\s*(?:\.|dot)\s*[\]\)\}]", re.IGNORECASE), "."),
    (re.compile(r"\\\."), "."),
    (re.compile(r"[\[\(\{]\s*:\s*[\]\)\}]"), ":"),
    (re.compile(r"[\[\(\{]\s*/\s*[\]\)\}]"), "/"),
    (re.compile(r"[\[\(\{]\s*(?:@|at)\s*[\]\)\}]", re.IGNORECASE), "@"),
)


def refang(value: str) -> str:
    """Undo common defanging conventions (``hxxp``, ``[.]``, ``(dot)``, ``[:]``...)."""
    text = value.strip()
    for pattern, repl in _REFANG_RULES:
        text = pattern.sub(repl, text)
    return text


def _defang_host(host: str) -> str:
    return host.replace("[.]", ".").replace(".", "[.]")


def defang(value: str) -> str:
    """Defang a URL or domain. Idempotent: ``defang(defang(x)) == defang(x)``."""
    text = value.strip()
    if not text:
        return text
    match = _SCHEME_RE.match(text)
    if match:
        scheme = match.group("scheme")
        rest = text[match.end() :]
        lowered = scheme.lower()
        if lowered in ("http", "https"):
            scheme = scheme[0] + ("XX" if scheme[1].isupper() else "xx") + scheme[3:]
        elif lowered == "ftp":
            scheme = scheme[0] + ("X" if scheme[1].isupper() else "x") + scheme[2:]
        # authority runs until the first '/', '?' or '#'
        cut = len(rest)
        for sep in "/?#":
            idx = rest.find(sep)
            if idx != -1:
                cut = min(cut, idx)
        authority, tail = rest[:cut], rest[cut:]
        if "@" in authority:
            userinfo, _, hostport = authority.rpartition("@")
            authority = f"{userinfo}[@]{_defang_host(hostport)}"
        else:
            authority = _defang_host(authority)
        return f"{scheme}://{authority}{tail}"
    if "/" in text:
        host, _, tail = text.partition("/")
        return f"{_defang_host(host)}/{tail}"
    return _defang_host(text)


def defang_text(text: str) -> str:
    """Defang every URL and domain-looking token inside free text."""
    from lureradar.util.domains import URL_RE, has_known_suffix, to_ascii_host

    def _sub(match: re.Match[str]) -> str:
        token = match.group(0)
        stripped = token.rstrip(".,;:!?)]}>'\"")
        trailer = token[len(stripped) :]
        if "://" not in stripped:
            host = stripped.split("/", 1)[0].split(":", 1)[0]
            if not has_known_suffix(to_ascii_host(host) or host):
                return token
        return defang(stripped) + trailer

    return URL_RE.sub(_sub, refang(text))


def is_defanged(value: str) -> bool:
    lowered = value.lower()
    return "[.]" in value or lowered.startswith(("hxxp://", "hxxps://"))
