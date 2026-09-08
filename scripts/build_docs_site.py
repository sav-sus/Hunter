#!/usr/bin/env python3
"""Build the documentation into browsable HTML.

Read the Docs builds the site itself from `mkdocs.yml`, so this is not needed to
publish. It exists so the HTML can be opened from a checkout without installing
anything or running a server, which is the difference between documentation
somebody reads and documentation somebody means to read.

Output goes to `docs-html/`, which is committed. That is a deliberate trade: a
few megabytes in the repository against being able to open the site from any
checkout. One line in `.gitignore` reverses it.

    python scripts/build_docs_site.py           # build
    python scripts/build_docs_site.py --serve   # build and open it

Regenerates the pages that come from the code first, so the HTML can never be
built from a stale rules reference or a stale worked example.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUTPUT = REPO / "docs-html"


def regenerate_pages() -> None:
    """Rebuild the rules reference and the worked example."""
    completed = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "build_docs_pages.py")],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        print(completed.stdout)
        print(completed.stderr, file=sys.stderr)
        raise SystemExit("could not regenerate the documentation pages")
    print(completed.stdout.strip())


def build() -> Path:
    """Build the site, replacing whatever was there."""
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)

    completed = subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "--site-dir", str(OUTPUT)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        if "No module named mkdocs" in completed.stderr:
            raise SystemExit("MkDocs is not installed. Run: uv sync --all-extras")
        print(completed.stderr, file=sys.stderr)
        raise SystemExit("MkDocs could not build the site")

    # A marker, so nobody edits the output by mistake.
    (OUTPUT / "README.md").write_text(
        "# Built documentation\n\n"
        "Generated HTML. Do not edit anything in here.\n\n"
        "The source is in `docs/`. Rebuild with:\n\n"
        "    python scripts/build_docs_site.py\n\n"
        "Open `index.html` to read it. Read the Docs builds its own copy from\n"
        "`mkdocs.yml` and does not use this folder.\n\n"
        "_Rittman Hunter is a Rittman Analytics product._\n",
        encoding="utf-8",
    )
    return OUTPUT


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true", help="Open the built site in a browser.")
    parser.add_argument(
        "--skip-regenerate",
        action="store_true",
        help="Do not rebuild the generated pages first.",
    )
    args = parser.parse_args()

    if not args.skip_regenerate:
        regenerate_pages()

    output = build()
    pages = len(list(output.rglob("index.html")))
    size = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    print(f"built {pages} pages into {output.relative_to(REPO)} ({size // 1024} KB)")
    print(f"open {output / 'index.html'}")

    if args.serve:
        webbrowser.open((output / "index.html").as_uri())


if __name__ == "__main__":
    main()
