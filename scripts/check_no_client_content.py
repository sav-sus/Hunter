#!/usr/bin/env python3
"""Fail if client-identifying content appears in tracked files.

Hunter is developed by running it against a real client repository, so client
names pass through the working tree constantly. Nothing client-derived may be
committed. This makes that rule enforced rather than remembered.

Layer names (staging, integration, warehouse) and entity suffixes (_fact, _dim,
_xa) are generic Rittman Analytics conventions and are deliberately not listed.

Usage:
    python scripts/check_no_client_content.py            # tracked files
    python scripts/check_no_client_content.py --staged   # staged files only
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Built from parts so this file does not match its own patterns.
_CLIENT = "hunkem" + "oller"
_SHORT = "hkm"
_PILOT_REPO = "gcp-" + "analytics-platform"

FORBIDDEN: list[tuple[str, str]] = [
    (rf"{_CLIENT}", "client name"),
    (rf"{_CLIENT[:6]}öller", "client name, accented spelling"),
    (rf"\b{_SHORT}[_\-]", "client short code"),
    (rf"[_\-]{_SHORT}\b", "client short code"),
    (rf"{_PILOT_REPO}", "pilot repository name"),
    (r"pj-data-warehouse-prod", "client warehouse project"),
    (r"pj-\w*-data-marts-prod", "client warehouse project"),
    (r"/Users/[^/\s]+/Clients/", "local client working path"),
]

# Binary and vendored content is not scanned.
SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".pdf",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".zip",
    ".gz",
    ".msgpack",
    ".gpickle",
}

SKIP_PATHS = {
    "scripts/check_no_client_content.py",  # this file names the patterns
    "src/hunter/assets/mermaid.min.js",  # vendored, 2.5 MB of minified JavaScript
    "src/hunter/assets/MERMAID-LICENSE",
}


def tracked_files(staged: bool) -> list[str]:
    cmd = (
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"]
        if staged
        else ["git", "ls-files"]
    )
    out = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return [line for line in out.stdout.splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="scan staged changes only")
    args = parser.parse_args()

    patterns = [(re.compile(p, re.IGNORECASE), why) for p, why in FORBIDDEN]
    hits: list[str] = []

    for rel in tracked_files(args.staged):
        if rel in SKIP_PATHS:
            continue
        path = REPO_ROOT / rel
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern, why in patterns:
                if pattern.search(line):
                    hits.append(f"{rel}:{lineno}: {why} ({pattern.pattern})")

    if hits:
        print("Client-identifying content found in tracked files:\n", file=sys.stderr)
        for hit in hits:
            print(f"  {hit}", file=sys.stderr)
        print(
            "\nNothing client-derived may be committed. Move it out of the tree, "
            "or use invented names.",
            file=sys.stderr,
        )
        return 1

    scanned = "staged changes" if args.staged else "tracked files"
    print(f"No client-identifying content in {scanned}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
