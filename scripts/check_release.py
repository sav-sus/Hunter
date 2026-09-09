#!/usr/bin/env python3
"""Check that everything installing Hunter agrees on one version, and that the
version has been released.

The composite actions install Hunter from the git tag ``v<hunter-version>``,
and the workflow ``hunter init`` writes references the actions at the same
tag. So five files carry the version, and a tag has to exist for it. The first
client install found all five pointing at a tag nobody had pushed: every job
failed in seconds with "unable to resolve action". This script is what makes
that impossible to ship again.

    python scripts/check_release.py                 # agreement only
    python scripts/check_release.py --tag            # agreement, and the tag exists
    python scripts/check_release.py --tag --allow-unreleased-bump
                                                     # as above, but a version that
                                                     # differs from origin/main may
                                                     # not have its tag yet

The last form is for pull requests. A release is a pull request that bumps the
version; its tag is created when it reaches main, by the release job in
.github/workflows/ci.yml. Until then the tag is legitimately absent.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ACTION_FILES = (
    REPO / "action.yml",
    REPO / "actions" / "lookml-sync" / "action.yml",
    REPO / "actions" / "droughty-sync" / "action.yml",
    REPO / "actions" / "modelling-sync" / "action.yml",
)
VERSION_LINE = re.compile(r'^__version__ = "(?P<version>[^"]+)"$', re.M)
HUNTER_VERSION_DEFAULT = re.compile(
    r"^  hunter-version:\n(?:    .*\n)*?    default: \"(?P<version>[^\"]+)\"", re.M
)


def package_version(init_text: str) -> str:
    match = VERSION_LINE.search(init_text)
    if match is None:
        raise SystemExit("src/hunter/__init__.py has no __version__ line")
    return match.group("version")


def action_default(text: str, path: Path) -> str:
    match = HUNTER_VERSION_DEFAULT.search(text)
    if match is None:
        raise SystemExit(f"{path} has no hunter-version input with a default")
    return match.group("version")


def disagreements(version: str) -> list[str]:
    """Every file that names a different version, with what it says."""
    out: list[str] = []
    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    declared = pyproject["project"]["version"]
    if declared != version:
        out.append(f"pyproject.toml says {declared}")
    for path in ACTION_FILES:
        found = action_default(path.read_text(encoding="utf-8"), path)
        if found != version:
            out.append(f"{path.relative_to(REPO)} defaults hunter-version to {found}")
    if ".dev" in version or "+" in version:
        out.append(
            f"the version is {version}, which is not a release: the actions install "
            "from a release tag, so a development version cannot be installed"
        )
    return out


def tag_exists(tag: str) -> bool:
    completed = subprocess.run(
        ["git", "ls-remote", "--tags", "origin", f"refs/tags/{tag}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(f"git ls-remote failed: {completed.stderr.strip()}")
    return bool(completed.stdout.strip())


def version_on_main() -> str | None:
    completed = subprocess.run(
        ["git", "show", "origin/main:src/hunter/__init__.py"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return package_version(completed.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tag", action="store_true", help="Also require the tag on origin.")
    parser.add_argument(
        "--allow-unreleased-bump",
        action="store_true",
        help="Accept a missing tag when the version differs from origin/main.",
    )
    args = parser.parse_args()

    version = package_version((REPO / "src" / "hunter" / "__init__.py").read_text(encoding="utf-8"))
    problems = disagreements(version)
    if problems:
        print(f"Hunter is {version}, but:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"Every file agrees: Hunter {version}, installed from tag v{version}.")

    if not args.tag:
        return 0
    tag = f"v{version}"
    if tag_exists(tag):
        print(f"Tag {tag} exists on origin.")
        return 0
    if args.allow_unreleased_bump:
        released = version_on_main()
        if released is not None and released != version:
            print(f"Tag {tag} is not on origin yet. main is {released}; this is a release bump.")
            return 0
    print(
        f"Tag {tag} does not exist on origin. Every action.yml installs Hunter from it, so\n"
        f"every client workflow fails with 'unable to resolve action'. Create it with:\n"
        f"  git tag {tag} && git push origin {tag}"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
