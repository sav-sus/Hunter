"""The check framework: overrides, silences, denominators and weighting."""

from __future__ import annotations

import datetime as dt

import pytest
import yaml

import hunter.checks  # noqa: F401  registers every rule
from hunter.checks import documentation
from hunter.checks.base import REGISTRY, Findings, plural
from hunter.config import resolve
from hunter.config.register import Register
from hunter.enums import Dimension, Severity
from tests.conftest import build_context, column, model, score_of


class TestRuleRegistry:
    def test_every_rule_has_a_consequence_and_a_plain_heading(self) -> None:
        """F14.2 and F14.5: a rule with no consequence line is not shippable."""
        for rule in REGISTRY.all():
            assert rule.consequence.strip(), rule.id
            assert rule.plain_heading.strip(), rule.id
            assert rule.title.strip(), rule.id

    def test_no_consequence_line_talks_about_severity(self) -> None:
        """ "high severity: relationships test missing" is what FR14.2 forbids."""
        for rule in REGISTRY.all():
            lowered = rule.consequence.lower()
            assert "severity" not in lowered, rule.id
            assert not lowered.startswith(("high", "medium", "low")), rule.id

    def test_rule_ids_are_namespaced_by_their_module(self) -> None:
        for rule in REGISTRY.all():
            assert "." in rule.id, rule.id

    def test_every_dimension_has_at_least_one_rule(self) -> None:
        covered = {rule.dimension for rule in REGISTRY.all()}
        missing = set(Dimension) - covered
        # Performance and cost needs warehouse data, which is milestone M2.
        assert missing == {Dimension.PERFORMANCE_COST}

    def test_a_duplicate_rule_id_is_refused(self) -> None:
        from hunter.checks.base import Rule

        with pytest.raises(ValueError, match="declared twice"):
            REGISTRY.add(
                Rule(
                    id="documentation.model_description_missing",
                    dimension=Dimension.DOCUMENTATION,
                    severity=Severity.LOW,
                    points=1.0,
                    title="x",
                    consequence="y",
                    plain_heading="z",
                )
            )

    def test_an_unknown_rule_id_is_a_clear_error(self) -> None:
        with pytest.raises(KeyError, match="no such rule"):
            REGISTRY.get("nonesuch.rule")


class TestConsequenceTemplates:
    def test_a_template_is_filled_from_the_evidence(self, config) -> None:
        context = build_context(config, models=[model("wh_a__thing_fact")])
        findings = documentation.run(context)
        finding = next(
            item for item in findings if item.rule == "documentation.model_description_missing"
        )
        assert "wh_a__thing_fact" in finding.summary
        assert "{" not in finding.consequence

    def test_an_unfilled_placeholder_stays_visible_rather_than_raising(self) -> None:
        """It should show up in review as {whatever}, not crash a client run."""
        rule = REGISTRY.get("documentation.model_description_missing")
        text = rule.format_consequence({"subject": "x", "label": "X"})
        assert "{consumers}" in text


class TestRuleOverrides:
    def test_a_disabled_rule_produces_nothing(self, config, tmp_path) -> None:
        path = tmp_path / "hunter.yml"
        path.write_text(
            yaml.safe_dump(
                {
                    "rules": {
                        "documentation.model_description_missing": {
                            "enabled": False,
                            "reason": "descriptions are held in Confluence instead",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        context = build_context(resolve(path).config, models=[model("wh_a__thing_fact")])
        findings = documentation.run(context)
        assert "documentation.model_description_missing" not in {item.rule for item in findings}

    def test_a_disabled_rule_is_left_out_of_the_denominator(self, config, tmp_path) -> None:
        """Otherwise switching a rule off would lower the score."""
        path = tmp_path / "hunter.yml"
        path.write_text(
            yaml.safe_dump(
                {
                    "rules": {
                        "documentation.owner_missing": {
                            "enabled": False,
                            "reason": "ownership is tracked outside the repository",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        context = build_context(resolve(path).config, models=[model("wh_a__thing_fact")])
        documentation.run(context)
        assert "documentation.owner_missing" not in context.examined

    def test_reweighting_changes_the_points(self, config, tmp_path) -> None:
        path = tmp_path / "hunter.yml"
        path.write_text(
            yaml.safe_dump({"rules": {"documentation.model_description_missing": {"points": 9.0}}}),
            encoding="utf-8",
        )
        context = build_context(resolve(path).config, models=[model("wh_a__thing_fact")])
        finding = next(
            item
            for item in documentation.run(context)
            if item.rule == "documentation.model_description_missing"
        )
        assert finding.points >= 9.0

    def test_severity_can_be_overridden(self, config, tmp_path) -> None:
        path = tmp_path / "hunter.yml"
        path.write_text(
            yaml.safe_dump(
                {"rules": {"documentation.model_description_missing": {"severity": "high"}}}
            ),
            encoding="utf-8",
        )
        context = build_context(resolve(path).config, models=[model("wh_a__thing_fact")])
        finding = next(
            item
            for item in documentation.run(context)
            if item.rule == "documentation.model_description_missing"
        )
        assert finding.severity is Severity.HIGH


class TestSilencing:
    """A silenced finding still appears, with its reason. It is visible, not gone."""

    def test_a_live_ignore_suppresses_scoring_but_not_reporting(self, config) -> None:
        register = Register.model_validate(
            {
                "ignores": [
                    {
                        "rule": "documentation.model_description_missing",
                        "models": ["wh_a__*"],
                        "reason": "documentation sweep scheduled for next sprint",
                        "expires": "2026-12-31",
                    }
                ]
            }
        )
        context = build_context(config, models=[model("wh_a__thing_fact")], register=register)
        finding = next(
            item
            for item in documentation.run(context)
            if item.rule == "documentation.model_description_missing"
        )
        assert finding.suppressed
        assert finding.effective_points == 0.0
        assert "next sprint" in finding.suppression_reason
        assert finding.suppression_expires == dt.date(2026, 12, 31)

    def test_an_expired_ignore_scores_again(self, config) -> None:
        """FR8.5: the finding comes back on expiry."""
        register = Register.model_validate(
            {
                "ignores": [
                    {
                        "rule": "documentation.model_description_missing",
                        "models": ["wh_a__*"],
                        "reason": "documentation sweep scheduled for last sprint",
                        "expires": "2026-06-30",
                    }
                ]
            }
        )
        context = build_context(config, models=[model("wh_a__thing_fact")], register=register)
        finding = next(
            item
            for item in documentation.run(context)
            if item.rule == "documentation.model_description_missing"
        )
        assert not finding.suppressed
        assert finding.effective_points > 0


class TestVendoredCode:
    def test_a_package_model_is_reported_but_never_scored(self, config) -> None:
        vendored = model("elementary_thing", package="elementary", vendored=True)
        context = build_context(config, models=[vendored])
        findings = documentation.run(context)
        for finding in findings:
            if finding.subject == "elementary_thing":
                assert not finding.scored
                assert finding.effective_points == 0.0

    def test_a_package_model_is_left_out_of_the_denominator(self, config) -> None:
        vendored = model("elementary_thing", package="elementary", vendored=True)
        context = build_context(config, models=[vendored])
        documentation.run(context)
        for entry in context.examined.values():
            assert entry.checked == 0 or entry.points_available == 0.0


class TestDenominators:
    def test_a_passing_check_still_counts_towards_the_denominator(self, config) -> None:
        """Without this the score has no denominator and reads as arbitrary."""
        good = model(
            "wh_a__thing_fact",
            description="One row per thing, owned by commerce.",
            owner="commerce",
            columns=[column("thing_pk", description="The key.")],
        )
        context = build_context(config, models=[good])
        findings = documentation.run(context)
        assert findings == []
        assert context.examined["documentation.model_description_missing"].checked == 1
        assert score_of(context, findings) == 100.0

    def test_a_failing_check_lowers_the_score_proportionately(self, config) -> None:
        context = build_context(config, models=[model("wh_a__thing_fact")])
        findings = documentation.run(context)
        assert 0.0 < score_of(context, findings) < 100.0


class TestPointsScaling:
    def test_a_partial_gap_costs_less_than_a_complete_one(self, config) -> None:
        mostly_documented = model(
            "wh_a__one_fact",
            description="A thing.",
            owner="team",
            columns=[
                column("a", description="The first thing."),
                column("b", description="The second thing."),
                column("c"),
            ],
        )
        undocumented = model(
            "wh_a__two_fact",
            description="A thing.",
            owner="team",
            columns=[column("a"), column("b"), column("c")],
        )
        context = build_context(config, models=[mostly_documented, undocumented])
        findings = [
            item
            for item in documentation.run(context)
            if item.rule == "documentation.column_description_missing"
        ]
        by_subject = {item.subject: item for item in findings}
        assert by_subject["wh_a__one_fact"].points < by_subject["wh_a__two_fact"].points


class TestExposureWeighting:
    def test_a_finding_on_a_heavily_used_model_costs_more(self, config) -> None:
        """FR7.4, and the reason exposure weighting exists."""
        used = model("wh_a__used_fact", owner="team")
        consumers = [
            model(f"wh_a__consumer_{index}_fact", deps=["wh_a__used_fact"], owner="team")
            for index in range(6)
        ]
        context = build_context(config, models=[used, *consumers])
        findings = [
            item
            for item in documentation.run(context)
            if item.rule == "documentation.model_description_missing"
        ]
        by_subject = {item.subject: item for itemine in [0] for item in findings}
        assert by_subject["wh_a__used_fact"].points > by_subject["wh_a__consumer_0_fact"].points


class TestHelpers:
    @pytest.mark.parametrize(
        ("count", "expected"),
        [(0, "0 columns"), (1, "1 column"), (2, "2 columns")],
    )
    def test_plural(self, count: int, expected: str) -> None:
        assert plural(count, "column") == expected

    def test_plural_with_an_irregular_form(self) -> None:
        assert plural(1, "business entity", "business entities") == "1 business entity"
        assert plural(3, "business entity", "business entities") == "3 business entities"

    def test_findings_collector_drops_none(self) -> None:
        findings = Findings()
        findings.add(None)
        assert findings == []

    def test_consumer_summary_agrees_in_number(self, config) -> None:
        one = model("wh_a__one_fact")
        two = model("wh_a__two_fact", deps=["wh_a__one_fact"])
        context = build_context(config, models=[one, two])
        assert context.consumer_summary("wh_a__one_fact").endswith("depends on it")
        assert "1 other model" in context.consumer_summary("wh_a__one_fact")
        assert context.consumer_summary("wh_a__two_fact") == ("nothing downstream depends on it")
