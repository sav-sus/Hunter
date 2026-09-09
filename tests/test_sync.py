"""The three sync checks, and the three actions that wrap them.

The property worth protecting here is that a sync check can never disagree with
the score, because both read the same findings. Several tests below exist only
to hold that: the rules a check claims must be real rules, and every rule in
the registry must belong to at most one check.

The other property is that a missing source reports skipped, never passed. A
green tick nobody earned is worse than no tick, and a test is the only thing
that stops that regressing.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from hunter import sync
from hunter.checks.base import REGISTRY, REQ_DBML, REQ_DROUGHTY, REQ_LOOKML, REQ_MANIFEST
from hunter.enums import Severity
from hunter.run import RunResult, run

REPO = Path(__file__).parent.parent
EXAMPLE = REPO / "examples" / "tiny-shop"
ACTIONS = REPO / "actions"
AS_OF = dt.date(2026, 9, 8)


@pytest.fixture(scope="module")
def result() -> RunResult:
    return run(EXAMPLE, as_of=AS_OF, read_git=False)


@pytest.fixture(scope="module")
def results(result: RunResult) -> list[sync.SyncResult]:
    return sync.evaluate_all(result)


class TestTheChecksAreCoherent:
    def test_there_are_three_in_reading_order(self) -> None:
        """Nearest the reports first: that is the drift a client notices."""
        assert [check.key for check in sync.SYNC_CHECKS] == ["lookml", "droughty", "modelling"]

    def test_every_prefix_matches_at_least_one_real_rule(self) -> None:
        """A prefix that matches nothing would report a silent empty pass."""
        ids = {rule.id for rule in REGISTRY.all()}
        for check in sync.SYNC_CHECKS:
            for prefix in check.prefixes:
                assert any(rule_id.startswith(prefix) for rule_id in ids), (
                    f"{check.key} claims {prefix!r}, which matches no rule"
                )

    def test_no_rule_belongs_to_two_checks(self) -> None:
        """Otherwise one drift would fail two builds and be counted twice."""
        owners: dict[str, list[str]] = {}
        for rule in REGISTRY.all():
            for check in sync.SYNC_CHECKS:
                if check.owns(rule.id):
                    owners.setdefault(rule.id, []).append(check.key)
        doubled = {rule: keys for rule, keys in owners.items() if len(keys) > 1}
        assert doubled == {}

    def test_every_check_requires_the_manifest(self) -> None:
        """Nothing can be compared without knowing what was built."""
        for check in sync.SYNC_CHECKS:
            assert REQ_MANIFEST in check.requires

    def test_each_check_names_a_dashboard_section(self) -> None:
        """The report and the CI check must group the same facts alike."""
        from hunter.emit.dashboard import checklist

        titles = {section.title for section in checklist(run(EXAMPLE, as_of=AS_OF, read_git=False))}
        for check in sync.SYNC_CHECKS:
            assert check.sections, f"{check.key} claims no section"
            for name in check.sections:
                assert name in titles, f"{check.key} claims section {name!r}, which does not exist"

    def test_every_required_source_has_a_readable_name(self) -> None:
        for check in sync.SYNC_CHECKS:
            for source in check.requires + check.sharpened_by:
                assert sync.source_name(source) != source, f"{source} has no plain-English name"


class TestAgainstTheExample:
    def test_all_three_run_on_the_example(self, results: list[sync.SyncResult]) -> None:
        """The example carries LookML, Droughty output and a design."""
        assert [item.ran for item in results] == [True, True, True]

    def test_each_one_found_the_drift_it_was_built_to_find(
        self, results: list[sync.SyncResult]
    ) -> None:
        by_key = {item.check.key: item for item in results}
        assert by_key["lookml"].verdict == "drifted"
        assert by_key["droughty"].verdict == "drifted"
        assert by_key["modelling"].verdict == "drifted"

    def test_the_counts_add_up(self, results: list[sync.SyncResult]) -> None:
        for item in results:
            assert item.passed + item.failed == item.checked
            assert 0 <= (item.share or 0) <= 100

    def test_findings_come_from_the_same_run_as_the_score(
        self, results: list[sync.SyncResult], result: RunResult
    ) -> None:
        """The whole design rests on this: no second opinion."""
        open_ids = {(item.rule, item.subject) for item in result.open_findings}
        for entry in results:
            for finding in entry.findings:
                assert (finding.rule, finding.subject) in open_ids

    def test_no_check_reports_a_coverage_rule_as_drift(
        self, results: list[sync.SyncResult]
    ) -> None:
        """ "Hunter could not resolve this name" is not a layer having moved."""
        for entry in results:
            for finding in entry.findings:
                assert not REGISTRY.get(finding.rule).about_coverage

    def test_statements_are_grouped_by_the_dashboard_sections(
        self, results: list[sync.SyncResult]
    ) -> None:
        by_key = {item.check.key: item for item in results}
        assert any("LookML view" in text for text, *_ in by_key["lookml"].statements)
        assert any("Droughty" in text for text, *_ in by_key["droughty"].statements)
        assert any("design" in text for text, *_ in by_key["modelling"].statements)


class TestASkippedCheckNeverPasses:
    """The most important behaviour in the module."""

    def test_a_missing_source_reports_skipped(self, result: RunResult) -> None:
        stripped = run(EXAMPLE, as_of=AS_OF, read_git=False)
        object.__setattr__(stripped, "available", frozenset({REQ_MANIFEST}))
        for check in sync.SYNC_CHECKS:
            item = sync.evaluate(stripped, check)
            assert item.ran is False
            assert item.verdict == "skipped"
            assert "Not checked" in item.headline

    def test_a_skipped_check_never_fails_a_build(self, result: RunResult) -> None:
        """Adding a design file must not become a breaking change."""
        stripped = run(EXAMPLE, as_of=AS_OF, read_git=False)
        object.__setattr__(stripped, "available", frozenset({REQ_MANIFEST}))
        for check in sync.SYNC_CHECKS:
            item = sync.evaluate(stripped, check)
            for threshold in ("never", "high", "any"):
                assert item.fails_build(threshold) is False

    def test_the_headline_names_what_was_missing(self, result: RunResult) -> None:
        stripped = run(EXAMPLE, as_of=AS_OF, read_git=False)
        object.__setattr__(stripped, "available", frozenset({REQ_MANIFEST, REQ_DBML}))
        item = sync.evaluate(stripped, sync.LOOKML_SYNC)
        assert "LookML files" in item.headline

    def test_modelling_says_when_it_is_narrower_than_it_could_be(self, result: RunResult) -> None:
        """A pass should still say what it could not see."""
        narrow = run(EXAMPLE, as_of=AS_OF, read_git=False)
        object.__setattr__(
            narrow, "available", frozenset({REQ_MANIFEST, REQ_DBML, REQ_LOOKML, REQ_DROUGHTY})
        )
        item = sync.evaluate(narrow, sync.MODELLING_SYNC)
        assert item.ran
        assert item.absent_but_useful, "no conceptual diagram, so it should say so"


class TestGates:
    def test_never_never_fails(self, results: list[sync.SyncResult]) -> None:
        assert [item.fails_build("never") for item in results] == [False, False, False]

    def test_any_fails_on_a_drifted_check(self, results: list[sync.SyncResult]) -> None:
        assert all(item.fails_build("any") for item in results)

    def test_high_fails_only_where_there_is_a_high_finding(
        self, results: list[sync.SyncResult]
    ) -> None:
        for item in results:
            expected = any(f.severity is Severity.HIGH for f in item.findings)
            assert item.fails_build("high") is expected

    def test_an_unknown_threshold_raises_rather_than_passing(
        self, results: list[sync.SyncResult]
    ) -> None:
        """A typo in a workflow must not silently mean "never"."""
        with pytest.raises(ValueError, match="never, high or any"):
            results[0].fails_build("HIGH")


class TestEmitters:
    def test_the_payload_carries_the_version_stamp(
        self, results: list[sync.SyncResult], result: RunResult
    ) -> None:
        payload = sync.as_payload(results, result)
        assert payload["meta"]["score_model_version"]  # type: ignore[index]
        assert len(payload["checks"]) == 3  # type: ignore[arg-type]

    def test_the_payload_is_json(self, results: list[sync.SyncResult], result: RunResult) -> None:
        text = json.dumps(sync.as_payload(results, result), default=str)
        assert json.loads(text)["checks"][0]["key"] == "lookml"

    def test_the_markdown_leads_with_a_table_of_all_three(
        self, results: list[sync.SyncResult]
    ) -> None:
        body = sync.as_markdown(results)
        head = body.split("###")[0]
        for check in sync.SYNC_CHECKS:
            assert check.title in head

    def test_the_markdown_says_skipped_is_not_a_pass(self, result: RunResult) -> None:
        stripped = run(EXAMPLE, as_of=AS_OF, read_git=False)
        object.__setattr__(stripped, "available", frozenset({REQ_MANIFEST}))
        body = sync.as_markdown([sync.evaluate(stripped, sync.LOOKML_SYNC)])
        assert "This is not a pass" in body

    def test_the_markdown_carries_the_attribution(self, results: list[sync.SyncResult]) -> None:
        assert "Rittman Analytics" in sync.as_markdown(results)

    def test_the_summary_carries_the_logo_when_configured(self, results) -> None:
        body = sync.as_markdown(results, logo_url="https://example.github.io/logo.png")
        assert body.startswith('<img src="https://example.github.io/logo.png"')
        assert "<img" not in sync.as_markdown(results)


class TestTheActions:
    """The YAML is tested because nothing else will run it until it is published."""

    def test_there_is_one_action_per_check(self) -> None:
        for check in sync.SYNC_CHECKS:
            assert (ACTIONS / f"{check.key}-sync" / "action.yml").exists()

    def test_each_one_is_valid_yaml_with_the_expected_shape(self) -> None:
        for check in sync.SYNC_CHECKS:
            doc = yaml.safe_load(
                (ACTIONS / f"{check.key}-sync" / "action.yml").read_text(encoding="utf-8")
            )
            assert doc["name"] == check.title
            assert doc["runs"]["using"] == "composite"
            assert set(doc["outputs"]) == {"verdict", "checked", "failed", "result"}
            assert doc["inputs"]["fail-on"]["default"] == "never"

    def test_the_three_take_the_same_inputs(self) -> None:
        """Different inputs per check would be a trap for whoever writes the
        workflow, since all three are usually added at once."""
        shapes = []
        for check in sync.SYNC_CHECKS:
            doc = yaml.safe_load(
                (ACTIONS / f"{check.key}-sync" / "action.yml").read_text(encoding="utf-8")
            )
            shapes.append(sorted(doc["inputs"]))
        assert shapes[0] == shapes[1] == shapes[2]

    def test_none_of_them_references_hunter_at_main(self) -> None:
        """A result must not change because somebody pushed a commit.

        Only the steps are inspected. Every one of these files also carries
        prose warning against `@main`, and a plain text search matches that,
        which is how the first version of this test failed on its own advice.
        """
        for path in sorted(ACTIONS.glob("*/action.yml")):
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            for step in doc["runs"]["steps"]:
                for field in ("uses", "run"):
                    assert "@main" not in step.get(field, ""), (
                        f"{path} step {step.get('name')!r} references a branch"
                    )

    def test_each_runs_the_command_for_its_own_check(self) -> None:
        for check in sync.SYNC_CHECKS:
            body = (ACTIONS / f"{check.key}-sync" / "action.yml").read_text(encoding="utf-8")
            assert f"hunter sync {check.key}" in body

    def test_the_gate_is_applied_after_the_summary_is_written(self) -> None:
        """Otherwise a failing build produces no explanation of why."""
        for check in sync.SYNC_CHECKS:
            doc = yaml.safe_load(
                (ACTIONS / f"{check.key}-sync" / "action.yml").read_text(encoding="utf-8")
            )
            names = [step.get("name", "") for step in doc["runs"]["steps"]]
            assert names.index("Write the run summary") < names.index("Apply the gate")


class TestTheCommand:
    def _hunter(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "hunter.cli", "sync", *args],
            capture_output=True,
            text=True,
            cwd=REPO,
        )

    def test_it_reports_all_three_by_default(self) -> None:
        done = self._hunter("--root", str(EXAMPLE))
        assert done.returncode == 0, done.stderr
        for check in sync.SYNC_CHECKS:
            assert check.title in done.stdout

    def test_one_check_can_be_named(self) -> None:
        done = self._hunter("droughty", "--root", str(EXAMPLE))
        assert done.returncode == 0, done.stderr
        assert "Droughty sync" in done.stdout
        assert "LookML sync" not in done.stdout

    def test_an_unknown_name_is_refused_with_the_options(self) -> None:
        done = self._hunter("looker", "--root", str(EXAMPLE))
        assert done.returncode == 2
        assert "lookml" in done.stderr

    def test_an_unknown_threshold_is_refused(self) -> None:
        done = self._hunter("--root", str(EXAMPLE), "--fail-on", "sometimes")
        assert done.returncode == 2
        assert "never, high or any" in done.stderr

    def test_it_fails_the_build_when_asked_to(self) -> None:
        done = self._hunter("lookml", "--root", str(EXAMPLE), "--fail-on", "any")
        assert done.returncode == 1
        assert "Failing" in done.stderr

    def test_it_never_fails_by_default(self) -> None:
        done = self._hunter("--root", str(EXAMPLE))
        assert done.returncode == 0

    def test_it_writes_json_and_markdown(self, tmp_path: Path) -> None:
        out = tmp_path / "sync.json"
        summary = tmp_path / "sync.md"
        done = self._hunter("--root", str(EXAMPLE), "--out", str(out), "--summary", str(summary))
        assert done.returncode == 0, done.stderr
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert [entry["key"] for entry in payload["checks"]] == ["lookml", "droughty", "modelling"]
        assert "Rittman Hunter" in summary.read_text(encoding="utf-8")


class TestSummaryTitle:
    """Each sync check posts its own comment; the heading must say which."""

    def test_two_checks_produce_two_different_headings(self, results) -> None:
        by_key = {item.check.key: item for item in results}
        lookml = sync.as_markdown([by_key["lookml"]])
        droughty = sync.as_markdown([by_key["droughty"]])
        assert lookml.splitlines()[0] != droughty.splitlines()[0]

    def test_the_heading_is_the_check_title_and_verdict(self, results) -> None:
        """Matches the CI job name exactly: "LookML sync", not "lookml sync"."""
        for item in results:
            heading = sync.as_markdown([item]).splitlines()[0]
            assert heading == f"## Rittman Hunter: {item.check.title}, {item.verdict}"
        titles = {item.check.title for item in results}
        assert titles == {"LookML sync", "Droughty sync", "Modelling sync"}

    def test_a_run_over_several_checks_falls_back_to_layer_sync(self, results) -> None:
        assert len(results) > 1
        assert sync.as_markdown(results).splitlines()[0] == "## Rittman Hunter: layer sync"

    def test_the_heading_is_never_hardcoded(self) -> None:
        """Fails if someone puts a literal title back into as_markdown."""
        import inspect

        source = inspect.getsource(sync.as_markdown)
        assert 'header("Rittman Hunter' not in source
        assert "summary_title(results)" in source
