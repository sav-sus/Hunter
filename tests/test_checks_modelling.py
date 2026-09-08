"""Testing, entity, lineage, conformance, cross-layer, Droughty and alignment rules."""

from __future__ import annotations

import datetime as dt

import pytest

from conftest import build_context, column, dbt_test, designed, model, rules_fired
from hunter.checks import (
    alignment,
    conformance,
    crosslayer,
    droughty,
    entity,
    lineage,
    testing,
)
from hunter.checks.entity import article, looks_like_boolean, looks_like_measure
from hunter.config.register import Register
from hunter.ingest.droughty import DroughtyData
from hunter.ingest.lookml import LookmlData
from hunter.model.entities import (
    DesignedColumn,
    DesignedRef,
    DroughtyTestSpec,
    Exposure,
    LookmlField,
    LookmlView,
)


def keyed_model(name: str = "wh_a__thing_fact", **kwargs):
    columns = kwargs.pop("columns", None) or [
        column("thing_pk"),
        column("thing_amount"),
        column("thing_dt"),
    ]
    return model(name, columns=columns, **kwargs)


def key_tests(name: str = "wh_a__thing_fact") -> list:
    return [
        dbt_test(name, "unique", column="thing_pk"),
        dbt_test(name, "not_null", column="thing_pk"),
    ]


class TestTesting:
    def test_a_fully_tested_fact_passes(self, config) -> None:
        context = build_context(config, models=[keyed_model()], tests=key_tests())
        assert testing.run(context) == []

    def test_a_model_with_no_tests_is_reported(self, config) -> None:
        context = build_context(config, models=[keyed_model()])
        assert "testing.no_tests_at_all" in rules_fired(testing.run(context))

    def test_only_weak_tests_is_reported(self, config) -> None:
        """3,492 of the pilot's 3,926 tests are at_least_one. Counting tests
        would score it well while its keys go unverified."""
        context = build_context(
            config,
            models=[keyed_model()],
            tests=[dbt_test("wh_a__thing_fact", "at_least_one", column="thing_amount")],
        )
        fired = rules_fired(testing.run(context))
        assert "testing.only_weak_tests" in fired
        assert "testing.key_uniqueness_missing" in fired

    def test_a_missing_uniqueness_test_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[keyed_model()],
            tests=[dbt_test("wh_a__thing_fact", "not_null", column="thing_pk")],
        )
        assert "testing.key_uniqueness_missing" in rules_fired(testing.run(context))

    def test_a_warn_only_key_test_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[keyed_model()],
            tests=[
                dbt_test("wh_a__thing_fact", "unique", column="thing_pk", severity="warn"),
                dbt_test("wh_a__thing_fact", "not_null", column="thing_pk"),
            ],
        )
        assert "testing.key_test_warns_only" in rules_fired(testing.run(context))

    def test_an_untested_foreign_key_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[keyed_model(columns=[column("thing_pk"), column("other_fk")])],
            tests=key_tests(),
        )
        assert "testing.relationship_test_missing" in rules_fired(testing.run(context))

    def test_a_tested_foreign_key_passes(self, config) -> None:
        context = build_context(
            config,
            models=[keyed_model(columns=[column("thing_pk"), column("other_fk")])],
            tests=[
                *key_tests(),
                dbt_test("wh_a__thing_fact", "relationships", column="other_fk"),
            ],
        )
        assert "testing.relationship_test_missing" not in rules_fired(testing.run(context))

    def test_an_untested_declared_grain_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[keyed_model()],
            design=[designed("wh_a__thing_fact", grain="one row per thing per day")],
            tests=[dbt_test("wh_a__thing_fact", "not_null", column="thing_pk")],
        )
        assert "testing.declared_grain_untested" in rules_fired(testing.run(context))


class TestEntityHelpers:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("order_total_amount", True),
            ("store_visitor_count_actual", True),
            ("exchange_rate_value", True),
            ("exchange_rate_from_currency", False),
            ("employee_cost_centre_name", False),
            ("product_name", False),
            ("order_status", False),
        ],
    )
    def test_measure_detection(self, name: str, expected: bool) -> None:
        assert looks_like_measure(name) is expected

    def test_a_mid_name_boolean_marker_is_found(self) -> None:
        assert looks_like_boolean("exchange_rate_is_carried_forward", ["is_", "has_"], ["_flag"])

    def test_articles(self) -> None:
        assert article("aggregate") == "an"
        assert article("fact") == "a"


class TestEntity:
    def test_a_well_shaped_fact_passes(self, config) -> None:
        context = build_context(
            config,
            models=[
                keyed_model(
                    columns=[
                        column("thing_pk"),
                        column("store_fk"),
                        column("customer_fk"),
                        column("thing_amount"),
                        column("thing_dt"),
                    ]
                )
            ],
        )
        assert entity.run(context) == []

    def test_a_fact_with_no_measures_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[
                keyed_model(columns=[column("thing_pk"), column("thing_name"), column("thing_dt")])
            ],
        )
        assert "entity.fact_without_measures" in rules_fired(entity.run(context))

    def test_a_dimension_carrying_figures_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[
                model(
                    "wh_a__thing_dim",
                    columns=[
                        column("thing_pk"),
                        column("thing_name"),
                        column("thing_total_amount"),
                    ],
                )
            ],
        )
        assert "entity.dimension_with_measures" in rules_fired(entity.run(context))

    def test_a_missing_surrogate_key_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[keyed_model(columns=[column("thing_name"), column("thing_amount")])],
        )
        assert "entity.surrogate_key_missing" in rules_fired(entity.run(context))

    def test_a_low_confidence_judgement_is_reported_but_not_scored(self, config) -> None:
        """FR3.6, and the mitigation for losing trust on false positives."""
        context = build_context(
            config,
            models=[
                model(
                    "wh_a__thing_dim",
                    columns=[
                        column("thing_pk"),
                        column("a_fk"),
                        column("b_fk"),
                        column("thing_dt"),
                    ],
                )
            ],
        )
        findings = entity.run(context)
        unclear = [item for item in findings if item.rule == "entity.type_unclear"]
        for item in unclear:
            assert not item.scored
            assert item.effective_points == 0.0

    def test_the_evidence_says_types_were_unavailable(self, config) -> None:
        """Types live in catalog.json, not the manifest. Saying so matters."""
        context = build_context(
            config,
            models=[
                model(
                    "wh_a__thing_dim",
                    columns=[column("thing_pk"), column("a_fk"), column("b_fk")],
                )
            ],
        )
        findings = [
            item
            for item in entity.run(context)
            if item.rule in {"entity.type_unclear", "entity.declared_type_mismatch"}
        ]
        for item in findings:
            assert "column types were not available" in item.consequence


class TestLineage:
    def test_a_tidy_graph_passes(self, config) -> None:
        context = build_context(
            config,
            models=[
                model("stg_x__a", layer="staging", materialised="view"),
                model("int_x__b", layer="integration", deps=["stg_x__a"], materialised="view"),
                keyed_model(deps=["int_x__b"]),
            ],
            lookml=_lookml_for("wh_a__thing_fact"),
        )
        assert "lineage.dead_model" not in rules_fired(lineage.run(context))

    def test_a_dead_model_is_reported(self, config) -> None:
        context = build_context(config, models=[keyed_model()])
        assert "lineage.dead_model" in rules_fired(lineage.run(context))

    def test_a_rejoin_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[
                model("stg_x__a", layer="staging", materialised="view"),
                model("int_x__b", layer="integration", deps=["stg_x__a"], materialised="view"),
                keyed_model(deps=["int_x__b", "stg_x__a"]),
            ],
        )
        assert "lineage.model_rejoin" in rules_fired(lineage.run(context))

    def test_reading_two_stages_below_is_reported(self, config) -> None:
        """Warehouse reading staging directly, skipping integration."""
        context = build_context(
            config,
            models=[
                model("stg_x__a", layer="staging", materialised="view"),
                keyed_model(deps=["stg_x__a"]),
            ],
        )
        finding = next(
            item for item in lineage.run(context) if item.rule == "lineage.staging_bypassed"
        )
        assert "integration" in finding.summary

    def test_reading_one_stage_below_is_fine(self, config) -> None:
        context = build_context(
            config,
            models=[
                model("int_x__b", layer="integration", materialised="view"),
                keyed_model(deps=["int_x__b"]),
            ],
        )
        assert "lineage.staging_bypassed" not in rules_fired(lineage.run(context))

    def test_reading_a_seed_bypasses_nothing(self, config) -> None:
        """Seeds sit outside the pipeline, so reading one skips no stage. This
        rule previously reported "skips the seeds layer"."""
        context = build_context(
            config,
            models=[
                model("a_seed", layer="seeds", resource_type="seed"),
                keyed_model(deps=["a_seed"]),
            ],
        )
        assert "lineage.staging_bypassed" not in rules_fired(lineage.run(context))

    def test_a_temporary_model_read_by_a_report_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[model("int_x__b", layer="integration", materialised="view")],
            lookml=_lookml_for("int_x__b"),
        )
        assert "lineage.temporary_model_exposed" in rules_fired(lineage.run(context))

    def test_high_fanout_is_reported(self, config) -> None:
        shared = model("int_x__shared", layer="integration", materialised="view")
        consumers = [
            keyed_model(f"wh_a__c{index}_fact", deps=["int_x__shared"]) for index in range(14)
        ]
        context = build_context(config, models=[shared, *consumers])
        assert "lineage.high_fanout" in rules_fired(lineage.run(context))


def _lookml_for(model_name: str, *, columns: list[str] | None = None) -> LookmlData:
    data = LookmlData()
    view = LookmlView(name=f"{model_name}_view", sql_table_name=model_name)
    view.model_name = model_name
    view.fields = [
        LookmlField(
            name=name,
            view=view.name,
            field_type="dimension",
            referenced_columns=[name],
        )
        for name in (columns or ["thing_pk"])
    ]
    data.views[view.name] = view
    return data


class TestConformance:
    def test_a_design_matching_its_model_passes(self, config) -> None:
        context = build_context(
            config,
            models=[keyed_model(columns=[column("thing_pk")])],
            design=[designed("wh_a__thing_fact")],
            tests=key_tests(),
        )
        fired = rules_fired(conformance.run(context))
        assert "conformance.column_missing_from_model" not in fired
        assert "conformance.column_missing_from_design" not in fired

    def test_a_designed_column_that_was_not_built_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[keyed_model(columns=[column("thing_pk")])],
            design=[
                designed(
                    "wh_a__thing_fact",
                    columns=[
                        DesignedColumn(name="thing_pk", is_primary_key=True, note="Key."),
                        DesignedColumn(name="thing_promised", note="Promised."),
                    ],
                )
            ],
        )
        assert "conformance.column_missing_from_model" in rules_fired(conformance.run(context))

    def test_an_undesigned_column_that_was_built_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[keyed_model(columns=[column("thing_pk"), column("thing_extra")])],
            design=[designed("wh_a__thing_fact")],
        )
        assert "conformance.column_missing_from_design" in rules_fired(conformance.run(context))

    def test_a_design_with_no_primary_key_is_reported(self, config) -> None:
        context = build_context(
            config,
            design=[
                designed(
                    "wh_a__thing_fact",
                    columns=[DesignedColumn(name="thing_id", note="An id.")],
                )
            ],
        )
        assert "conformance.design_no_primary_key" in rules_fired(conformance.run(context))

    def test_an_untested_designed_relationship_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[
                keyed_model(columns=[column("thing_pk"), column("other_fk")]),
                model("wh_a__other_dim", columns=[column("other_pk")]),
            ],
            design=[
                designed(
                    "wh_a__thing_fact",
                    columns=[
                        DesignedColumn(name="thing_pk", is_primary_key=True, note="Key."),
                        DesignedColumn(name="other_fk", note="Link."),
                    ],
                ),
                designed(
                    "wh_a__other_dim",
                    columns=[DesignedColumn(name="other_pk", is_primary_key=True, note="Key.")],
                ),
            ],
            design_refs=[
                DesignedRef(
                    from_table="wh_a__thing_fact",
                    from_columns=["other_fk"],
                    to_table="wh_a__other_dim",
                    to_columns=["other_pk"],
                    cardinality="many-to-one",
                )
            ],
            tests=key_tests(),
        )
        assert "conformance.relationship_not_tested" in rules_fired(conformance.run(context))

    def test_a_relationship_pointing_at_a_missing_column_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[keyed_model(columns=[column("thing_pk"), column("other_fk")])],
            design=[
                designed(
                    "wh_a__thing_fact",
                    columns=[
                        DesignedColumn(name="thing_pk", is_primary_key=True, note="Key."),
                        DesignedColumn(name="other_fk", note="Link."),
                    ],
                ),
                designed("wh_a__other_dim"),
            ],
            design_refs=[
                DesignedRef(
                    from_table="wh_a__thing_fact",
                    from_columns=["other_fk"],
                    to_table="wh_a__other_dim",
                    to_columns=["nonesuch_pk"],
                )
            ],
        )
        assert "conformance.relationship_key_missing" in rules_fired(conformance.run(context))

    def test_unavailable_types_are_declared_not_passed_over(self, config) -> None:
        """Reporting no drift when nothing was compared would mislead."""
        context = build_context(
            config,
            models=[keyed_model(columns=[column("thing_pk")])],
            design=[designed("wh_a__thing_fact")],
        )
        finding = next(
            item
            for item in conformance.run(context)
            if item.rule == "conformance.types_unavailable"
        )
        assert finding.points == 0.0
        assert "were not checked" in finding.consequence

    def test_type_drift_is_reported_when_types_are_known(self, config) -> None:
        context = build_context(
            config,
            models=[
                keyed_model(
                    columns=[column("thing_pk", data_type="STRING")],
                )
            ],
            design=[
                designed(
                    "wh_a__thing_fact",
                    columns=[
                        DesignedColumn(
                            name="thing_pk",
                            data_type="numeric",
                            is_primary_key=True,
                            note="Key.",
                        )
                    ],
                )
            ],
        )
        assert "conformance.type_drift" in rules_fired(conformance.run(context))

    def test_equivalent_type_names_are_not_drift(self, config) -> None:
        context = build_context(
            config,
            models=[keyed_model(columns=[column("thing_pk", data_type="STRING")])],
            design=[
                designed(
                    "wh_a__thing_fact",
                    columns=[
                        DesignedColumn(
                            name="thing_pk",
                            data_type="varchar",
                            is_primary_key=True,
                            note="Key.",
                        )
                    ],
                )
            ],
        )
        assert "conformance.type_drift" not in rules_fired(conformance.run(context))


class TestCrossLayer:
    def test_a_view_matching_its_model_passes(self, config) -> None:
        context = build_context(
            config,
            models=[keyed_model(columns=[column("thing_pk")])],
            lookml=_lookml_for("wh_a__thing_fact", columns=["thing_pk"]),
            exposures=[
                Exposure(
                    name="dash",
                    unique_id="exposure.my_project.dash",
                    depends_on_models=["wh_a__thing_fact"],
                )
            ],
        )
        fired = rules_fired(crosslayer.run(context))
        assert "crosslayer.field_references_missing_column" not in fired
        assert "crosslayer.exposure_missing" not in fired

    def test_a_field_reading_a_removed_column_is_reported(self, config) -> None:
        """The rule that catches a dbt rename breaking a dashboard, in the same
        pull request rather than by the client."""
        context = build_context(
            config,
            models=[keyed_model(columns=[column("thing_pk")])],
            lookml=_lookml_for("wh_a__thing_fact", columns=["thing_renamed"]),
        )
        finding = next(
            item
            for item in crosslayer.run(context)
            if item.rule == "crosslayer.field_references_missing_column"
        )
        assert finding.severity.value == "high"

    def test_a_view_pointing_at_no_model_is_reported(self, config) -> None:
        context = build_context(
            config, models=[keyed_model()], lookml=_lookml_for("nonesuch_table")
        )
        assert "crosslayer.view_model_missing" in rules_fired(crosslayer.run(context))

    def test_an_unresolvable_table_name_is_declared_not_guessed(self, config) -> None:
        data = LookmlData()
        view = LookmlView(name="v", sql_table_name="@{project}.@{dataset}.@{table}")
        data.views["v"] = view
        context = build_context(config, models=[keyed_model()], lookml=data)
        finding = next(
            item
            for item in crosslayer.run(context)
            if item.rule == "crosslayer.view_table_unresolvable"
        )
        assert "was not checked" in finding.consequence

    def test_an_explore_with_no_caching_policy_is_reported(self, config) -> None:
        from hunter.model.entities import Explore

        data = _lookml_for("wh_a__thing_fact", columns=["thing_pk"])
        data.explores["e"] = Explore(name="e", view_name="wh_a__thing_fact_view")
        context = build_context(
            config, models=[keyed_model(columns=[column("thing_pk")])], lookml=data
        )
        assert "crosslayer.explore_no_caching_policy" in rules_fired(crosslayer.run(context))

    def test_a_model_feeding_reports_with_no_exposure_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[keyed_model(columns=[column("thing_pk")])],
            lookml=_lookml_for("wh_a__thing_fact", columns=["thing_pk"]),
        )
        assert "crosslayer.exposure_missing" in rules_fired(crosslayer.run(context))


def _droughty(
    *,
    generated: list[DroughtyTestSpec] | None = None,
    overrides: list[DroughtyTestSpec] | None = None,
    ignored: list[str] | None = None,
    defined: list[str] | None = None,
    refs: list[str] | None = None,
    empty: list[str] | None = None,
    modified: dt.date | None = None,
) -> DroughtyData:
    data = DroughtyData()
    data.found_any = True
    data.artifacts.generated_tests = generated or []
    data.artifacts.test_overrides = overrides or []
    data.artifacts.test_ignore_models = ignored or []
    data.artifacts.doc_blocks_defined = defined or []
    data.artifacts.doc_refs = refs or []
    data.artifacts.doc_blocks_empty = empty or []
    data.artifacts.schema_modified_at = modified
    return data


class TestDroughty:
    def test_an_override_that_never_landed_is_reported(self, config) -> None:
        """Replaces the hand check the pilot team does after every regeneration."""
        generated = [
            DroughtyTestSpec(
                model="wh_a__thing_fact",
                column="thing_pk",
                test_name="not_null",
                kind="not_null",
            )
        ]
        overrides = [
            *generated,
            DroughtyTestSpec(
                model="wh_a__thing_fact",
                column="thing_pk",
                test_name="unique",
                kind="unique",
            ),
        ]
        context = build_context(
            config,
            models=[keyed_model()],
            droughty=_droughty(generated=generated, overrides=overrides),
        )
        assert "droughty.override_dropped" in rules_fired(droughty.run(context))

    def test_a_clean_regeneration_reports_nothing(self, config) -> None:
        specs = [
            DroughtyTestSpec(
                model="wh_a__thing_fact",
                column="thing_pk",
                test_name="unique",
                kind="unique",
            )
        ]
        context = build_context(
            config,
            models=[keyed_model()],
            tests=key_tests(),
            droughty=_droughty(generated=specs, overrides=specs),
        )
        assert "droughty.override_dropped" not in rules_fired(droughty.run(context))

    def test_a_generated_test_missing_from_dbt_is_reported(self, config) -> None:
        specs = [
            DroughtyTestSpec(
                model="wh_a__thing_fact",
                column="thing_pk",
                test_name="unique",
                kind="unique",
            )
        ]
        context = build_context(config, models=[keyed_model()], droughty=_droughty(generated=specs))
        assert "droughty.generated_test_missing" in rules_fired(droughty.run(context))

    def test_an_excluded_model_is_not_reported(self, config) -> None:
        """test_ignore records a decision the team already made."""
        specs = [
            DroughtyTestSpec(
                model="wh_a__thing_fact",
                column="thing_pk",
                test_name="unique",
                kind="unique",
            )
        ]
        context = build_context(
            config,
            models=[keyed_model()],
            droughty=_droughty(generated=specs, ignored=["wh_a__thing_fact"]),
        )
        fired = rules_fired(droughty.run(context))
        assert "droughty.generated_test_missing" not in fired
        assert "droughty.model_not_covered" not in fired

    def test_an_undefined_description_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[keyed_model()],
            droughty=_droughty(refs=["thing_pk"], defined=[]),
        )
        assert "droughty.description_undefined" in rules_fired(droughty.run(context))

    def test_an_orphan_description_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[keyed_model()],
            droughty=_droughty(refs=[], defined=["never_used"]),
        )
        assert "droughty.description_orphaned" in rules_fired(droughty.run(context))

    def test_a_stale_generated_schema_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[keyed_model()],
            droughty=_droughty(modified=dt.date(2026, 1, 1)),
        )
        assert "droughty.schema_stale" in rules_fired(droughty.run(context))


class TestAlignment:
    def test_a_built_and_designed_entity_reports_nothing(self, config) -> None:
        context = build_context(
            config,
            models=[keyed_model(columns=[column("thing_pk")])],
            design=[designed("wh_a__thing_fact")],
        )
        fired = rules_fired(alignment.run(context))
        assert "alignment.built_off_plan" not in fired

    def test_an_off_plan_build_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[keyed_model()],
            design=[designed("wh_a__other_fact")],
        )
        assert "alignment.built_off_plan" in rules_fired(alignment.run(context))

    def test_an_approved_off_plan_build_is_informational(self, config) -> None:
        register = Register.model_validate(
            {
                "off_plan_approved": [
                    {
                        "model": "wh_a__thing_fact",
                        "reason": "built for the year-end close, design entry to follow",
                        "approved_by": "sav",
                    }
                ]
            }
        )
        context = build_context(
            config,
            models=[keyed_model()],
            design=[designed("wh_a__other_fact")],
            register=register,
        )
        findings = alignment.run(context)
        fired = rules_fired(findings)
        assert "alignment.built_off_plan" not in fired
        approval = next(item for item in findings if item.rule == "alignment.approved_off_plan")
        assert approval.points == 0.0
        assert "year-end close" in approval.consequence

    def test_a_switched_off_model_is_reported_as_such(self, config) -> None:
        context = build_context(
            config,
            disabled=[keyed_model()],
            design=[designed("wh_a__thing_fact")],
        )
        assert "alignment.built_disabled" in rules_fired(alignment.run(context))

    def test_the_design_backlog_is_one_count_not_many_failures(self, config) -> None:
        from hunter.model.entities import ConceptualEntity

        concepts = [ConceptualEntity(name=f"wh_a__idea_{index}", domain="a") for index in range(20)]
        context = build_context(config, concepts=concepts)
        findings = [
            item for item in alignment.run(context) if item.rule == "alignment.design_backlog"
        ]
        assert len(findings) == 1
        assert findings[0].points == 0.0
        assert "20 business entities" in findings[0].summary

    def test_a_stale_diagram_claim_is_reported(self, config) -> None:
        from hunter.model.entities import ConceptualEntity

        context = build_context(
            config,
            concepts=[ConceptualEntity(name="wh_a__things", domain="a", claimed_status="built")],
        )
        assert "alignment.diagram_claim_stale" in rules_fired(alignment.run(context))

    def test_a_stale_register_entry_is_reported(self, config) -> None:
        register = Register.model_validate({"models": {"wh_gone__x": {"owner": "team"}}})
        context = build_context(config, models=[keyed_model()], register=register)
        assert "register.entry_matches_no_model" in rules_fired(alignment.run(context))

    def test_an_expired_silence_is_reported(self, config) -> None:
        register = Register.model_validate(
            {
                "ignores": [
                    {
                        "rule": "documentation.model_description_missing",
                        "reason": "documentation sweep that never happened",
                        "expires": "2026-01-31",
                    }
                ]
            }
        )
        context = build_context(config, models=[keyed_model()], register=register)
        assert "register.ignore_expired" in rules_fired(alignment.run(context))

    def test_denominators_exceed_the_failures(self, config) -> None:
        """Counting only failures made this dimension score zero whenever a
        single entity was off-plan."""
        context = build_context(
            config,
            models=[keyed_model(), keyed_model("wh_a__second_fact")],
            design=[designed("wh_a__thing_fact")],
        )
        findings = alignment.run(context)
        lost = sum(item.effective_points for item in findings)
        available = sum(entry.points_available for entry in context.examined.values())
        assert available > lost > 0
