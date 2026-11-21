"""Shared helpers for repository guard scripts (stdlib only)."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINARY_EXT = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".pdf",
    ".zip",
    ".gz",
    ".db",
    ".webp",
    ".avif",
}


def repo_files() -> list[Path]:
    """Tracked + untracked-but-not-ignored files (what a commit could contain)."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "-co", "--exclude-standard"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        files = [ROOT / line for line in out.splitlines() if line]
    except (OSError, subprocess.CalledProcessError):
        files = [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]
    return [f for f in files if f.is_file()]


def is_text(path: Path) -> bool:
    return path.suffix.lower() not in BINARY_EXT
