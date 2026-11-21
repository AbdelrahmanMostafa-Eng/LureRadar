"""Fail if any fixture references a non-reserved domain or IP.

Fixtures must only use RFC 2606/6761 names (``*.test``, ``*.example``,
``*.invalid``, ``*.localhost``, ``example.com/.net/.org``) and RFC 5737/3849
documentation IPs, so the repository never ships real malicious indicators.
"""

from __future__ import annotations

import ipaddress
import re
import sys
from pathlib import Path

from _common import ROOT

FIXTURE_DIRS = [ROOT / "tests" / "fixtures", ROOT / "web" / "src" / "data" / "demo"]
RESERVED_TLDS = {"test", "example", "invalid", "localhost"}
RESERVED_DOMAINS = {"example.com", "example.net", "example.org"}
DOC_NETS = [
    ipaddress.ip_network(n)
    for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "2001:db8::/32")
]
# Hostname-like tokens with an alphabetic TLD (ignores versions such as 1.2.3).
HOST_RE = re.compile(
    r"(?<![\w@.-])((?:xn--)?[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.(?:xn--)?[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*\.[a-z][a-z0-9-]{1,62})(?![\w-])",
    re.IGNORECASE,
)
IPV4_RE = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.])")
# Tokens that look like hosts but are file names or code identifiers.
FILE_EXT = {
    "json",
    "yaml",
    "yml",
    "html",
    "htm",
    "txt",
    "md",
    "py",
    "js",
    "ts",
    "css",
    "exe",
    "apk",
    "zip",
    "rar",
    "msi",
    "png",
    "jpg",
    "svg",
    "gif",
    "xml",
    "csv",
    "php",
    "asp",
    "aspx",
    "jsp",
    "ipa",
    "dmg",
    "pkg",
    "bat",
    "scr",
    "iso",
    "7z",
    "jar",
    "lnk",
    "ps1",
    "vbs",
    "cmd",
    "sh",
    "woff2",
    "bin",
    "dat",
    "log",
    "webp",
    "ico",
    "zone",
}


def _benign_infrastructure() -> set[str]:
    """Shipped allowlists + shorteners: legitimate infrastructure, never indicators."""
    import yaml

    names: set[str] = set()
    data_dir = ROOT / "src" / "lureradar" / "data"
    for f in ("allowlist_base.yaml",):
        d = yaml.safe_load((data_dir / f).read_text(encoding="utf-8")) or {}
        names.update(d.get("outlets", []) + d.get("platforms", []))
    names.update(
        (yaml.safe_load((data_dir / "shorteners.yaml").read_text("utf-8")) or {}).get("domains", [])
    )
    for allow in (ROOT / "packs").glob("*/allowlist.yaml"):
        d = yaml.safe_load(allow.read_text(encoding="utf-8")) or {}
        names.update(d.get("outlets", []) + d.get("platforms", []))
    return {n.lower() for n in names}


# Standards bodies that appear in XML/JSON namespaces, never as indicators.
NAMESPACE_HOSTS = {"w3.org", "json-schema.org", "purl.org", "schema.org", "ietf.org"}
BENIGN = _benign_infrastructure() | NAMESPACE_HOSTS


def allowed_host(host: str) -> bool:
    host = host.lower().rstrip(".")
    if any(host == d or host.endswith("." + d) for d in BENIGN):
        return True
    tld = host.rsplit(".", 1)[-1]
    if tld in FILE_EXT:
        return True
    if tld in RESERVED_TLDS:
        return True
    return any(host == d or host.endswith("." + d) for d in RESERVED_DOMAINS)


def allowed_ip(text: str) -> bool:
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return True
    return any(ip in net for net in DOC_NETS) or ip.is_private or ip.is_loopback


def scan(path: Path) -> list[str]:
    problems = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in HOST_RE.finditer(line):
            if not allowed_host(m.group(1)):
                problems.append(
                    f"{path.relative_to(ROOT)}:{lineno}: non-reserved domain {m.group(1)!r}"
                )
        for m in IPV4_RE.finditer(line):
            if not allowed_ip(m.group(1)):
                problems.append(
                    f"{path.relative_to(ROOT)}:{lineno}: non-documentation IP {m.group(1)!r}"
                )
    return problems


def main(argv: list[str]) -> int:
    targets = [Path(a) for a in argv] or [d for d in FIXTURE_DIRS if d.exists()]
    files = []
    for t in targets:
        files.extend([t] if t.is_file() else [p for p in t.rglob("*") if p.is_file()])
    problems: list[str] = []
    for f in files:
        problems.extend(scan(f))
    if problems:
        print("Fixture domain guard FAILED (use reserved names: *.test, *.example, example.com):")
        print("\n".join(f"  {p}" for p in problems[:200]))
        return 1
    print(f"fixture domain guard: ok ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
