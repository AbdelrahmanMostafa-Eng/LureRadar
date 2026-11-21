"""Target parsing and domain normalisation.

All parsing is offline: the Public Suffix List snapshot bundled with
``tldextract`` is used and no network fetch is ever attempted.
"""

from __future__ import annotations

import ipaddress
import re
from functools import lru_cache
from urllib.parse import urlsplit

import idna
import tldextract

from lureradar.errors import InvalidTargetError
from lureradar.models import ParsedTarget, TargetKind
from lureradar.util.defang import refang

# Offline extractor: never download the PSL; include private suffixes so that
# ``foo.github.io`` and ``foo.blogspot.com`` are treated as separately owned.
_EXTRACT = tldextract.TLDExtract(
    suffix_list_urls=(), cache_dir=None, include_psl_private_domains=True
)

_LABEL = r"(?:[^\W_](?:[^\W_]|-){0,62})"
_HOST = rf"(?:{_LABEL}\.)+[^\W\d_](?:[^\W_]|-){{1,62}}"
URL_RE = re.compile(
    rf"(?:(?:https?|ftp)://[^\s<>\"'`]+)|(?<![\w@.-])(?:{_HOST})(?::\d{{2,5}})?(?:/[^\s<>\"'`]*)?",
    re.IGNORECASE,
)
_TRAILING = ".,;:!?)]}>'\""
_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")
_MAX_INPUT = 20_000


def extract(host: str) -> tldextract.tldextract.ExtractResult:
    return _EXTRACT(host)


_RESERVED_TLDS = frozenset({"test", "example", "invalid", "localhost"})


@lru_cache(maxsize=1)
def _shared_host_suffixes() -> tuple[str, ...]:
    from importlib import resources

    import yaml

    text = resources.files("lureradar.data").joinpath("shared_hosts.yaml").read_text("utf-8")
    data = yaml.safe_load(text) or {}
    return tuple(sorted({str(s).lower() for s in data.get("suffixes", [])}, key=len, reverse=True))


def has_known_suffix(host: str) -> bool:
    """True if ``host`` ends in a public suffix or an RFC 2606/6761 reserved TLD."""
    if bool(_EXTRACT(host).suffix):
        return True
    return host.rsplit(".", 1)[-1].lower() in _RESERVED_TLDS


def find_urls(text: str) -> list[str]:
    """Return URL- and domain-looking tokens in ``text`` (input should be refanged).

    Bare tokens are kept only when they end in a real public suffix, so
    ``setup.exe`` or ``e.g.`` are ignored while ``free-key.xyz`` is found.
    """
    found: list[str] = []
    for match in URL_RE.finditer(text):
        token = match.group(0).rstrip(_TRAILING)
        if not token:
            continue
        if "://" not in token:
            host = token.split("/", 1)[0].split(":", 1)[0]
            if not has_known_suffix(to_ascii_host(host) or host):
                continue
        found.append(token)
    return found


def to_ascii_host(host: str) -> str:
    """IDNA-encode a hostname (UTS #46). Returns '' if it cannot be encoded."""
    host = host.strip().rstrip(".").lower()
    if not host:
        return ""
    try:
        return idna.encode(host, uts46=True, transitional=False).decode("ascii")
    except idna.IDNAError:
        pass
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        return ""


def to_unicode_host(host: str) -> str:
    """Decode punycode labels for display/analysis; best effort, label by label."""
    labels = []
    for label in host.split("."):
        if label.startswith("xn--"):
            try:
                labels.append(idna.decode(label))
                continue
            except idna.IDNAError:
                try:
                    labels.append(label.encode("ascii").decode("idna"))
                    continue
                except UnicodeError:
                    pass
        labels.append(label)
    return ".".join(labels)


def tokenize(text: str) -> list[str]:
    """Split a hostname or path into lowercase alphanumeric tokens."""
    return [t for t in _TOKEN_SPLIT.split(text.lower()) if t]


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return True


def _looks_like_text(text: str) -> bool:
    if any(ch.isspace() for ch in text):
        return True
    return "." not in text and "://" not in text and not _is_ip(text)


@lru_cache(maxsize=4096)
def parse_target(raw: str) -> ParsedTarget:
    """Parse user input into a :class:`ParsedTarget`.

    Accepts URLs, bare domains (optionally with a path) and free text. Defanged
    input (``hxxps://evil[.]example``) is refanged first.
    """
    if len(raw) > _MAX_INPUT:
        raise InvalidTargetError(f"input too long ({len(raw)} > {_MAX_INPUT} characters)")
    text = refang(raw)
    if not text:
        raise InvalidTargetError("empty target")
    if _looks_like_text(text):
        return ParsedTarget(raw=raw, kind=TargetKind.TEXT)

    kind = TargetKind.URL
    url_text = text
    if "://" not in text:
        if any(sep in text for sep in "/?#"):
            url_text = "http://" + text
        else:
            kind = TargetKind.DOMAIN
            url_text = "http://" + text

    try:
        parts = urlsplit(url_text)
        hostname = parts.hostname or ""
        _ = parts.port  # raises ValueError on garbage ports
    except ValueError as exc:
        raise InvalidTargetError(f"could not parse {raw!r}: {exc}") from exc

    if parts.scheme.lower() not in ("http", "https", "ftp"):
        raise InvalidTargetError(f"unsupported scheme {parts.scheme!r}")
    if not hostname:
        raise InvalidTargetError(f"no hostname in {raw!r}")

    is_ip = _is_ip(hostname)
    ascii_host = hostname.strip("[]").lower() if is_ip else to_ascii_host(hostname)
    if not ascii_host or (not is_ip and not re.fullmatch(r"[a-z0-9.-]+", ascii_host)):
        raise InvalidTargetError(f"invalid hostname in {raw!r}")

    path = parts.path or ""
    if parts.query:
        path += "?" + parts.query
    if kind is TargetKind.DOMAIN:
        url = None
    else:
        host_part = f"[{ascii_host}]" if is_ip and ":" in ascii_host else ascii_host
        netloc = host_part if parts.port is None else f"{host_part}:{parts.port}"
        url = f"{parts.scheme.lower()}://{netloc}{path or '/'}"

    if is_ip:
        return ParsedTarget(
            raw=raw,
            kind=kind,
            url=url,
            scheme=parts.scheme.lower(),
            host=ascii_host,
            unicode_host=ascii_host,
            registrable_domain=ascii_host,
            domain_label=ascii_host,
            path=path,
            is_ip=True,
        )

    subdomain, label, suffix, is_private = split_host(ascii_host)
    registrable = f"{label}.{suffix}" if label and suffix else ascii_host
    return ParsedTarget(
        raw=raw,
        kind=kind,
        url=url,
        scheme=parts.scheme.lower(),
        host=ascii_host,
        unicode_host=to_unicode_host(ascii_host),
        registrable_domain=registrable,
        domain_label=label,
        subdomain=subdomain,
        suffix=suffix,
        path=path,
        is_ip=False,
        is_private_suffix=is_private,
    )


def split_host(ascii_host: str) -> tuple[str, str, str, bool]:
    """Return ``(subdomain, label, suffix, is_private_suffix)``.

    Applies the PSL's implicit ``*`` rule: an unknown TLD (``.test``,
    ``.invalid``, ``.example``, internal names) is treated as a one-label suffix,
    exactly as browsers do.
    """
    labels = ascii_host.split(".")
    for extra in _shared_host_suffixes():
        if ascii_host.endswith("." + extra) and ascii_host != extra:
            head = ascii_host[: -len(extra) - 1].split(".")
            return ".".join(head[:-1]), head[-1], extra, True
    ext = _EXTRACT(ascii_host)
    if ext.suffix:
        return ext.subdomain, ext.domain, ext.suffix, bool(ext.is_private)
    if len(labels) < 2:
        return "", ascii_host, "", False
    return ".".join(labels[:-2]), labels[-2], labels[-1], False


def registrable_domain(host_or_url: str) -> str:
    """eTLD+1 of a host or URL (ASCII/punycode)."""
    target = parse_target(host_or_url)
    return target.registrable_domain


def normalise_domain(value: str) -> str:
    """Canonical ASCII hostname for a domain/URL; raises InvalidTargetError."""
    target = parse_target(value)
    if target.kind is TargetKind.TEXT:
        raise InvalidTargetError(f"not a domain: {value!r}")
    return target.host
