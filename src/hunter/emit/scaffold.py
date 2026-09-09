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
from pathlib import Path

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


def _as_relative(path: Path, root: Path) -> str:
    try:
        value = str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return "."
    return value or "."


def ruleset_text(found: Detected, *, house: str = "ra-house@1") -> str:
    """The starting ``hunter.yml``, with every detected path written in."""
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
        "# Uncomment to change a rule, and say why. The reason is published on the",
        "# conventions page, which is the point of asking for it.",
        "# rules:",
        "#   structure.select_star_from_source:",
        "#     enabled: false",
        "#     reason: staging deliberately takes every column and reshapes downstream",
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
        "models:",
    ]

    owners = sorted(needs_owner or [])[:20]
    if owners:
        lines += [
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

    lines += ["", "off_plan_approved:"]
    off = sorted(off_plan or [])[:10]
    if off:
        lines += [
            "  # These are built and appear on no design. Either add them to the",
            "  # design, or accept them here with a reason and a review date.",
        ]
        for name in off:
            lines += [
                f"  - model: {name}",
                "    reason:           # why this was built ahead of the design",
                "    approved_by:      # who accepted it",
                f"    review_by: {review.isoformat()}",
            ]
    else:
        lines += [
            "  # Example:",
            "  #",
            "  # - model: wh_finance__ledger_fact",
            "  #   reason: built for the year-end close, design entry to follow",
            "  #   approved_by: sav",
            "  #   review_by: " + review.isoformat(),
        ]

    lines += [
        "",
        "ignores:",
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


def workflow_text(*, action_ref: str = "sav-sus/Hunter@v0.1.0") -> str:
    """The workflow a client repository needs. Section 11.6.

    One file, five jobs. Every pull request gets the score and the three sync
    checks, each as its own line on the pull request so one drifted layer does
    not hide another. A push to main rebuilds the dashboard and publishes it to
    GitHub Pages, so a stakeholder opens a link and never needs GitHub access.
    Nothing is filtered by path: a new layer is picked up on its own.
    """
    repo, _, tag = action_ref.partition("@")
    return f"""# Rittman Hunter.
#
# What runs when:
#   a pull request    the score, a comment on the pull request, and the three
#                     sync checks (LookML, Droughty, modelling) as separate lines
#   a push to main    the same, then the dashboard is rebuilt and published to
#                     GitHub Pages
#   Monday 06:00      the same as a push, to catch drift that arrived from
#                     outside a pull request
#
# No path filter on purpose. A new layer or a new model is detected by Hunter
# itself, so nothing here needs editing as the warehouse grows.
#
# fetch-depth: 0 matters. Attribution and showcase windows need full history,
# and the default shallow checkout has none.
#
# GitHub Pages: in the repository settings, under Pages, set the source to
# "GitHub Actions" once. The publish job does the rest.
name: Hunter

on:
  pull_request:
  push:
    branches: [main]
  schedule:
    - cron: '0 6 * * 1'

permissions:
  contents: read
  pull-requests: write

concurrency:
  group: hunter-${{{{ github.ref }}}}
  cancel-in-progress: true

jobs:
  hunter:
    name: Score
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: {action_ref}
        with:
          mode: advisory
          publish: ${{{{ github.event_name != 'pull_request' }}}}
      - name: Hand the dashboard to GitHub Pages
        if: github.event_name != 'pull_request'
        uses: actions/upload-pages-artifact@v3
        with:
          path: out/site/_built

  lookml-sync:
    name: LookML sync
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: {repo}/actions/lookml-sync@{tag}
        with:
          fail-on: never

  droughty-sync:
    name: Droughty sync
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: {repo}/actions/droughty-sync@{tag}
        with:
          fail-on: never

  modelling-sync:
    name: Modelling sync
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: {repo}/actions/modelling-sync@{tag}
        with:
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


def scaffold(
    root: Path,
    *,
    force: bool = False,
    needs_owner: list[str] | None = None,
    off_plan: list[str] | None = None,
    today: dt.date | None = None,
    write_workflow: bool = True,
) -> list[Path]:
    """Write the ruleset, the register and the workflow.

    Raises:
        FileExistsError: a target already exists and ``force`` is not set.
            Overwriting a ruleset somebody has tuned would be worse than
            refusing.
    """
    found = detect(root)
    targets: dict[Path, str] = {
        root / ".hunter" / "hunter.yml": ruleset_text(found),
        root / ".hunter" / "register.yml": register_text(
            needs_owner=needs_owner, off_plan=off_plan, today=today
        ),
    }
    if write_workflow:
        targets[root / ".github" / "workflows" / "hunter.yml"] = workflow_text()

    if not force:
        existing = [path for path in targets if path.exists()]
        if existing:
            names = ", ".join(str(path.relative_to(root)) for path in sorted(existing))
            raise FileExistsError(f"These already exist: {names}")

    written: list[Path] = []
    for path, text in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return sorted(written)
