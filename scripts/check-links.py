#!/usr/bin/env python3
"""Verify that every relative Markdown link resolves to a file on disk.

External links (``http(s)://``) and pure anchors (``#...``) are skipped — this
checks the repository's internal integrity (catalog -> docs -> screenshots ->
JSON), which is what breaks silently as the library grows. Run from the repo
root. Exits non-zero if any relative link is dangling.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def main() -> int:
    broken: list[str] = []
    checked = 0
    for md in ROOT.rglob("*.md"):
        if "node_modules" in md.parts:
            continue
        text = md.read_text(encoding="utf-8")
        for m in LINK_RE.finditer(text):
            target = m.group(1).strip()
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            path_part = target.split("#", 1)[0].split("?", 1)[0]
            if not path_part:
                continue
            checked += 1
            resolved = (md.parent / path_part).resolve()
            if not resolved.exists():
                broken.append(f"{md.relative_to(ROOT)} -> {target}")
    for b in broken:
        print(f"  BROKEN {b}")
    print(f"\ncheck-links: {checked} relative links, {len(broken)} broken")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
