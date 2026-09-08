"""The showcase: what changed in a window, and what it means.

F12. Every fact here is computed from git history and the manifest. FR12.9's
written narrative is milestone M3, and until then the showcase is facts with
plain-language headings rather than prose.

FR12.12 is the rule that shapes it: debt created is reported beside work
delivered. A showcase that lists only achievements is marketing, not reporting.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

from hunter.ingest.git import CommitInfo, GitData, load_git
from hunter.run import RunResult

#: A file that defines a model, so a change to it is a change to the model.
MODEL_FILE = re.compile(r"\.sql$|\.py$", re.IGNORECASE)
LOOKML_FILE = re.compile(r"\.lkml$|\.lookml$", re.IGNORECASE)
DESIGN_FILE = re.compile(r"\.dbml$|\.mermaid$", re.IGNORECASE)


@dataclass
class Window:
    """The period a showcase covers. FR12.1."""

    start: dt.date
    end: dt.date
    label: str

    @classmethod
    def last_days(cls, days: int, *, end: dt.date | None = None) -> Window:
        finish = end or dt.date.today()
        start = finish - dt.timedelta(days=days)
        return cls(start=start, end=finish, label=f"the last {days} days")

    @property
    def days(self) -> int:
        return (self.end - self.start).days


@dataclass
class Showcase:
    """What happened in the window."""

    window: Window
    commits: list[CommitInfo] = field(default_factory=list)
    pull_requests: list[CommitInfo] = field(default_factory=list)
    models_added: list[str] = field(default_factory=list)
    models_changed: list[str] = field(default_factory=list)
    models_removed: list[str] = field(default_factory=list)
    lookml_files_changed: list[str] = field(default_factory=list)
    design_files_changed: list[str] = field(default_factory=list)
    tickets: list[str] = field(default_factory=list)
    contributors: list[str] = field(default_factory=list)
    debt_created: int = 0
    debt_context: str = ""

    @property
    def delivered_anything(self) -> bool:
        return bool(self.models_added or self.models_changed or self.pull_requests)


def _model_name_from_path(path: str) -> str | None:
    if not MODEL_FILE.search(path):
        return None
    name = Path(path).stem
    return name or None


def build_showcase(
    result: RunResult,
    *,
    window: Window,
    git: GitData | None = None,
    root: Path | None = None,
) -> Showcase:
    """Assemble the showcase for one window."""
    history = git
    if history is None and root is not None:
        history = load_git(root)
    showcase = Showcase(window=window)
    if history is None or not history.available:
        # FR12.12 says debt is reported beside delivery, always. With no
        # history there is no delivery to report either, and saying why beats
        # leaving the section blank.
        showcase.debt_context = (
            "No usable history, so nothing in this window can be attributed. "
            f"Across the whole repository there are {len(result.open_findings)} "
            "open findings."
        )
        return showcase

    commits = history.commits_between(window.start, window.end)
    showcase.commits = commits
    showcase.pull_requests = [commit for commit in commits if commit.pull_request is not None]
    showcase.contributors = sorted({commit.author for commit in commits if commit.author})

    pattern = result.config.integrations.jira.ticket_pattern
    tickets: set[str] = set()
    for commit in commits:
        tickets.update(commit.tickets(pattern))
    showcase.tickets = sorted(tickets)

    known = result.project.model_names()
    touched: set[str] = set()
    lookml: set[str] = set()
    design: set[str] = set()
    for commit in commits:
        for path in commit.files:
            if LOOKML_FILE.search(path):
                lookml.add(path)
            elif DESIGN_FILE.search(path):
                design.add(path)
            name = _model_name_from_path(path)
            if name:
                touched.add(name)

    showcase.lookml_files_changed = sorted(lookml)
    showcase.design_files_changed = sorted(design)

    # A model whose file first appeared inside the window is new. One that
    # exists in the manifest and was touched is changed. One that was touched
    # and is not in the manifest has gone.
    for name in sorted(touched):
        model = result.project.any_model(name)
        if model is None:
            showcase.models_removed.append(name)
            continue
        if model.created_at is not None and window.start <= model.created_at <= window.end:
            showcase.models_added.append(name)
        else:
            showcase.models_changed.append(name)

    showcase.models_added.sort()
    showcase.models_changed.sort()
    showcase.models_removed.sort()

    # FR12.12: debt created is reported beside work delivered. Attributed to a
    # model touched in the window, since a finding carries no date of its own
    # without a previous report to compare against.
    changed_models = set(showcase.models_added) | set(showcase.models_changed)
    debt = [
        finding
        for finding in result.open_findings
        if finding.subject in changed_models and finding.severity.value in {"high", "medium"}
    ]
    showcase.debt_created = len(debt)
    showcase.debt_context = (
        f"{len(debt)} findings worth attention sit on the "
        f"{len(changed_models)} tables this window touched."
        if changed_models
        else "No tables were touched in this window."
    )
    _ = known
    return showcase


def showcase_page(result: RunResult, showcase: Showcase) -> str:
    """The showcase as a site page. FR12.10."""
    from hunter.emit.markdown import table, timestamp

    window = showcase.window
    out = [
        f"# What changed in {window.label}",
        "",
        f"{window.start.isoformat()} to {window.end.isoformat()}, {window.days} days.",
        "",
    ]

    if not showcase.commits:
        out += [
            "Nothing was committed in this window.",
            "",
            showcase.debt_context,
            timestamp(result, "History read"),
        ]
        return "\n".join(out)

    out += [
        "## In summary",
        "",
        table(
            ["Measure", "Count"],
            [
                ["Merged pull requests", len(showcase.pull_requests)],
                ["Commits", len(showcase.commits)],
                ["People who contributed", len(showcase.contributors)],
                ["Tables added", len(showcase.models_added)],
                ["Tables changed", len(showcase.models_changed)],
                ["Tables removed", len(showcase.models_removed)],
                ["Reporting files changed", len(showcase.lookml_files_changed)],
                ["Design files changed", len(showcase.design_files_changed)],
                ["Tickets referenced", len(showcase.tickets)],
            ],
        ),
        "",
        "## Alongside that",
        "",
        showcase.debt_context,
        "",
        "This section is always here. A showcase that lists only what was "
        "delivered is marketing rather than reporting.",
        "",
    ]

    if showcase.models_added:
        out += [
            "## Tables added",
            "",
            table(
                ["Table", "Area", "State", "Written by"],
                [_model_row(result, name) for name in showcase.models_added],
            ),
            "",
        ]

    if showcase.models_changed:
        out += [
            "## Tables changed",
            "",
            table(
                ["Table", "Area", "State", "Last changed by"],
                [_model_row(result, name, changed=True) for name in showcase.models_changed],
            ),
            "",
        ]

    if showcase.pull_requests:
        out += [
            "## Merged pull requests",
            "",
            table(
                ["Number", "Title", "Author", "Date", "Tickets"],
                [
                    [
                        f"#{commit.pull_request}",
                        commit.subject,
                        commit.author,
                        commit.authored_on.isoformat(),
                        ", ".join(commit.tickets(result.config.integrations.jira.ticket_pattern))
                        or "-",
                    ]
                    for commit in sorted(showcase.pull_requests, key=lambda item: item.authored_on)
                ],
            ),
            "",
        ]

    if showcase.design_files_changed:
        out += [
            "## Design changed",
            "",
            "The design files themselves changed in this window, so the "
            "reconciliation on this site reflects a newer design than the "
            "previous run did.",
            "",
            table(["File"], [[path] for path in showcase.design_files_changed]),
            "",
        ]

    out.append(timestamp(result, "History read"))
    return "\n".join(out)


def _model_row(result: RunResult, name: str, *, changed: bool = False) -> list[object]:
    model = result.project.any_model(name)
    row = next((item for item in result.alignment.rows if item.model_name == name), None)
    who = (model.last_modified_by if changed else model.created_by) if model else None
    return [
        name,
        (model.domain if model else None) or "-",
        row.state_label if row else "-",
        who or "unknown",
    ]
