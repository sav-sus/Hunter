"""Read authorship and commit windows from git history.

Two things depend on this: attribution (F6) and the showcase window (F12).

Attribution exists so debt can be routed to whoever can fix it. FR6.3 forbids a
per-person league table, and the reasoning is in the requirements document: a
public ranking moves contributor behaviour towards avoiding blame rather than
towards quality, and the tool loses its audience. So this module records author
names for routing, and the emit layer reports by team and domain.

History is read in a single ``git log`` pass rather than one call per file. A
call per file would be 280 subprocesses on the pilot repository and would put
the run well outside the 5-minute budget in NFR1.

A shallow clone has no history to read. That is why ``fetch-depth: 0`` matters
in the Action, and it is reported rather than silently producing no attribution.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

from git import InvalidGitRepositoryError, NoSuchPathError, Repo
from git.exc import GitCommandError

from hunter.model.entities import ParseIssue

#: Field and record separators. Chosen because they cannot appear in a commit
#: subject, unlike any printable delimiter.
FIELD_SEP = "\x1f"
RECORD_SEP = "\x1e"

#: ``Merge pull request #1184 from org/branch-name``
MERGE_PR = re.compile(r"Merge pull request #(?P<number>\d+) from (?P<branch>\S+)")

#: ``(#1184)`` at the end of a squash-merge subject.
SQUASH_PR = re.compile(r"\(#(?P<number>\d+)\)\s*$")

#: Commit trailer, e.g. ``Refs: DA-5411``.
TRAILER = re.compile(r"^(?P<key>[A-Za-z-]+):\s*(?P<value>.+)$", re.MULTILINE)


@dataclass(frozen=True)
class CommitInfo:
    """One commit, as much as Hunter needs of it."""

    sha: str
    author: str
    authored_on: dt.date
    subject: str
    body: str = ""
    files: tuple[str, ...] = ()

    @property
    def pull_request(self) -> str | None:
        match = MERGE_PR.search(self.subject) or SQUASH_PR.search(self.subject)
        return match.group("number") if match else None

    @property
    def merge_branch(self) -> str | None:
        match = MERGE_PR.search(self.subject)
        return match.group("branch") if match else None

    @property
    def trailers(self) -> dict[str, str]:
        """Trailers from the commit body, e.g. ``Refs: DA-5411``."""
        return trailers(self.body)

    def tickets(self, pattern: str) -> list[str]:
        """Ticket references in the subject, merge branch name or body. FR12.8.

        A squash merge loses the branch name, so the body and trailers are the
        only places a reference survives. Projects whose subjects do not carry
        one can widen ``integrations.jira.ticket_pattern``.
        """
        try:
            ticket = re.compile(pattern)
        except re.error:
            return []
        haystack = " ".join(filter(None, [self.subject, self.merge_branch, self.body]))
        return sorted(set(ticket.findall(haystack)))


@dataclass
class FileHistory:
    """Who created a file and who touched it last."""

    path: str
    created_by: str | None = None
    created_at: dt.date | None = None
    created_commit: str | None = None
    created_in_pr: str | None = None
    last_modified_by: str | None = None
    last_modified_at: dt.date | None = None
    last_commit: str | None = None
    change_count: int = 0


@dataclass
class GitData:
    """What git history yielded."""

    histories: dict[str, FileHistory] = field(default_factory=dict)
    commits: list[CommitInfo] = field(default_factory=list)
    available: bool = False
    is_shallow: bool = False
    head_sha: str | None = None
    branch: str | None = None
    issues: list[ParseIssue] = field(default_factory=list)

    def history(self, path: str) -> FileHistory | None:
        return self.histories.get(path)

    def commits_between(self, start: dt.date, end: dt.date) -> list[CommitInfo]:
        return [commit for commit in self.commits if start <= commit.authored_on <= end]

    def pull_requests_between(self, start: dt.date, end: dt.date) -> list[CommitInfo]:
        return [
            commit for commit in self.commits_between(start, end) if commit.pull_request is not None
        ]

    def authors(self) -> list[str]:
        """Distinct authors, sorted. For routing, never for ranking. FR6.3."""
        return sorted({commit.author for commit in self.commits if commit.author})


def open_repo(root: Path) -> tuple[Repo | None, list[ParseIssue]]:
    """Open a repository, reporting rather than raising when there is none."""
    issues: list[ParseIssue] = []
    try:
        return Repo(root, search_parent_directories=True), issues
    except (InvalidGitRepositoryError, NoSuchPathError):
        issues.append(
            ParseIssue(
                source=str(root),
                message=(
                    "this is not a git repository, so authorship and the showcase "
                    "window are unavailable. Every other dimension still scores."
                ),
                recoverable=True,
            )
        )
        return None, issues


def _parse_log(output: str) -> list[CommitInfo]:
    """Parse one ``git log`` pass into commits with their changed files."""
    commits: list[CommitInfo] = []
    for record in output.split(RECORD_SEP):
        block = record.strip("\n")
        if not block.strip():
            continue
        # The body may span lines, so split on the field separator first and
        # take whatever follows the final one as the changed-file list.
        parts = block.split(FIELD_SEP)
        if len(parts) < 6:
            continue
        sha, author, authored, subject, body = parts[0], parts[1], parts[2], parts[3], parts[4]
        files_block = parts[5]
        try:
            authored_on = dt.datetime.fromisoformat(authored).date()
        except ValueError:
            continue
        files = tuple(sorted({line.strip() for line in files_block.splitlines() if line.strip()}))
        commits.append(
            CommitInfo(
                sha=sha.strip(),
                author=author.strip(),
                authored_on=authored_on,
                subject=subject.strip(),
                body=body.strip(),
                files=files,
            )
        )
    return commits


def load_git(root: Path, *, max_commits: int | None = None) -> GitData:
    """Read history in one pass and build per-file attribution.

    Args:
        root: any path inside the repository.
        max_commits: cap the traversal. Useful on very large histories; leaving
            it unset reads everything, which is what attribution needs.
    """
    data = GitData()
    repo, issues = open_repo(root)
    data.issues.extend(issues)
    if repo is None:
        return data

    data.available = True
    try:
        data.head_sha = repo.head.commit.hexsha
    except (ValueError, GitCommandError):
        data.issues.append(
            ParseIssue(
                source=str(root),
                message="the repository has no commits yet, so there is no history to read.",
                recoverable=True,
            )
        )
        return data

    try:
        data.branch = repo.active_branch.name
    except TypeError:
        data.branch = None  # detached HEAD, which is normal in CI

    try:
        data.is_shallow = repo.git.rev_parse("--is-shallow-repository").strip() == "true"
    except GitCommandError:
        data.is_shallow = False

    if data.is_shallow:
        data.issues.append(
            ParseIssue(
                source=str(root),
                message=(
                    "this is a shallow clone, so authorship and showcase windows are "
                    "incomplete. Set fetch-depth: 0 on the checkout step."
                ),
                recoverable=True,
            )
        )

    # The body is captured so commit trailers such as "Refs: DA-5411" are
    # readable. Rename detection is left at the git default: a renamed model
    # keeps the history of its current path, which is what a reader expects.
    args = [
        f"--format={RECORD_SEP}%H{FIELD_SEP}%an{FIELD_SEP}%aI{FIELD_SEP}%s{FIELD_SEP}%b{FIELD_SEP}",
        "--name-only",
    ]
    if max_commits:
        args.append(f"-n{max_commits}")

    try:
        output = repo.git.log(*args)
    except GitCommandError as exc:
        data.issues.append(
            ParseIssue(
                source=str(root),
                message=f"could not read history: {exc}",
                recoverable=True,
            )
        )
        return data

    # git log is newest first. Attribution needs both ends, so walk it once and
    # let the oldest entry win for creation and the newest for last change.
    commits = _parse_log(output)
    data.commits = commits

    for commit in commits:
        for path in commit.files:
            history = data.histories.get(path)
            if history is None:
                history = FileHistory(path=path)
                data.histories[path] = history
                history.last_modified_by = commit.author
                history.last_modified_at = commit.authored_on
                history.last_commit = commit.sha
            history.change_count += 1
            # Newest first, so every later iteration is older
            history.created_by = commit.author
            history.created_at = commit.authored_on
            history.created_commit = commit.sha
            if commit.pull_request:
                history.created_in_pr = commit.pull_request

    return data


def trailers(message: str) -> dict[str, str]:
    """Trailers from a commit message body, e.g. ``Refs: DA-5411``."""
    out: dict[str, str] = {}
    for match in TRAILER.finditer(message):
        out[match.group("key").strip().lower()] = match.group("value").strip()
    return out


def tickets_in(text: str, pattern: str) -> list[str]:
    """Ticket references matching a project's pattern. FR12.8."""
    try:
        return sorted(set(re.compile(pattern).findall(text)))
    except re.error:
        return []
