"""One version everywhere, or the actions install something that does not exist.

The second half covers the deadlock that shipped: the pull-request check
required the tag, the release job required the check, and the tag was never
created. The check must not look at the remote, and creating the tag must work
on a commit whose version already matches main.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

from hunter import __version__
from hunter.emit.scaffold import DEFAULT_ACTION_REF, workflow_text

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_release  # noqa: E402


class TestVersionAgreement:
    def test_the_package_version_is_a_release(self) -> None:
        """The actions install from tag v<version>; a dev version has no tag."""
        assert ".dev" not in __version__
        assert "+" not in __version__

    def test_every_file_agrees_with_the_package(self) -> None:
        assert check_release.disagreements(__version__) == []

    def test_each_action_defaults_to_the_package_version(self) -> None:
        for relative in check_release.ACTION_FILES:
            loaded = yaml.safe_load((REPO / relative).read_text(encoding="utf-8"))
            assert loaded["inputs"]["hunter-version"]["default"] == __version__, relative

    def test_the_scaffolded_workflow_pins_the_same_tag(self) -> None:
        assert DEFAULT_ACTION_REF.endswith(f"@v{__version__}")
        loaded = yaml.safe_load(workflow_text())
        refs = [
            step["uses"]
            for job in loaded["jobs"].values()
            for step in job["steps"]
            if "uses" in step and step["uses"].startswith("sav-sus/Hunter")
        ]
        assert refs, "the workflow references no Hunter action"
        assert all(ref.endswith(f"@v{__version__}") for ref in refs), refs

    def test_the_check_script_notices_a_drifted_action(self, tmp_path: Path) -> None:
        text = (REPO / "action.yml").read_text(encoding="utf-8")
        drifted = text.replace(f'default: "{__version__}"', 'default: "9.9.9"', 1)
        assert check_release.action_default(drifted, tmp_path / "action.yml") == "9.9.9"


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return completed.stdout.strip()


def _repo_with_origin(tmp_path: Path) -> Path:
    """A working repository whose origin is a bare repository beside it."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", "-q", str(origin))
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "remote", "add", "origin", str(origin))
    (repo / "version.txt").write_text("0.1.0\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "release 0.1.0")
    _git(repo, "push", "-q", "-u", "origin", "main")
    return repo


class TestReleaseTagging:
    """The wiring that deadlocked, exercised against a real origin."""

    def test_the_check_job_never_requires_the_tag(self) -> None:
        """The pull-request check and the release job must not wait on each other."""
        loaded = yaml.safe_load((REPO / ".github" / "workflows" / "ci.yml").read_text())
        check_runs = [
            step.get("run", "")
            for step in loaded["jobs"]["check"]["steps"]
            if "check_release" in step.get("run", "")
        ]
        assert check_runs, "the check job does not run the release check"
        assert all("--tag" not in run and "--release" not in run for run in check_runs)
        release_runs = [
            step.get("run", "") for step in loaded["jobs"]["release"]["steps"] if step.get("run")
        ]
        assert any("--release" in run for run in release_runs)
        assert loaded["jobs"]["release"]["needs"] == "check"

    def test_a_push_whose_version_matches_main_still_gets_its_tag(self, tmp_path: Path) -> None:
        """The exact case that failed: version on main, no tag, nothing to compare."""
        repo = _repo_with_origin(tmp_path)
        assert not check_release.tag_exists("v0.1.0", repo)
        message = check_release.ensure_tag("v0.1.0", repo)
        assert message.startswith("Created tag v0.1.0")
        assert check_release.tag_exists("v0.1.0", repo)

    def test_a_second_run_leaves_the_tag_alone(self, tmp_path: Path) -> None:
        repo = _repo_with_origin(tmp_path)
        check_release.ensure_tag("v0.1.0", repo)
        released_at = _git(repo, "rev-parse", "v0.1.0")
        (repo / "notes.txt").write_text("a later commit, same version\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "later")
        _git(repo, "push", "-q", "origin", "main")
        assert check_release.ensure_tag("v0.1.0", repo).startswith("Tag v0.1.0 already exists")
        assert _git(repo, "rev-parse", "v0.1.0") == released_at

    def test_a_version_bump_creates_a_new_tag_and_keeps_the_old_one(self, tmp_path: Path) -> None:
        repo = _repo_with_origin(tmp_path)
        check_release.ensure_tag("v0.1.0", repo)
        first = _git(repo, "rev-parse", "v0.1.0")
        (repo / "version.txt").write_text("0.2.0\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "release 0.2.0")
        _git(repo, "push", "-q", "origin", "main")
        assert check_release.ensure_tag("v0.2.0", repo).startswith("Created tag v0.2.0")
        assert check_release.tag_exists("v0.2.0", repo)
        assert _git(repo, "rev-parse", "v0.1.0") == first
        assert _git(repo, "rev-parse", "v0.2.0") == _git(repo, "rev-parse", "HEAD")
