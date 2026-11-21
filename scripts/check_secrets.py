"""Fail if anything that looks like a credential is in the repository.

High-signal patterns only (no entropy guessing) so the check stays quiet and
trustworthy. CI additionally runs GitHub secret scanning.
"""

from __future__ import annotations

import re
import sys

from _common import ROOT, is_text, repo_files

PATTERNS = {
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})\b"),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "Private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    # built from parts so this file does not match its own pattern
    "minisign secret key": re.compile("untrusted comment: minisign " + "encrypted secret key"),
    "Stripe key": re.compile(r"\b(?:sk|rk)_live_[0-9a-zA-Z]{20,}\b"),
    "Assigned secret": re.compile(
        r"""(?i)\b(?:api[_-]?key|secret|token|password|auth[_-]?key)\b\s*[:=]\s*["'][A-Za-z0-9/+_\-]{24,}["']"""
    ),
}
SKIP = {"uv.lock", "package-lock.json"}
ALLOW_MARKER = "secret-scan: allow"


def main() -> int:
    findings: list[str] = []
    for path in repo_files():
        rel = path.relative_to(ROOT).as_posix()
        if path.name in SKIP or not is_text(path) or rel.startswith("node_modules/"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if ALLOW_MARKER in line:
                continue
            for name, rx in PATTERNS.items():
                if rx.search(line):
                    findings.append(f"{rel}:{lineno}: possible {name}")
    if findings:
        print("Secret scan FAILED:")
        print("\n".join(f"  {f}" for f in findings))
        return 1
    print(f"secret scan: ok ({len(repo_files())} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
