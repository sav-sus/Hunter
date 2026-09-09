"""``hunter init``: work out this repository's layout and write the three files.

Section 11.6. A client repository gets three things and no Hunter code: a
ruleset, a register, and a workflow that calls the published Actions and
publishes the dashboard to GitHub Pages.

The register is pre-filled with the entries the team would otherwise have to
discover, each with a blank reason. Handing someone an empty file and asking
them to document their exceptions does not work; handing them the list and
asking for a reason against each one does.
"""

from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from hunter import __version__
from hunter.config.schema import CiSpec
from hunter.enums import ManifestSource

#: Where a dbt project might sit, in the order worth trying.
DBT_PROJECT_FILE = "dbt_project.yml"

#: Candidate locations for each optional source, most specific first.
DBML_PATTERNS = (
    "models/_model/*.dbml",
    "docs/data_model_design/*.dbml",
    "docs/*.dbml",
    "models/**/*.dbml",
)
CONCEPTUAL_CANDIDATES = (
    "docs/data_model_design/conceptual_model.mermaid",
    "docs/conceptual_model.mermaid",
    "models/_model/conceptual_model.mermaid",
)
LOGICAL_CANDIDATES = (
    "docs/data_model_design/logical_model.mermaid",
    "docs/logical_model.mermaid",
)
LOOKML_PATTERNS = ("lookml/**/*.lkml", "**/*.lkml")
DROUGHTY_DBML_PATTERNS = ("docs/db_docs/*.dbml",)


class Detected:
    """What was found in the repository, and what it implies for the ruleset."""

    def __init__(self) -> None:
        self.dbt_project_dir: str = "."
        self.dbml: list[str] = []
        self.conceptual: str | None = None
        self.logical: str | None = None
        self.lookml: list[str] = []
        self.droughty_dbml: list[str] = []
        self.manifest_found: bool = False
        #: dbt's profile name from dbt_project.yml, for the CI profile example.
        self.profile: str | None = None
        #: The warehouse adapter, read from a profiles.yml in the repository.
        self.adapter: str | None = None
        #: Whether target/ is gitignored, in which case CI has no manifest
        #: unless the workflow builds one.
        self.target_gitignored: bool = False
        #: dbt packages with the versions the repository pins, such as
        #: ``dbt-bigquery~=1.9``, and the file they were read from. CI parses
        #: with the same dbt the team runs, or the manifest can differ.
        self.dbt_pins: list[str] = []
        self.dbt_pins_source: str | None = None
        #: Where GitHub Pages would publish this repository's site, worked out
        #: from the origin remote. Offered in hunter.yml as a commented line.
        self.pages_url: str | None = None
        self.notes: list[str] = []


def _find_dbt_project(root: Path) -> Path | None:
    """The dbt project directory, ignoring installed packages."""
    direct = root / DBT_PROJECT_FILE
    if direct.exists():
        return root
    candidates = [
        path.parent
        for path in sorted(root.glob(f"*/{DBT_PROJECT_FILE}"))
        if "dbt_packages" not in path.parts
    ]
    if candidates:
        return candidates[0]
    deeper = [
        path.parent
        for path in sorted(root.glob(f"*/*/{DBT_PROJECT_FILE}"))
        if "dbt_packages" not in path.parts
    ]
    return deeper[0] if deeper else None


def detect(root: Path) -> Detected:
    """Look at the repository and work out where everything is."""
    found = Detected()

    project_dir = _find_dbt_project(root)
    if project_dir is None:
        found.notes.append(
            "No dbt_project.yml was found, so paths below are guesses. Set "
            "paths.dbt_project_dir by hand."
        )
        project_dir = root
    found.dbt_project_dir = _as_relative(project_dir, root)

    found.manifest_found = (project_dir / "target" / "manifest.json").exists()
    if not found.manifest_found:
        found.notes.append(
            "No target/manifest.json was found. Run `dbt parse` in the project, or "
            "pass --manifest with the path to one your dbt job already produces."
        )

    found.profile = _dbt_profile_name(project_dir)
    found.adapter = _dbt_adapter(root, project_dir)
    found.dbt_pins, found.dbt_pins_source = _dbt_pins(root, project_dir)
    found.pages_url = _pages_url(root)
    if found.adapter is None:
        for pin in found.dbt_pins:
            package = re.split(r"[=~!<>\[ ]", pin, maxsplit=1)[0]
            if package != "dbt-core":
                found.adapter = package.removeprefix("dbt-")
                break
    found.target_gitignored = _target_is_gitignored(root, project_dir)
    if found.target_gitignored:
        found.notes.append(
            "target/ is gitignored, so a CI checkout never has a manifest. The generated "
            "workflow builds one with `dbt parse` before Hunter runs. That needs a dbt "
            "profile in CI: add a repository secret named DBT_PROFILES_YML. The header "
            "of .github/workflows/hunter.yml says what to put in it."
        )

    for pattern in DBML_PATTERNS:
        if list(project_dir.glob(pattern)):
            found.dbml = [pattern]
            break
    if not found.dbml:
        found.notes.append(
            "No DBML design files were found, so nothing will be compared against a "
            "design. Set paths.dbml if they live somewhere else."
        )

    for candidate in CONCEPTUAL_CANDIDATES:
        if (project_dir / candidate).exists():
            found.conceptual = candidate
            break
    for candidate in LOGICAL_CANDIDATES:
        if (project_dir / candidate).exists():
            found.logical = candidate
            break

    for pattern in LOOKML_PATTERNS:
        if list(project_dir.glob(pattern)):
            found.lookml = [pattern]
            break

    for pattern in DROUGHTY_DBML_PATTERNS:
        if list(project_dir.glob(pattern)):
            found.droughty_dbml = [pattern]
            break

    return found


def _dbt_profile_name(project_dir: Path) -> str | None:
    try:
        loaded = yaml.safe_load((project_dir / DBT_PROJECT_FILE).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    if isinstance(loaded, dict) and isinstance(loaded.get("profile"), str):
        return loaded["profile"]
    return None


def _dbt_adapter(root: Path, project_dir: Path) -> str | None:
    """The adapter type from a profiles.yml committed in the repository, if any."""
    for candidate in (
        project_dir / "profiles.yml",
        root / "profiles.yml",
        project_dir / ".dbt" / "profiles.yml",
        root / ".dbt" / "profiles.yml",
    ):
        if not candidate.exists():
            continue
        try:
            loaded = yaml.safe_load(candidate.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(loaded, dict):
            continue
        for profile in loaded.values():
            outputs = profile.get("outputs") if isinstance(profile, dict) else None
            if not isinstance(outputs, dict):
                continue
            for output in outputs.values():
                if isinstance(output, dict) and isinstance(output.get("type"), str):
                    return output["type"]
    return None


#: dbt-core and the adapters. Not dbt-common, dbt-adapters or the other
#: internal packages, which the adapter pulls in at the version it needs.
_DBT_ADAPTERS = (
    "bigquery",
    "snowflake",
    "postgres",
    "redshift",
    "databricks",
    "duckdb",
    "spark",
    "trino",
    "athena",
    "clickhouse",
    "sqlserver",
    "fabric",
    "synapse",
    "oracle",
    "mysql",
)
_DBT_PACKAGE = r"dbt-(?:core|" + "|".join(_DBT_ADAPTERS) + r")"
_REQUIREMENT = re.compile(
    r"(?<![\w-])(?P<name>" + _DBT_PACKAGE + r")(?:\[[^\]]*\])?\s*"
    r"(?P<spec>(?:===?|~=|!=|<=?|>=?)\s*[0-9][\w.*+!-]*(?:\s*,\s*(?:===?|~=|!=|<=?|>=?)\s*[0-9][\w.*+!-]*)*)",
    re.I,
)
_LOCKED = re.compile(
    r'^name = "(?P<name>' + _DBT_PACKAGE + r')"\nversion = "(?P<version>[^"]+)"', re.M
)
_PIN_FILES = (
    "requirements.txt",
    "requirements-dbt.txt",
    "requirements/dbt.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "uv.lock",
    "poetry.lock",
)


def _dbt_pins(root: Path, project_dir: Path) -> tuple[list[str], str | None]:
    """The dbt versions the repository pins, from the first file that names any.

    Lock files give exact versions and win over loose ranges, so they are
    read first. Requirement and project files are read for their specifiers.
    """
    seen: list[Path] = []
    for directory in (project_dir, root):
        for name in _PIN_FILES:
            candidate = directory / name
            if candidate.exists() and candidate not in seen:
                seen.append(candidate)
    seen.sort(key=lambda path: 0 if path.suffix == ".lock" else 1)
    for path in seen:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        pins: dict[str, str] = {}
        if path.suffix == ".lock":
            for match in _LOCKED.finditer(text):
                pins[match.group("name").lower()] = f"=={match.group('version')}"
        else:
            for match in _REQUIREMENT.finditer(text):
                pins[match.group("name").lower()] = re.sub(r"\s+", "", match.group("spec"))
        if pins:
            ordered = sorted(pins, key=lambda name: (name != "dbt-core", name))
            return [f"{name}{pins[name]}" for name in ordered], _as_relative(path, root)
    return [], None


_GITHUB_REMOTE = re.compile(r"github\.com[:/](?P<owner>[^/\s]+)/(?P<repo>[^/\s]+?)(?:\.git)?/?$")


def _pages_url(root: Path) -> str | None:
    """The GitHub Pages address for the origin remote, or None if not on GitHub."""
    completed = subprocess.run(
        ["git", "-C", str(root), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    match = _GITHUB_REMOTE.search(completed.stdout.strip())
    if match is None:
        return None
    return f"https://{match.group('owner').lower()}.github.io/{match.group('repo')}/"


_TARGET_IGNORE = re.compile(r"^/?(\*\*/)?target/?(\*\*)?$")


def _target_is_gitignored(root: Path, project_dir: Path) -> bool:
    for ignore_file in {root / ".gitignore", project_dir / ".gitignore"}:
        if not ignore_file.exists():
            continue
        try:
            lines = ignore_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            if _TARGET_IGNORE.match(line.strip()):
                return True
    return False


def _as_relative(path: Path, root: Path) -> str:
    try:
        value = str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return "."
    return value or "."


def ruleset_text(found: Detected, *, house: str = "ra-house@1", ci: CiSpec | None = None) -> str:
    """The starting ``hunter.yml``, with every detected path written in."""
    ci = ci or CiSpec()
    lines = [
        "# Rittman Hunter, project ruleset.",
        "#",
        "# This says what correct looks like for this repository. Everything not",
        "# named here comes from the house ruleset below, and any difference from",
        "# it is reported on the site's conventions page.",
        "",
        f"extends: {house}",
        "",
        "paths:",
        f"  dbt_project_dir: {found.dbt_project_dir}",
        "  manifest: target/manifest.json",
    ]

    if found.dbml:
        lines.append("  dbml:")
        lines.extend(f"    - {pattern}" for pattern in found.dbml)
    else:
        lines += [
            "  # No design files were found. Point this at your DBML when there is some.",
            "  dbml: []",
        ]

    if found.conceptual:
        lines.append(f"  conceptual_diagram: {found.conceptual}")
    if found.logical:
        lines.append(f"  logical_diagram: {found.logical}")

    if found.lookml:
        lines.append("  lookml:")
        lines.extend(f"    - {pattern}" for pattern in found.lookml)
    if found.droughty_dbml:
        lines.append("  droughty_dbml:")
        lines.extend(f"    - {pattern}" for pattern in found.droughty_dbml)

    lines += [
        "",
        "# Advisory means Hunter never fails a build. Leave it here for the first",
        "# few weeks: a tool that fails builds on day one gets switched off.",
        "pull_request:",
        "  mode: advisory",
        "",
        "# How CI gets dbt's manifest. `parse` runs dbt parse in CI and needs the",
        "# DBT_PROFILES_YML secret. `committed` unpacks a manifest kept in this",
        "# repository, no credential needed. `artifact` fetches it from this",
        "# repository's own dbt workflow. Change it here and rerun `hunter init",
        "# --force`: the workflow is regenerated to match, so the choice survives.",
        "ci:",
        f"  manifest_source: {ci.manifest_source}",
        *(
            [f"  manifest_path: {ci.manifest_path}"]
            if ci.manifest_source is ManifestSource.COMMITTED
            else [f"  # manifest_path: {ci.manifest_path}"]
        ),
        *(
            [
                f"  manifest_workflow: {ci.manifest_workflow or '<your-dbt-workflow>.yml'}",
                f"  manifest_artifact: {ci.manifest_artifact}",
            ]
            if ci.manifest_source is ManifestSource.ARTIFACT
            else ["  # manifest_workflow: dbt.yml", "  # manifest_artifact: manifest"]
        ),
        "",
        "# Where the site is published. Set it once GitHub Pages is switched on, and",
        "# the pull request comment links to the live dashboard as well as to the run",
        "# that produced it.",
        "# branding:",
        f"#   site_url: {found.pages_url or 'https://<organisation>.github.io/<repository>/'}",
        "",
        "# Switching a rule off. Uncomment the block, and say why: the reason is",
        "# published on the conventions page, which is the point of asking for it.",
        "# There is no silent switch for any rule. These are the ones repositories",
        "# most often change; `hunter rules` lists all 77.",
        "# rules:",
        "#   crosslayer.explore_no_caching_policy:   # explores need a datagroup",
        "#     enabled: false",
        "#     reason: this Looker instance caches at the connection, not per explore",
        "#   crosslayer.exposure_missing:            # tables Looker reads need an exposure",
        "#     enabled: false",
        "#     reason: exposures are declared in the LookML repository, not here",
        "#   structure.select_star_from_source:      # staging must name its columns",
        "#     enabled: false",
        "#     reason: staging deliberately takes every column and reshapes downstream",
        "#   documentation.owner_missing:            # every table names an owner",
        "#     severity: low",
        "#     reason: owners are being assigned team by team this quarter",
        "",
    ]

    if found.notes:
        lines += ["# Worth checking:", *[f"#   - {note}" for note in found.notes], ""]

    return "\n".join(lines)


def register_text(
    *,
    needs_owner: list[str] | None = None,
    off_plan: list[str] | None = None,
    today: dt.date | None = None,
) -> str:
    """The starting ``register.yml``, pre-filled with what Hunter would flag."""
    when = today or dt.date.today()
    review = when.replace(year=when.year + 1) if when.month != 2 or when.day != 29 else when

    lines = [
        "# Rittman Hunter, the authored register.",
        "#",
        "# hunter.yml says what correct looks like. This file records what the team",
        "# has decided about particular tables: that one is temporary on purpose,",
        "# that an off-plan build is accepted, who owns what, and what one row means.",
        "#",
        "# Plain information needs no reason. An exception or an approval does, and",
        "# a silenced rule needs an end date as well. Nothing here hides a finding:",
        "# an approved exception still appears on the site with its reason.",
        "",
        "version: 1",
        "",
    ]

    # An empty section is written as an explicit empty collection. A bare key
    # with only comments under it reads as null in YAML, and the first install
    # of Hunter shipped a register that `hunter score` then refused for exactly
    # that reason.
    owners = sorted(needs_owner or [])[:20]
    if owners:
        lines += [
            "models:",
            "  # Hunter found no owner for these. Fill in a team name against each.",
            "  # Owner is plain information, so no reason is needed.",
        ]
        for name in owners:
            lines += [
                f"  {name}:",
                "    owner:            # who to ask about this table",
                "    grain:            # what one row of it means, in plain words",
            ]
        if needs_owner and len(needs_owner) > len(owners):
            lines.append(
                f"  # and {len(needs_owner) - len(owners)} more. Run `hunter score` "
                "for the full list."
            )
    else:
        lines += [
            "models: {}",
            "  # Status is one of three words: temporary, verified or permanent.",
            "  # Temporary is a working step, or a table only ever meant to run once.",
            "  # Verified is permanent, and a named person has confirmed it should stay.",
            "  # Leave it out and Hunter works it out from the layer and materialisation.",
            "  #",
            "  # int_commerce__demand_transactions:",
            "  #   persistence: temporary",
            "  #   reason: intermediate step feeding the order fact, not for consumption",
            "  #   review_by: " + review.isoformat(),
            "  #",
            "  # wh_commerce__order_fact:",
            "  #   persistence: verified",
            "  #   verified_by: sav",
            "  #   verified_on: " + when.isoformat(),
            "  #   reason: signed off at the design review as the order fact of record",
        ]

    off = sorted(off_plan or [])[:10]
    if off:
        # Listed as comments, not entries. An approval needs a reason and a
        # named approver before the file is valid, so a live entry with blanks
        # would stop `hunter score` from running at all. The names are still
        # handed over; the team uncomments each one as it is decided.
        lines += [
            "",
            "off_plan_approved: []",
            "  # These are built and appear on no design. Either add each one to the",
            "  # design, or approve it here: uncomment the block, fill in the reason",
            "  # and the approver, and delete the [] on the line above.",
        ]
        for name in off:
            lines += [
                f"  # - model: {name}",
                "  #   reason:           # why this was built ahead of the design",
                "  #   approved_by:      # who accepted it",
                f"  #   review_by: {review.isoformat()}",
            ]
    else:
        lines += [
            "",
            "off_plan_approved: []",
            "  # Example:",
            "  #",
            "  # - model: wh_finance__ledger_fact",
            "  #   reason: built for the year-end close, design entry to follow",
            "  #   approved_by: sav",
            "  #   review_by: " + review.isoformat(),
        ]

    lines += [
        "",
        "ignores: []",
        "  # A silenced rule needs a reason and an end date. It comes back on that",
        "  # date automatically, so nothing goes quiet for good.",
        "  #",
        "  # - rule: documentation.model_description_missing",
        "  #   models: ['stg_legacy__*']",
        "  #   reason: legacy staging, scheduled for removal this quarter",
        "  #   expires: " + review.isoformat(),
        "",
    ]
    return "\n".join(lines)


#: Where the published actions live. The tag is the package version: every
#: composite action installs Hunter from `v<hunter-version>`, so the version
#: here, in pyproject.toml and in each action.yml must agree, and the tag must
#: exist on the remote. scripts/check_release.py enforces both.
ACTION_REPO = "sav-sus/Hunter"
DEFAULT_ACTION_REF = f"{ACTION_REPO}@v{__version__}"


def workflow_text(
    *,
    action_ref: str | None = None,
    dbt_project_dir: str = ".",
    adapter: str | None = None,
    profile: str | None = None,
    dbt_pins: list[str] | None = None,
    dbt_pins_source: str | None = None,
    ci: CiSpec | None = None,
) -> str:
    """The workflow a client repository needs. Section 11.6.

    One file, six jobs. The first builds the dbt manifest, because every Hunter
    command reads it and dbt's ``target/`` is never in a checkout. Then every
    pull request gets the score and the three sync checks, each as its own
    line on the pull request so one drifted layer does not hide another. A push
    to main rebuilds the dashboard and publishes it to GitHub Pages, so a
    stakeholder opens a link and never needs GitHub access. Nothing is
    filtered by path: a new layer is picked up on its own.
    """
    action_ref = action_ref or DEFAULT_ACTION_REF
    ci = ci or CiSpec()
    repo, _, tag = action_ref.partition("@")
    adapter_guessed = adapter is None
    adapter = adapter or "bigquery"
    profile = profile or "your_profile_name"
    target_dir = "target" if dbt_project_dir in ("", ".") else f"{dbt_project_dir}/target"
    manifest = f"{target_dir}/manifest.json"
    dbt_dir = dbt_project_dir or "."
    adapter_note = (
        ""
        if not adapter_guessed
        else "\n        # No profiles.yml in the repository, so the adapter is a guess. Change it."
    )
    if dbt_pins:
        packages = " ".join(f'"{pin}"' for pin in dbt_pins)
        if not any(pin.startswith("dbt-core") for pin in dbt_pins):
            packages = "dbt-core " + packages
        install_note = (
            f"\n        # Pinned to match {dbt_pins_source}, so CI parses with the dbt the team"
            "\n        # runs. A different dbt can write a different manifest."
        )
    else:
        packages = f"dbt-core dbt-{adapter}"
        install_note = (
            "\n        # Unpinned: no dbt version was found in the repository. CI then parses"
            "\n        # with the newest dbt, which can differ from the one the team runs and"
            "\n        # change the manifest Hunter scores. Pin it here once you know the"
            f'\n        # version, for example "dbt-core~=1.10" "dbt-{adapter}~=1.9".'
        )
    manifest_header, manifest_job = _manifest_pieces(
        ci,
        profile=profile,
        adapter=adapter,
        packages=packages,
        install_note=install_note,
        adapter_note=adapter_note,
        manifest=manifest,
    )
    return f"""# Rittman Hunter.
#
# What runs when:
#   a pull request    the dbt manifest is built, then the score, a comment on the
#                     pull request, and the three sync checks (LookML, Droughty,
#                     modelling) as separate lines
#   a push to main    the same, then the dashboard is rebuilt and published to
#                     GitHub Pages
#   Monday 06:00      the same as a push, to catch drift that arrived from
#                     outside a pull request
#
# No path filter on purpose. A new layer or a new model is detected by Hunter
# itself, so nothing here needs editing as the warehouse grows.
#
{manifest_header}
# GitHub Pages: in the repository settings, under Pages, set the source to
# "GitHub Actions" once. The publish job does the rest.
#
# fetch-depth: 0 on the score job matters. Attribution and showcase windows
# need full history, and the default shallow checkout has none.
name: Hunter

on:
  pull_request:
  push:
    branches: [main]
  schedule:
    - cron: '0 6 * * 1'
  # Run by hand from the Actions tab. A manual run counts as a push, so it is
  # the way to test publishing without merging anything.
  workflow_dispatch:

permissions:
  contents: read
  pull-requests: write

concurrency:
  group: hunter-${{{{ github.ref }}}}
  cancel-in-progress: true

env:
  DBT_PROJECT_DIR: {dbt_dir}
  MANIFEST: {manifest}

jobs:
{manifest_job}
  hunter:
    name: Score
    needs: manifest
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/download-artifact@v4
        with:
          name: dbt-manifest
          path: {target_dir}
      - uses: {action_ref}
        with:
          mode: advisory
          manifest: ${{{{ env.MANIFEST }}}}
          # The site is built on pull requests as well, so the comment's link
          # reaches a dashboard for this change. Only main is published.
          publish: true
      - name: Hand the dashboard to GitHub Pages
        if: github.event_name != 'pull_request'
        uses: actions/upload-pages-artifact@v3
        with:
          path: out/site/_built

  lookml-sync:
    name: LookML sync
    needs: manifest
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          name: dbt-manifest
          path: {target_dir}
      - uses: {repo}/actions/lookml-sync@{tag}
        with:
          manifest: ${{{{ env.MANIFEST }}}}
          fail-on: never

  droughty-sync:
    name: Droughty sync
    needs: manifest
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          name: dbt-manifest
          path: {target_dir}
      - uses: {repo}/actions/droughty-sync@{tag}
        with:
          manifest: ${{{{ env.MANIFEST }}}}
          fail-on: never

  modelling-sync:
    name: Modelling sync
    needs: manifest
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          name: dbt-manifest
          path: {target_dir}
      - uses: {repo}/actions/modelling-sync@{tag}
        with:
          manifest: ${{{{ env.MANIFEST }}}}
          fail-on: never

  publish:
    name: Publish the dashboard
    if: github.event_name != 'pull_request'
    needs: hunter
    runs-on: ubuntu-latest
    permissions:
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{{{ steps.deploy.outputs.page_url }}}}
    steps:
      - id: deploy
        uses: actions/deploy-pages@v4
"""


def _manifest_pieces(
    ci: CiSpec,
    *,
    profile: str,
    adapter: str,
    packages: str,
    install_note: str,
    adapter_note: str,
    manifest: str,
) -> tuple[str, str]:
    """The header comment and the first job, for the chosen manifest source.

    Three ways CI can get dbt's manifest, chosen at ``hunter init`` and kept in
    hunter.yml under ``ci``, so regenerating the workflow keeps the choice
    instead of handing the client the default to edit by hand again.
    """
    common = (
        "# ---------------------------------------------------------------------------\n"
        "# HOW CI GETS DBT'S MANIFEST\n"
        "#\n"
        "# Every Hunter command reads dbt's manifest.json, and dbt writes it under\n"
        "# target/, which is gitignored, so a checkout never has one. The first job\n"
        f"# below supplies it. Source: {ci.manifest_source}. To change it, run\n"
        "#   hunter init --force --manifest-source parse|committed|artifact\n"
        "# or edit `ci:` in .hunter/hunter.yml and rerun `hunter init --force`.\n"
    )
    if ci.manifest_source is ManifestSource.COMMITTED:
        header = common + (
            "#\n"
            "# committed: a manifest kept in the repository, gzipped or plain, at\n"
            f"#   {ci.manifest_path}\n"
            "# No warehouse credential is needed. Refresh it whenever models change,\n"
            "# or the sync checks will report drift that is only staleness:\n"
            "#   dbt parse && gzip -c target/manifest.json > <that path>\n"
            "# ---------------------------------------------------------------------------\n"
        )
        job = f"""  manifest:
    name: Unpack the committed dbt manifest
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Unpack {ci.manifest_path}
        run: |
          set -euo pipefail
          src="{ci.manifest_path}"
          if [ ! -f "$src" ]; then
            echo "::error title=No committed manifest at $src::Hunter reads dbt's manifest and" \\
              "this workflow expects one committed at $src. Create it with: dbt parse &&" \\
              "gzip -c target/manifest.json > $src. Or choose another source with" \\
              "hunter init --force --manifest-source parse|artifact."
            exit 1
          fi
          mkdir -p "$(dirname "$MANIFEST")"
          case "$src" in
            *.gz) gunzip -c "$src" > "$MANIFEST" ;;
            *) cp "$src" "$MANIFEST" ;;
          esac
      - uses: actions/upload-artifact@v4
        with:
          name: dbt-manifest
          path: ${{{{ env.MANIFEST }}}}
          if-no-files-found: error
"""
        return header, job

    if ci.manifest_source is ManifestSource.ARTIFACT:
        workflow = ci.manifest_workflow or "<your-dbt-workflow>.yml"
        placeholder = (
            ""
            if ci.manifest_workflow
            else "# SET THIS FIRST: manifest_workflow in .hunter/hunter.yml, the workflow file\n"
            "# in this repository that runs dbt, then rerun `hunter init --force`.\n"
        )
        header = common + (
            "#\n"
            "# artifact: fetched from the latest successful run of this repository's own\n"
            f"# dbt workflow, {workflow}, from the artifact named\n"
            f"# {ci.manifest_artifact!r}. That workflow must upload manifest.json under\n"
            "# that name. No warehouse credential is needed here; dbt already ran.\n"
            + placeholder
            + "# ---------------------------------------------------------------------------\n"
        )
        job = f"""  manifest:
    name: Fetch the dbt manifest from {workflow}
    runs-on: ubuntu-latest
    permissions:
      contents: read
      actions: read
    steps:
      - name: Download the manifest artifact from the latest successful run
        env:
          GH_TOKEN: ${{{{ github.token }}}}
        run: |
          set -euo pipefail
          run_id=$(gh run list --repo "$GITHUB_REPOSITORY" --workflow "{workflow}" \\
            --branch main --status success --limit 1 --json databaseId --jq '.[0].databaseId')
          if [ -z "$run_id" ]; then
            echo "::error title=No successful run of {workflow}::Hunter fetches dbt's manifest" \\
              "from that workflow's {ci.manifest_artifact!r} artifact and found no successful" \\
              "run on main. Check ci.manifest_workflow in .hunter/hunter.yml."
            exit 1
          fi
          mkdir -p "$(dirname "$MANIFEST")"
          gh run download "$run_id" --repo "$GITHUB_REPOSITORY" \\
            --name "{ci.manifest_artifact}" --dir manifest-download
          found=$(find manifest-download -name manifest.json | head -1)
          if [ -z "$found" ]; then
            echo "::error title=No manifest.json in artifact {ci.manifest_artifact!r}::The" \\
              "artifact was downloaded but holds no manifest.json. Check ci.manifest_artifact" \\
              "in .hunter/hunter.yml against what {workflow} uploads."
            exit 1
          fi
          mv "$found" "$MANIFEST"
      - uses: actions/upload-artifact@v4
        with:
          name: dbt-manifest
          path: ${{{{ env.MANIFEST }}}}
          if-no-files-found: error
"""
        return header, job

    header = common + (
        "#\n"
        "# parse: runs `dbt parse` here. That does not connect to the warehouse, but\n"
        "# dbt will not start without a profile it can resolve, so CI needs one, as\n"
        "# two repository secrets:\n"
        "#\n"
        "#   DBT_PROFILES_YML    the whole contents of a profiles.yml for CI. For\n"
        "#                       BigQuery with a service account, for example:\n"
        "#\n"
        f"#                         {profile}:\n"
        "#                           target: ci\n"
        "#                           outputs:\n"
        "#                             ci:\n"
        f"#                               type: {adapter}\n"
        "#                               method: service-account\n"
        "#                               keyfile: /home/runner/.dbt/keyfile.json\n"
        "#                               project: your-gcp-project\n"
        "#                               dataset: hunter_ci\n"
        "#                               threads: 4\n"
        "#\n"
        "#   DBT_KEYFILE_JSON    the service account key as JSON. Written to\n"
        "#                       /home/runner/.dbt/keyfile.json, the path the profile\n"
        "#                       above points at. Leave it unset for adapters that\n"
        "#                       authenticate another way.\n"
        "#\n"
        "# Add both under Settings, Secrets and variables, Actions. Without the first,\n"
        "# the manifest job stops with a message naming it, and nothing else runs.\n"
        "#\n"
        "# NO CREDENTIAL FOR CI? Use `committed` (a manifest kept in the repository) or\n"
        "# `artifact` (fetched from your own dbt workflow). Neither needs a secret.\n"
        "# ---------------------------------------------------------------------------\n"
    )
    job = f"""  manifest:
    name: Build the dbt manifest
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dbt
        run: pip install --quiet {packages}{install_note}{adapter_note}
      - name: Write the dbt profile from the repository secrets
        env:
          DBT_PROFILES_YML: ${{{{ secrets.DBT_PROFILES_YML }}}}
          DBT_KEYFILE_JSON: ${{{{ secrets.DBT_KEYFILE_JSON }}}}
        run: |
          set -euo pipefail
          if [ -z "$DBT_PROFILES_YML" ]; then
            echo "::error title=Missing secret DBT_PROFILES_YML::Hunter reads dbt's manifest," \\
              "and building one needs a dbt profile. Add a repository secret named" \\
              "DBT_PROFILES_YML holding a profiles.yml for CI. The comment at the top of" \\
              ".github/workflows/hunter.yml shows one. No credential? Run" \\
              "hunter init --force --manifest-source committed."
            exit 1
          fi
          mkdir -p "$HOME/.dbt"
          printf '%s\\n' "$DBT_PROFILES_YML" > "$HOME/.dbt/profiles.yml"
          if [ -n "$DBT_KEYFILE_JSON" ]; then
            printf '%s\\n' "$DBT_KEYFILE_JSON" > "$HOME/.dbt/keyfile.json"
          fi
      - name: dbt deps
        working-directory: ${{{{ env.DBT_PROJECT_DIR }}}}
        run: dbt deps
      - name: dbt parse
        working-directory: ${{{{ env.DBT_PROJECT_DIR }}}}
        run: dbt parse
      - uses: actions/upload-artifact@v4
        with:
          name: dbt-manifest
          path: ${{{{ env.MANIFEST }}}}
          if-no-files-found: error
"""
    return header, job


STAMP_PREFIX = "# Written by hunter init"


def stamp(text: str) -> str:
    """Prefix generated text with a line that fingerprints the rest of it.

    The fingerprint is how a later ``hunter init`` tells a file nobody touched,
    which it can refresh, from one somebody spent an afternoon getting right,
    which it must not overwrite without being told to.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return (
        f"{STAMP_PREFIX} {__version__}, fingerprint {digest}. Edit freely: init refuses to\n"
        "# overwrite an edited file unless run with --force, and then keeps a .bak copy.\n" + text
    )


def file_state(path: Path) -> str:
    """``missing``, ``pristine`` (as generated), ``edited``, or ``foreign``."""
    if not path.exists():
        return "missing"
    text = path.read_text(encoding="utf-8")
    first, _, rest = text.partition("\n")
    if not first.startswith(STAMP_PREFIX):
        return "foreign"
    match = re.search(r"fingerprint ([0-9a-f]{12})", first)
    _, _, body = rest.partition("\n")
    if match is None:
        return "foreign"
    return (
        "pristine"
        if hashlib.sha256(body.encode("utf-8")).hexdigest()[:12] == match.group(1)
        else "edited"
    )


def _difference(path: Path, fresh: str) -> str:
    """How far an existing file is from what init would write now, in one clause."""
    current = path.read_text(encoding="utf-8").splitlines()
    proposed = fresh.splitlines()
    diff = list(difflib.ndiff(current, proposed))
    added = sum(1 for line in diff if line.startswith("+ "))
    removed = sum(1 for line in diff if line.startswith("- "))
    lost = "1 line" if removed == 1 else f"{removed} lines"
    return f"{lost} of yours would be lost, {added} added"


@dataclass
class ScaffoldOutcome:
    """What ``scaffold`` did to each file, so init can say so."""

    created: list[Path] = field(default_factory=list)
    refreshed: list[Path] = field(default_factory=list)
    overwritten: dict[Path, Path] = field(default_factory=dict)  # path -> backup

    @property
    def written(self) -> list[Path]:
        return sorted([*self.created, *self.refreshed, *self.overwritten])


def scaffold(
    root: Path,
    *,
    force: bool = False,
    needs_owner: list[str] | None = None,
    off_plan: list[str] | None = None,
    today: dt.date | None = None,
    write_workflow: bool = True,
    ci: CiSpec | None = None,
) -> ScaffoldOutcome:
    """Write the ruleset, the register and the workflow.

    A file that is exactly as init last wrote it is refreshed. A file somebody
    has edited, or that init did not write, is left alone and named, unless
    ``force`` is given, in which case the old file is kept beside the new one
    as ``<name>.bak``.

    Raises:
        FileExistsError: an edited or foreign file is in the way and ``force``
            is not set. The message names each file and what would be lost.
    """
    found = detect(root)
    ci = ci or CiSpec()
    targets: dict[Path, str] = {
        root / ".hunter" / "hunter.yml": stamp(ruleset_text(found, ci=ci)),
        root / ".hunter" / "register.yml": stamp(
            register_text(needs_owner=needs_owner, off_plan=off_plan, today=today)
        ),
    }
    if write_workflow:
        targets[root / ".github" / "workflows" / "hunter.yml"] = stamp(
            workflow_text(
                dbt_project_dir=found.dbt_project_dir,
                adapter=found.adapter,
                profile=found.profile,
                dbt_pins=found.dbt_pins,
                dbt_pins_source=found.dbt_pins_source,
                ci=ci,
            )
        )

    states = {path: file_state(path) for path in targets}
    blocking = {path: state for path, state in states.items() if state in ("edited", "foreign")}
    if blocking and not force:
        lines = ["These files are in the way, and init will not discard them:"]
        for path, state in sorted(blocking.items()):
            why = (
                "edited since init wrote it" if state == "edited" else "not written by hunter init"
            )
            lines.append(f"  {path.relative_to(root)}: {why}; {_difference(path, targets[path])}")
        lines.append(
            "Run again with --force to overwrite them. Each old file is kept beside the "
            "new one as <name>.bak."
        )
        raise FileExistsError("\n".join(lines))

    outcome = ScaffoldOutcome()
    for path, text in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        state = states[path]
        if state in ("edited", "foreign"):
            backup = path.with_name(path.name + ".bak")
            backup.write_bytes(path.read_bytes())
            outcome.overwritten[path] = backup
        elif state == "pristine":
            outcome.refreshed.append(path)
        else:
            outcome.created.append(path)
        path.write_text(text, encoding="utf-8")
    return outcome
