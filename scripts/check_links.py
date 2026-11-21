"""Check that relative links in Markdown files point to existing files/anchors."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from _common import ROOT, repo_files

LINK_RE = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)|!\[[^\]]*\]\(([^)\s]+)\)")
HTML_RE = re.compile(r"""(?:src|href)=["']([^"']+)["']""")
HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)


def slugify(heading: str) -> str:
    h = re.sub(r"<[^>]+>", "", heading).strip().lower()
    h = re.sub(r"[^\w\- ]", "", h)
    return h.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return {slugify(h) for h in HEADING_RE.findall(text)}


def main() -> int:
    md_files = [
        p
        for p in repo_files()
        if p.suffix == ".md" and "node_modules" not in p.parts and ".venv" not in p.parts
    ]
    problems: list[str] = []
    for md in md_files:
        text = md.read_text(encoding="utf-8")
        stripped = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        stripped = re.sub(r"`[^`\n]*`", "", stripped)
        targets = [a or b for a, b in LINK_RE.findall(stripped)] + HTML_RE.findall(stripped)
        for target in targets:
            if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("//"):
                continue  # external (http, mailto...) - not checked offline
            path_part, _, anchor = target.partition("#")
            dest = md if not path_part else (md.parent / path_part).resolve()
            if not dest.exists():
                problems.append(f"{md.relative_to(ROOT)}: broken link -> {target}")
                continue
            if anchor and dest.suffix == ".md" and anchor.lower() not in anchors(dest):
                problems.append(f"{md.relative_to(ROOT)}: missing anchor -> {target}")
    if problems:
        print("Link check FAILED:")
        print("\n".join(f"  {p}" for p in problems))
        return 1
    print(f"link check: ok ({len(md_files)} markdown files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
