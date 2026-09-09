"""One version everywhere, or the actions install something that does not exist."""

from __future__ import annotations

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
        for path in check_release.ACTION_FILES:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            assert loaded["inputs"]["hunter-version"]["default"] == __version__, path

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
