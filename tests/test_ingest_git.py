"""Reading authorship and commit windows."""

from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path

import pytest

from hunter.ingest.git import CommitInfo, load_git, tickets_in, trailers


def run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A small repository with two commits by different authors."""
    root = tmp_path / "repo"
    root.mkdir()
    run(["git", "init", "-q", "-b", "main"], root)
    run(["git", "config", "user.email", "first@example.com"], root)
    run(["git", "config", "user.name", "First Author"], root)
    run(["git", "config", "commit.gpgsign", "false"], root)

    (root / "models").mkdir()
    (root / "models" / "orders.sql").write_text("select 1\n", encoding="utf-8")
    run(["git", "add", "-A"], root)
    run(["git", "commit", "-q", "-m", "Add orders model\n\nRefs: DA-1001"], root)

    run(["git", "config", "user.name", "Second Author"], root)
    (root / "models" / "orders.sql").write_text("select 2\n", encoding="utf-8")
    (root / "models" / "customers.sql").write_text("select 3\n", encoding="utf-8")
    run(["git", "add", "-A"], root)
    run(["git", "commit", "-q", "-m", "Change orders and add customers (#42)"], root)
    return root


class TestLoadGit:
    def test_history_is_read(self, repo: Path) -> None:
        data = load_git(repo)
        assert data.available
        assert not data.is_shallow
        assert len(data.commits) == 2
        assert data.branch == "main"
        assert data.head_sha

    def test_creation_is_the_oldest_commit_touching_a_file(self, repo: Path) -> None:
        history = load_git(repo).history("models/orders.sql")
        assert history is not None
        assert history.created_by == "First Author"
        assert history.change_count == 2

    def test_last_change_is_the_newest_commit(self, repo: Path) -> None:
        history = load_git(repo).history("models/orders.sql")
        assert history.last_modified_by == "Second Author"
        assert history.last_commit != history.created_commit

    def test_a_file_touched_once_has_the_same_commit_at_both_ends(self, repo: Path) -> None:
        history = load_git(repo).history("models/customers.sql")
        assert history.created_by == "Second Author"
        assert history.created_commit == history.last_commit
        assert history.change_count == 1

    def test_authors_are_sorted_and_deduplicated(self, repo: Path) -> None:
        """Sorted for determinism, and for routing rather than ranking. FR6.3."""
        assert load_git(repo).authors() == ["First Author", "Second Author"]

    def test_a_window_selects_by_date(self, repo: Path) -> None:
        data = load_git(repo)
        today = dt.date.today()
        assert len(data.commits_between(today - dt.timedelta(days=1), today)) == 2
        old = today - dt.timedelta(days=400)
        assert data.commits_between(old, old + dt.timedelta(days=1)) == []

    def test_a_directory_that_is_not_a_repository_is_reported(self, tmp_path: Path) -> None:
        outside = tmp_path / "plain"
        outside.mkdir()
        data = load_git(outside)
        assert not data.available
        assert len(data.issues) == 1
        assert data.issues[0].recoverable
        assert "not a git repository" in data.issues[0].message

    def test_max_commits_caps_the_traversal(self, repo: Path) -> None:
        assert len(load_git(repo, max_commits=1).commits) == 1


class TestCommitInfo:
    def test_a_merge_commit_yields_its_pull_request_and_branch(self) -> None:
        commit = CommitInfo(
            sha="a" * 40,
            author="A",
            authored_on=dt.date(2026, 9, 1),
            subject="Merge pull request #1184 from org/DA-5411-add-store-fact",
        )
        assert commit.pull_request == "1184"
        assert commit.merge_branch == "org/DA-5411-add-store-fact"
        assert commit.tickets(r"[A-Z]+-[0-9]+") == ["DA-5411"]

    def test_a_squash_merge_yields_its_pull_request(self) -> None:
        commit = CommitInfo(
            sha="b" * 40,
            author="A",
            authored_on=dt.date(2026, 9, 1),
            subject="Add the store fact (#533)",
        )
        assert commit.pull_request == "533"
        assert commit.merge_branch is None

    def test_a_plain_commit_has_no_pull_request(self) -> None:
        commit = CommitInfo(
            sha="c" * 40, author="A", authored_on=dt.date(2026, 9, 1), subject="Fix a typo"
        )
        assert commit.pull_request is None

    def test_tickets_are_found_in_the_body_when_the_subject_has_none(self) -> None:
        """A squash merge loses the branch name, so the body is the only place
        a reference survives."""
        commit = CommitInfo(
            sha="d" * 40,
            author="A",
            authored_on=dt.date(2026, 9, 1),
            subject="Add the store fact (#533)",
            body="Refs: DA-5398\nCo-authored-by: Someone",
        )
        assert commit.tickets(r"[A-Z]+-[0-9]+") == ["DA-5398"]
        assert commit.trailers["refs"] == "DA-5398"

    def test_an_invalid_ticket_pattern_yields_nothing_rather_than_raising(self) -> None:
        commit = CommitInfo(
            sha="e" * 40, author="A", authored_on=dt.date(2026, 9, 1), subject="DA-1"
        )
        assert commit.tickets("[unclosed") == []

    def test_the_body_is_read_from_history(self, repo: Path) -> None:
        data = load_git(repo)
        first = data.commits[-1]
        assert first.trailers.get("refs") == "DA-1001"


class TestHelpers:
    def test_trailers_are_parsed(self) -> None:
        assert trailers("Body text\n\nRefs: DA-1\nReviewed-by: Someone") == {
            "refs": "DA-1",
            "reviewed-by": "Someone",
        }

    def test_no_trailers_is_an_empty_mapping(self) -> None:
        assert trailers("just a message") == {}

    def test_tickets_in_text(self) -> None:
        assert tickets_in("DA-1 and DA-2 and DA-1", r"[A-Z]+-[0-9]+") == ["DA-1", "DA-2"]

    def test_an_invalid_pattern_yields_nothing(self) -> None:
        assert tickets_in("DA-1", "[unclosed") == []
