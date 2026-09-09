#!/usr/bin/env python3
"""Check that everything installing Hunter agrees on one version, and release it.

The composite actions install Hunter from the git tag ``v<hunter-version>``,
and the workflow ``hunter init`` writes references the actions at the same
tag. So five files carry the version, and a tag has to exist for it. The first
client install found all five pointing at a tag nobody had pushed: every job
failed in seconds with "unable to resolve action".

Three modes, kept apart on purpose so none can wait on another:

    python scripts/check_release.py            # the six files agree, and the
                                               # version is a release. No network.
                                               # Runs on every pull request.
    python scripts/check_release.py --tag      # as above, and the tag is on origin
    python scripts/check_release.py --release  # as above, creating the tag first
                                               # if it is missing. Runs on main.

The first version of this wiring had the pull-request check require the tag
and the release job require the check, so the tag could never be created. The
agreement check now never looks at the remote, and the release job creates the
tag before it asserts anything about it.
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
    Path("action.yml"),
    Path("actions") / "lookml-sync" / "action.yml",
    Path("actions") / "droughty-sync" / "action.yml",
    Path("actions") / "modelling-sync" / "action.yml",
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


def disagreements(version: str, repo: Path = REPO) -> list[str]:
    """Every file that names a different version, with what it says."""
    out: list[str] = []
    pyproject = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))
    declared = pyproject["project"]["version"]
    if declared != version:
        out.append(f"pyproject.toml says {declared}")
    for relative in ACTION_FILES:
        path = repo / relative
        found = action_default(path.read_text(encoding="utf-8"), path)
        if found != version:
            out.append(f"{relative} defaults hunter-version to {found}")
    if ".dev" in version or "+" in version:
        out.append(
            f"the version is {version}, which is not a release: the actions install "
            "from a release tag, so a development version cannot be installed"
        )
    return out


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)


def tag_exists(tag: str, repo: Path = REPO) -> bool:
    completed = _git(repo, "ls-remote", "--tags", "origin", f"refs/tags/{tag}")
    if completed.returncode != 0:
        raise SystemExit(f"git ls-remote failed: {completed.stderr.strip()}")
    return bool(completed.stdout.strip())


def ensure_tag(tag: str, repo: Path = REPO) -> str:
    """Create the tag at HEAD and push it, unless origin already has it.

    An existing tag is left where it is. That is what makes a later commit
    with the same version a no-op, and a version bump a new tag: the old
    release keeps pointing at the commit that was released.
    """
    if tag_exists(tag, repo):
        return f"Tag {tag} already exists on origin."
    for step in (("tag", tag), ("push", "origin", tag)):
        completed = _git(repo, *step)
        if completed.returncode != 0:
            raise SystemExit(f"git {' '.join(step)} failed: {completed.stderr.strip()}")
    head = _git(repo, "rev-parse", "--short", "HEAD").stdout.strip()
    return f"Created tag {tag} at {head} and pushed it."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--tag", action="store_true", help="Also require the tag on origin.")
    group.add_argument(
        "--release",
        action="store_true",
        help="Create the tag on origin if it is missing, then require it.",
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

    if not (args.tag or args.release):
        return 0
    tag = f"v{version}"
    if args.release:
        print(ensure_tag(tag))
    if tag_exists(tag):
        print(f"Tag {tag} exists on origin.")
        return 0
    print(
        f"Tag {tag} does not exist on origin. Every action.yml installs Hunter from it, so\n"
        f"every client workflow fails with 'unable to resolve action'. Create it with:\n"
        f"  python scripts/check_release.py --release"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
