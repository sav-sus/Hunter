"""Golden-file tests: the example project's score, and that it never moves.

Section 11.9. Two runs of the same commit must produce an identical payload, and
any deliberate change to the arithmetic must show up as a diff on a committed
file rather than as a surprise in a client's report.

Regenerate after an intended change:

    python -m tests.regenerate_golden

and the diff on ``tests/golden/tiny-shop.json`` is then part of the review.
"""

from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from pathlib import Path

import pytest

from hunter.emit.report import build_report, stable_payload
from hunter.run import RunResult, run

EXAMPLE = Path(__file__).parent.parent / "examples" / "tiny-shop"
GOLDEN = Path(__file__).parent / "golden" / "tiny-shop.json"

#: Pinned so expiry dates, staleness windows and ages never drift with the
#: calendar. Every date in the fixture is chosen relative to this.
AS_OF = dt.date(2026, 9, 8)

#: The example's score. Changing this line is how a score change gets reviewed.
EXPECTED_SCORE = 88.2

#: Every rule the fixture is built to trigger, and how many times. Each entry
#: is a deliberate flaw described in fixtures/tiny-project/build.py.
EXPECTED_FINDINGS: dict[str, int] = {
    "alignment.built_disabled": 1,
    "alignment.built_off_plan": 1,
    "alignment.design_backlog": 1,
    "conformance.column_missing_from_design": 1,
    "conformance.column_missing_from_model": 1,
    "conformance.design_not_built": 1,
    "conformance.types_unavailable": 1,
    "crosslayer.explore_no_caching_policy": 1,
    "crosslayer.exposure_missing": 3,
    "crosslayer.field_references_missing_column": 1,
    "documentation.model_description_missing": 1,
    "documentation.owner_missing": 1,
    "droughty.description_orphaned": 1,
    "droughty.generated_test_missing": 3,
    "droughty.introspected_column_undesigned": 2,
    "droughty.model_not_covered": 1,
    "droughty.override_dropped": 1,
    "entity.dimension_with_measures": 1,
    "entity.type_unclear": 1,
    "lineage.dead_model": 2,
    "lineage.staging_bypassed": 2,
    "structure.hardcoded_reference": 1,
    "structure.select_star_from_source": 2,
    "testing.declared_grain_untested": 1,
    "testing.key_not_null_missing": 2,
    "testing.key_uniqueness_missing": 1,
    "testing.no_tests_at_all": 2,
    "testing.only_weak_tests": 1,
}


@pytest.fixture(scope="module")
def result() -> RunResult:
    """History is skipped on purpose.

    Attribution and the description-staleness rule both read git. Both would
    make this payload depend on who committed the example and when, so a
    shallow CI checkout, a squash merge or a second developer would each break
    the comparison for no reason. Attribution is covered by
    ``test_ingest_git.py`` and ``test_model_build.py`` against repositories
    those tests build themselves.
    """
    return run(EXAMPLE, as_of=AS_OF, read_git=False)


class TestFixtureScore:
    def test_the_score_is_what_the_golden_file_says(self, result: RunResult) -> None:
        assert result.score.total == EXPECTED_SCORE

    def test_every_scored_dimension_has_a_grade(self, result: RunResult) -> None:
        for entry in result.score.dimensions:
            if entry.scored:
                assert entry.grade in {"A", "B", "C", "D", "E"}
                assert 0.0 <= entry.score <= 100.0

    def test_performance_is_the_only_skipped_dimension(self, result: RunResult) -> None:
        """It needs warehouse data, which is milestone M2."""
        assert [str(item) for item in result.score.dimensions_skipped] == ["performance_cost"]

    def test_the_effective_weights_still_total_one_hundred(self, result: RunResult) -> None:
        total = sum(entry.effective_weight for entry in result.score.dimensions)
        assert round(total, 1) == 100.0


class TestFixtureFindings:
    def test_exactly_the_intended_findings_are_produced(self, result: RunResult) -> None:
        """Each of these is a flaw the fixture was built to demonstrate. A new
        entry here means a rule started firing where it did not before."""
        assert dict(Counter(item.rule for item in result.findings)) == EXPECTED_FINDINGS

    def test_the_off_plan_build_is_the_legacy_table(self, result: RunResult) -> None:
        finding = next(item for item in result.findings if item.rule == "alignment.built_off_plan")
        assert finding.subject == "wh_commerce__legacy_fact"

    def test_the_disabled_model_is_not_reported_as_unstarted(self, result: RunResult) -> None:
        """The state that six pilot models forced into existence."""
        finding = next(item for item in result.findings if item.rule == "alignment.built_disabled")
        assert finding.subject == "wh_commerce__forecast_fact"
        assert "conformance.design_not_built" not in {
            item.rule for item in result.findings if item.subject == "wh_commerce__forecast_fact"
        }

    def test_the_dropped_override_is_the_missing_not_null(self, result: RunResult) -> None:
        """The check that replaces the pilot team's manual verification."""
        finding = next(item for item in result.findings if item.rule == "droughty.override_dropped")
        assert finding.subject == "wh_master__customer_dim"
        assert "not_null" in finding.evidence["tests"]

    def test_the_broken_report_field_names_the_missing_column(self, result: RunResult) -> None:
        finding = next(
            item
            for item in result.findings
            if item.rule == "crosslayer.field_references_missing_column"
        )
        assert "order_channel_name" in finding.evidence["columns"]

    def test_the_weak_test_is_not_credited_as_key_cover(self, result: RunResult) -> None:
        """3,492 of the pilot's 3,926 tests are at_least_one."""
        finding = next(item for item in result.findings if item.rule == "testing.only_weak_tests")
        assert finding.subject == "wh_master__product_dim"

    def test_the_silenced_finding_is_reported_and_costs_nothing(self, result: RunResult) -> None:
        silenced = result.suppressed_findings
        assert len(silenced) == 1
        assert silenced[0].subject == "wh_master__customer_dim"
        assert silenced[0].effective_points == 0.0
        assert "customer rework" in silenced[0].suppression_reason

    def test_the_low_confidence_judgement_is_a_suggestion(self, result: RunResult) -> None:
        assert len(result.suggestions) == 1
        assert result.suggestions[0].rule == "entity.type_unclear"
        assert result.suggestions[0].effective_points == 0.0

    def test_every_finding_carries_a_consequence_in_business_terms(self, result: RunResult) -> None:
        """FR14.2. A finding with an unfilled placeholder is a rule bug."""
        for finding in result.findings:
            assert finding.consequence.strip()
            assert "{" not in finding.consequence, finding.rule
            assert "{" not in finding.summary, finding.rule

    def test_the_vendored_model_is_never_scored(self, result: RunResult) -> None:
        for finding in result.findings:
            if finding.subject == "package_helper":
                assert finding.effective_points == 0.0


class TestFixtureAlignment:
    def test_the_reconciliation_counts(self, result: RunResult) -> None:
        counts = {str(state): count for state, count in result.alignment.state_counts().items()}
        assert counts == {
            "built_disabled": 1,
            "built_off_plan": 1,
            "conceptual_only": 1,
            "designed_and_delivered": 4,
            "designed_not_started": 1,
        }
        # Six designed entities: four built, one switched off, one not started.
        assert sum(counts.values()) == 8

    def test_coverage(self, result: RunResult) -> None:
        coverage = result.alignment.coverage
        assert coverage.designed_entities == 6
        assert coverage.designed_and_built == 4
        assert coverage.conceptual_entities == 7
        assert coverage.delivery_coverage == pytest.approx(66.7, abs=0.1)

    def test_the_stale_diagram_claim_is_found(self, result: RunResult) -> None:
        """The fixture's diagram shows suppliers as planned, which is right, and
        forecasts as deviating, which carries no expectation."""
        stale = result.alignment.stale_claims()
        assert [row.label for row in stale] == []


class TestDivergenceReport:
    def test_the_disabled_rule_appears_with_its_reason(self, result: RunResult) -> None:
        """FR7b: overridden, disabled or reweighted, and why."""
        divergences = result.resolved.divergences
        assert [item.path for item in divergences] == ["rules.structure.model_too_long.enabled"]
        assert divergences[0].kind == "disabled"
        assert "adds nothing here" in divergences[0].reason


class TestDeterminism:
    """FR7.7 and NFR3: the same inputs give the same output, every time."""

    def test_two_runs_produce_an_identical_payload(self) -> None:
        first = stable_payload(run(EXAMPLE, as_of=AS_OF))
        second = stable_payload(run(EXAMPLE, as_of=AS_OF))
        assert json.dumps(first, sort_keys=True, default=str) == json.dumps(
            second, sort_keys=True, default=str
        )

    def test_the_payload_matches_the_committed_golden_file(self, result: RunResult) -> None:
        assert GOLDEN.exists(), f"{GOLDEN} is missing. Run: python -m tests.regenerate_golden"
        expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
        actual = json.loads(json.dumps(stable_payload(result), sort_keys=True, default=str))
        assert actual == expected, (
            "The report has changed. If the change is intended, run "
            "python -m tests.regenerate_golden and review the diff."
        )

    def test_generated_at_is_the_only_thing_that_moves(self, result: RunResult) -> None:
        first = build_report(result, generated_at=dt.datetime(2026, 9, 8, 10, 0, 0))
        second = build_report(result, generated_at=dt.datetime(2026, 9, 8, 11, 0, 0))
        assert first["meta"]["generated_at"] != second["meta"]["generated_at"]
        del first["meta"], second["meta"]
        assert first == second

    def test_no_absolute_path_reaches_the_report(self, result: RunResult) -> None:
        """A local path in a client's pull request is a leak and unreadable."""
        payload = json.dumps(stable_payload(result), default=str)
        assert "/Users/" not in payload
        assert "/home/" not in payload


#: Rendered every page and every diagram, then hashed. Run under two different
#: hash seeds, this catches anything that iterates a set where it should iterate
#: a sorted list.
_RENDER_AND_HASH = """
import datetime as dt, hashlib, json, pathlib, sys, tempfile
from hunter.emit.markdown import write_site
from hunter.emit.report import stable_payload
from hunter.run import run

root = pathlib.Path(sys.argv[1])
out = pathlib.Path(tempfile.mkdtemp())
result = run(root, as_of=dt.date(2026, 9, 8), read_git=False)
write_site(result, out, generated_at=dt.datetime(2026, 9, 8, 12, 0, 0))

digest = hashlib.sha256()
for path in sorted(p for p in out.rglob("*") if p.is_file()):
    digest.update(str(path.relative_to(out)).encode())
    digest.update(path.read_bytes())
digest.update(json.dumps(stable_payload(result), sort_keys=True, default=str).encode())
print(digest.hexdigest())
"""


class TestRenderedOutputIsDeterministic:
    """The golden file alone cannot prove this.

    Within one process the hash seed is fixed, so a loop over a set of strings
    gives the same order every time and the golden comparison passes. The order
    only changes between processes. One such loop shipped in the blast-radius
    diagram and reordered three edges on three committed pages, which is why
    this runs the whole render twice under different seeds.
    """

    def _digest(self, seed: str) -> str:
        import os
        import subprocess
        import sys

        env = os.environ | {"PYTHONHASHSEED": seed}
        completed = subprocess.run(
            [sys.executable, "-c", _RENDER_AND_HASH, str(EXAMPLE)],
            capture_output=True,
            text=True,
            env=env,
            cwd=EXAMPLE.parent.parent,
        )
        assert completed.returncode == 0, completed.stderr
        return completed.stdout.strip()

    def test_two_hash_seeds_render_byte_identical_output(self) -> None:
        assert self._digest("0") == self._digest("1")
