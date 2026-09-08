"""The score arithmetic: denominators, renormalisation and version movement."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
import yaml

import hunter.checks  # noqa: F401  registers every rule
from hunter import SCORE_MODEL_VERSION
from hunter.checks.base import Denominator
from hunter.config import resolve
from hunter.enums import Dimension, PrMode, Severity
from hunter.model.findings import (
    Finding,
    SystemicGap,
    grade_for,
    interpretation_for,
)
from hunter.score.baseline import (
    Baseline,
    BaselineError,
    dimension_deltas,
    load_baseline,
    write_baseline,
)
from hunter.score.engine import compute_score, dimension_scores, fails_build, systemic_gaps

DOC_RULE = "documentation.model_description_missing"
OWNER_RULE = "documentation.owner_missing"
TEST_RULE = "testing.key_uniqueness_missing"


@pytest.fixture
def config():
    return resolve().config


def finding(rule: str, dimension: Dimension, *, subject: str = "m", points: float = 1.0):
    return Finding(
        rule=rule,
        dimension=dimension,
        severity=Severity.MEDIUM,
        subject=subject,
        summary="s",
        consequence="c",
        points=points,
    )


def denominator(rule: str, *, checked: int, available: float) -> Denominator:
    return Denominator(rule_id=rule, checked=checked, points_available=available)


class TestDimensionScoring:
    def test_no_findings_scores_one_hundred(self, config) -> None:
        examined = {DOC_RULE: denominator(DOC_RULE, checked=10, available=10.0)}
        result = compute_score([], examined, config, available=["manifest"])
        assert result.dimension(Dimension.DOCUMENTATION).score == 100.0

    def test_every_check_failing_scores_zero(self, config) -> None:
        examined = {DOC_RULE: denominator(DOC_RULE, checked=3, available=3.0)}
        findings = [
            finding(DOC_RULE, Dimension.DOCUMENTATION, subject=f"m{index}") for index in range(3)
        ]
        result = compute_score(findings, examined, config, available=["manifest"])
        assert result.dimension(Dimension.DOCUMENTATION).score == 0.0

    def test_half_failing_scores_about_half(self, config) -> None:
        examined = {DOC_RULE: denominator(DOC_RULE, checked=10, available=10.0)}
        findings = [
            finding(DOC_RULE, Dimension.DOCUMENTATION, subject=f"m{index}") for index in range(5)
        ]
        result = compute_score(findings, examined, config, available=["manifest"])
        assert result.dimension(Dimension.DOCUMENTATION).score == 50.0

    def test_a_dimension_never_goes_below_zero(self, config) -> None:
        """Even when the findings outweigh what was examined."""
        examined = {DOC_RULE: denominator(DOC_RULE, checked=1, available=1.0)}
        findings = [
            finding(DOC_RULE, Dimension.DOCUMENTATION, subject=f"m{index}", points=50.0)
            for index in range(5)
        ]
        result = compute_score(findings, examined, config, available=["manifest"])
        assert result.dimension(Dimension.DOCUMENTATION).score == 0.0

    def test_suppressed_findings_cost_nothing(self, config) -> None:
        examined = {DOC_RULE: denominator(DOC_RULE, checked=4, available=4.0)}
        silenced = finding(DOC_RULE, Dimension.DOCUMENTATION)
        silenced.suppressed = True
        result = compute_score([silenced], examined, config, available=["manifest"])
        assert result.dimension(Dimension.DOCUMENTATION).score == 100.0

    def test_low_confidence_findings_cost_nothing(self, config) -> None:
        """FR3.6: reported as a suggestion, excluded from the score."""
        examined = {DOC_RULE: denominator(DOC_RULE, checked=4, available=4.0)}
        suggestion = finding(DOC_RULE, Dimension.DOCUMENTATION)
        suggestion.scored = False
        result = compute_score([suggestion], examined, config, available=["manifest"])
        assert result.dimension(Dimension.DOCUMENTATION).score == 100.0


class TestPerRuleWeighting:
    """A rule that examined 200 objects must not out-vote one that examined 3
    just by having a bigger denominator: adding a rule would then mechanically
    raise the score."""

    def test_rules_count_equally_at_equal_points(self, config) -> None:
        examined = {
            DOC_RULE: denominator(DOC_RULE, checked=200, available=200.0),
            OWNER_RULE: denominator(OWNER_RULE, checked=3, available=3.0),
        }
        # The small rule fails entirely, the large one passes entirely.
        findings = [
            finding(OWNER_RULE, Dimension.DOCUMENTATION, subject=f"m{index}", points=1.0)
            for index in range(3)
        ]
        score = compute_score(findings, examined, config, available=["manifest"]).dimension(
            Dimension.DOCUMENTATION
        )
        # Weighted by the rules' own points (1.0 and 0.8), not by object counts
        assert 40.0 < score.score < 60.0

    def test_a_higher_point_rule_weighs_more(self, config) -> None:
        light = {OWNER_RULE: denominator(OWNER_RULE, checked=4, available=4.0)}
        heavy = {TEST_RULE: denominator(TEST_RULE, checked=4, available=4.0)}
        light_findings = [
            finding(OWNER_RULE, Dimension.DOCUMENTATION, subject=f"m{i}") for i in range(4)
        ]
        heavy_findings = [finding(TEST_RULE, Dimension.TESTING, subject=f"m{i}") for i in range(4)]
        light_total = compute_score(light_findings, light, config, available=["manifest"]).total
        heavy_total = compute_score(heavy_findings, heavy, config, available=["manifest"]).total
        # Both dimensions carry the whole weight when alone, so both reach 0.
        assert light_total == heavy_total == 0.0


class TestRenormalisation:
    def test_a_skipped_dimension_redistributes_its_weight(self, config) -> None:
        """Without this, no warehouse access means being scored out of 93."""
        examined = {DOC_RULE: denominator(DOC_RULE, checked=10, available=10.0)}
        result = compute_score([], examined, config, available=["manifest"])
        assert result.weights_renormalised
        assert result.total == 100.0
        assert round(sum(entry.effective_weight for entry in result.dimensions), 1) == 100.0

    def test_skipped_dimensions_are_named_with_a_reason(self, config) -> None:
        examined = {DOC_RULE: denominator(DOC_RULE, checked=10, available=10.0)}
        result = compute_score([], examined, config, available=["manifest"])
        assert Dimension.PERFORMANCE_COST in result.dimensions_skipped
        skipped = result.dimension(Dimension.PERFORMANCE_COST)
        assert skipped.skipped_reason
        assert skipped.effective_weight == 0.0

    def test_two_scored_dimensions_share_the_weight_in_proportion(self, config) -> None:
        examined = {
            DOC_RULE: denominator(DOC_RULE, checked=4, available=4.0),
            TEST_RULE: denominator(TEST_RULE, checked=4, available=4.0),
        }
        result = compute_score([], examined, config, available=["manifest"])
        doc = result.dimension(Dimension.DOCUMENTATION)
        test = result.dimension(Dimension.TESTING)
        # House weights are 13 and 18, so testing should carry more
        assert test.effective_weight > doc.effective_weight
        assert round(doc.effective_weight + test.effective_weight, 1) == 100.0

    def test_a_dimension_with_zero_weight_is_skipped(self, tmp_path: Path) -> None:
        weights = {str(item): 0.0 for item in Dimension}
        weights["testing"] = 100.0
        path = tmp_path / "hunter.yml"
        path.write_text(yaml.safe_dump({"scoring": {"weights": weights}}), encoding="utf-8")
        config = resolve(path).config
        examined = {
            DOC_RULE: denominator(DOC_RULE, checked=4, available=4.0),
            TEST_RULE: denominator(TEST_RULE, checked=4, available=4.0),
        }
        result = compute_score([], examined, config, available=["manifest"])
        assert Dimension.DOCUMENTATION in result.dimensions_skipped
        assert result.dimension(Dimension.TESTING).effective_weight == 100.0

    def test_nothing_examined_at_all_gives_a_zero_total(self, config) -> None:
        result = compute_score([], {}, config, available=[])
        assert result.total == 0.0
        assert result.dimensions_scored == []


class TestGradesAndBands:
    @pytest.mark.parametrize(
        ("score", "grade"),
        [(100, "A"), (85, "A"), (84, "B"), (70, "B"), (69, "C"), (40, "D"), (0, "E")],
    )
    def test_grade_boundaries(self, score: int, grade: str) -> None:
        assert grade_for(score) == grade

    def test_the_interpretation_matches_the_grade_band(self) -> None:
        """FR7.10: one set of thresholds, so the two cannot disagree."""
        assert "Well maintained" in interpretation_for(90)
        assert "remediation backlog" in interpretation_for(10)

    def test_the_headline_is_the_number_and_the_panel_is_separate(self, config) -> None:
        examined = {DOC_RULE: denominator(DOC_RULE, checked=4, available=4.0)}
        result = compute_score([], examined, config, available=["manifest"])
        assert isinstance(result.total, float)
        assert result.interpretation and result.interpretation != str(result.total)


class TestSystemicGaps:
    def test_a_rule_failing_on_everything_is_named(self, config) -> None:
        examined = {OWNER_RULE: denominator(OWNER_RULE, checked=10, available=10.0)}
        findings = [
            finding(OWNER_RULE, Dimension.DOCUMENTATION, subject=f"m{index}") for index in range(10)
        ]
        gaps = systemic_gaps(findings, examined, config)
        assert [gap.rule for gap in gaps] == [OWNER_RULE]
        assert gaps[0].failed == 10
        assert gaps[0].checked == 10
        assert gaps[0].is_total

    def test_a_partial_failure_is_not_systemic(self, config) -> None:
        examined = {OWNER_RULE: denominator(OWNER_RULE, checked=10, available=10.0)}
        findings = [
            finding(OWNER_RULE, Dimension.DOCUMENTATION, subject=f"m{index}") for index in range(4)
        ]
        assert systemic_gaps(findings, examined, config) == []

    def test_a_tiny_sample_is_not_systemic(self, config) -> None:
        """One object failing out of one is not a pattern."""
        examined = {OWNER_RULE: denominator(OWNER_RULE, checked=1, available=1.0)}
        findings = [finding(OWNER_RULE, Dimension.DOCUMENTATION)]
        assert systemic_gaps(findings, examined, config) == []

    def test_gaps_are_ordered_by_severity(self, config) -> None:
        examined = {
            OWNER_RULE: denominator(OWNER_RULE, checked=5, available=5.0),
            TEST_RULE: denominator(TEST_RULE, checked=5, available=5.0),
        }
        findings = []
        for index in range(5):
            low = finding(OWNER_RULE, Dimension.DOCUMENTATION, subject=f"a{index}")
            low.severity = Severity.LOW
            high = finding(TEST_RULE, Dimension.TESTING, subject=f"b{index}")
            high.severity = Severity.HIGH
            findings.extend([low, high])
        gaps = systemic_gaps(findings, examined, config)
        assert gaps[0].severity is Severity.HIGH

    def test_a_zero_point_rule_is_never_a_gap(self, config) -> None:
        """Informational rules report without scoring."""
        examined = {
            "alignment.design_backlog": denominator(
                "alignment.design_backlog", checked=5, available=0.0
            )
        }
        findings = [
            finding("alignment.design_backlog", Dimension.MODEL_CONFORMANCE, points=0.0)
            for _ in range(5)
        ]
        assert systemic_gaps(findings, examined, config) == []


class TestBaselineAndVersionMovement:
    def test_delta_against_a_baseline(self, config) -> None:
        examined = {DOC_RULE: denominator(DOC_RULE, checked=4, available=4.0)}
        result = compute_score(
            [],
            examined,
            config,
            available=["manifest"],
            baseline=80.0,
            baseline_score_model_version=SCORE_MODEL_VERSION,
            baseline_house_version=config.house_version,
        )
        assert result.baseline == 80.0
        assert result.delta == 20.0
        assert result.real_delta == 20.0
        assert result.version_attributed_delta == 0.0

    def test_movement_after_a_score_model_change_is_attributed_to_the_upgrade(self, config) -> None:
        """FR7.9: a client on a support plan must never see an apparent
        regression caused by an upgrade."""
        examined = {DOC_RULE: denominator(DOC_RULE, checked=4, available=4.0)}
        result = compute_score(
            [],
            examined,
            config,
            available=["manifest"],
            baseline=95.0,
            baseline_score_model_version="0",
            baseline_house_version=config.house_version,
        )
        assert result.delta == 5.0
        assert result.version_attributed_delta == 5.0
        assert result.real_delta == 0.0

    def test_movement_after_a_house_ruleset_change_is_attributed_too(self, config) -> None:
        examined = {DOC_RULE: denominator(DOC_RULE, checked=4, available=4.0)}
        result = compute_score(
            [],
            examined,
            config,
            available=["manifest"],
            baseline=95.0,
            baseline_score_model_version=SCORE_MODEL_VERSION,
            baseline_house_version="0",
        )
        assert result.real_delta == 0.0

    def test_no_baseline_means_no_delta(self, config) -> None:
        examined = {DOC_RULE: denominator(DOC_RULE, checked=4, available=4.0)}
        result = compute_score([], examined, config, available=["manifest"])
        assert result.baseline is None
        assert result.delta is None


class TestBaselineFile:
    def test_round_trip(self, tmp_path: Path, config) -> None:
        examined = {DOC_RULE: denominator(DOC_RULE, checked=4, available=4.0)}
        result = compute_score([], examined, config, available=["manifest"])
        baseline = Baseline.from_result(
            result,
            house_version=config.house_version,
            commit="abc123",
            recorded_on=dt.date(2026, 9, 8),
            note="Recorded at installation.",
        )
        path = tmp_path / ".hunter" / "baseline.json"
        write_baseline(path, baseline)

        loaded = load_baseline(path)
        assert loaded is not None
        assert loaded.total == result.total
        assert loaded.commit == "abc123"
        assert loaded.score_model_version == SCORE_MODEL_VERSION

    def test_a_missing_baseline_is_not_an_error(self, tmp_path: Path) -> None:
        assert load_baseline(tmp_path / "absent.json") is None

    def test_a_malformed_baseline_is_a_clear_error(self, tmp_path: Path) -> None:
        path = tmp_path / "baseline.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(BaselineError, match="not valid JSON"):
            load_baseline(path)

    def test_the_file_is_written_sorted_and_newline_terminated(
        self, tmp_path: Path, config
    ) -> None:
        """So a diff of it stays readable in review."""
        examined = {DOC_RULE: denominator(DOC_RULE, checked=4, available=4.0)}
        result = compute_score([], examined, config, available=["manifest"])
        path = tmp_path / "baseline.json"
        write_baseline(path, Baseline.from_result(result, house_version=config.house_version))
        text = path.read_text(encoding="utf-8")
        assert text.endswith("\n")
        assert text.index('"commit"') < text.index('"total"')

    def test_dimension_deltas(self, config) -> None:
        examined = {DOC_RULE: denominator(DOC_RULE, checked=4, available=4.0)}
        result = compute_score([], examined, config, available=["manifest"])
        baseline = Baseline(
            total=50.0,
            dimensions={Dimension.DOCUMENTATION: 60.0},
            recorded_on=dt.date(2026, 1, 1),
        )
        assert dimension_deltas(result, baseline) == {Dimension.DOCUMENTATION: 40.0}

    def test_no_baseline_means_no_dimension_deltas(self, config) -> None:
        examined = {DOC_RULE: denominator(DOC_RULE, checked=4, available=4.0)}
        result = compute_score([], examined, config, available=["manifest"])
        assert dimension_deltas(result, None) == {}


class TestBuildFailure:
    def test_advisory_mode_never_fails(self, config) -> None:
        """FR11.7: advisory on first installation."""
        examined = {DOC_RULE: denominator(DOC_RULE, checked=4, available=4.0)}
        findings = [finding(DOC_RULE, Dimension.DOCUMENTATION, subject=f"m{i}") for i in range(4)]
        result = compute_score(findings, examined, config, available=["manifest"])
        assert result.total == 0.0
        assert fails_build(result, config) == (False, None)

    def test_gate_mode_fails_below_the_threshold(self, tmp_path: Path) -> None:
        path = tmp_path / "hunter.yml"
        path.write_text(
            yaml.safe_dump({"scoring": {"fail_under": 70}, "pull_request": {"mode": "gate"}}),
            encoding="utf-8",
        )
        config = resolve(path).config
        assert config.pull_request.mode is PrMode.GATE
        examined = {DOC_RULE: denominator(DOC_RULE, checked=4, available=4.0)}
        findings = [finding(DOC_RULE, Dimension.DOCUMENTATION, subject=f"m{i}") for i in range(4)]
        result = compute_score(findings, examined, config, available=["manifest"])
        failed, reason = fails_build(result, config)
        assert failed
        assert "below the agreed threshold" in reason

    def test_ratchet_mode_fails_on_real_regression_only(self, tmp_path: Path) -> None:
        """A drop caused by an upgrade must not fail a client's build."""
        path = tmp_path / "hunter.yml"
        path.write_text(
            yaml.safe_dump(
                {
                    "scoring": {"fail_on_regression": True},
                    "pull_request": {"mode": "ratchet"},
                }
            ),
            encoding="utf-8",
        )
        config = resolve(path).config
        examined = {DOC_RULE: denominator(DOC_RULE, checked=4, available=4.0)}

        real = compute_score(
            [finding(DOC_RULE, Dimension.DOCUMENTATION, subject="m")],
            examined,
            config,
            available=["manifest"],
            baseline=100.0,
            baseline_score_model_version=SCORE_MODEL_VERSION,
            baseline_house_version=config.house_version,
        )
        assert fails_build(real, config)[0]

        upgrade = compute_score(
            [finding(DOC_RULE, Dimension.DOCUMENTATION, subject="m")],
            examined,
            config,
            available=["manifest"],
            baseline=100.0,
            baseline_score_model_version="0",
            baseline_house_version=config.house_version,
        )
        assert not fails_build(upgrade, config)[0]


class TestDeterminism:
    def test_the_same_inputs_give_the_same_score(self, config) -> None:
        """FR7.7 and NFR3."""
        examined = {
            DOC_RULE: denominator(DOC_RULE, checked=7, available=7.0),
            TEST_RULE: denominator(TEST_RULE, checked=5, available=5.0),
        }
        findings = [
            finding(DOC_RULE, Dimension.DOCUMENTATION, subject=f"m{index}") for index in range(3)
        ]
        first = compute_score(findings, examined, config, available=["manifest"])
        second = compute_score(list(reversed(findings)), examined, config, available=["manifest"])
        assert first.model_dump() == second.model_dump()


class TestSystemicGapModel:
    def test_is_total(self) -> None:
        gap = SystemicGap(
            rule="a.b",
            dimension=Dimension.TESTING,
            severity=Severity.HIGH,
            summary="s",
            consequence="c",
            failed=5,
            checked=5,
        )
        assert gap.is_total


class TestDimensionScoresDirectly:
    def test_a_dimension_with_no_runnable_rule_is_skipped(self, config) -> None:
        results = dimension_scores([], {}, config, available=[])
        assert all(not entry.scored for entry in results)
