"""The alignment chain: states, coverage and the stale-diagram check."""

from __future__ import annotations

import pytest

from hunter.config import resolve
from hunter.config.register import Register
from hunter.enums import AlignmentState, Presence
from hunter.ingest.diagrams import LogicalData
from hunter.ingest.manifest import ManifestData
from hunter.model.align import build_alignment
from hunter.model.build import build_project
from hunter.model.entities import (
    ConceptualEntity,
    DesignedColumn,
    DesignedEntity,
    Model,
    TestRef,
)


@pytest.fixture
def config():
    return resolve().config


def warehouse_model(name: str, *, description: str | None = None) -> Model:
    return Model(
        name=name,
        unique_id=f"model.my_project.{name}",
        path=f"models/warehouse/{name}.sql",
        materialisation="table",
        description=description,
        package="my_project",
    )


def designed(name: str, *, grain: str | None = None, domain: str | None = None) -> DesignedEntity:
    return DesignedEntity(
        name=name,
        columns=[DesignedColumn(name="thing_pk", is_primary_key=True)],
        grain_note=grain,
        domain=domain,
    )


def assemble(
    config,
    *,
    models: list[Model] | None = None,
    disabled: list[Model] | None = None,
    design: list[DesignedEntity] | None = None,
    concepts: list[ConceptualEntity] | None = None,
    logical: LogicalData | None = None,
    register: Register | None = None,
    tests: list[TestRef] | None = None,
):
    manifest = ManifestData()
    manifest.project_name = "my_project"
    for item in models or []:
        manifest.models[item.name] = item
    for item in disabled or []:
        item.enabled = False
        manifest.disabled_models[item.name] = item
    manifest.tests = tests or []

    from hunter.ingest.dbml import DbmlData
    from hunter.ingest.diagrams import ConceptualData

    dbml = DbmlData()
    for item in design or []:
        dbml.entities[item.name] = item

    conceptual = ConceptualData()
    for item in concepts or []:
        conceptual.entities[item.name] = item

    reg = register or Register()
    project, _ = build_project(
        config=config,
        register=reg,
        manifest=manifest,
        dbml=dbml if design else None,
        conceptual=conceptual if concepts else None,
        logical=logical,
    )
    return build_alignment(project, config, reg, logical=logical)


class TestStates:
    def test_designed_and_built_is_delivered(self, config) -> None:
        alignment = assemble(
            config,
            models=[warehouse_model("wh_a__thing_fact")],
            design=[designed("wh_a__thing_fact")],
        )
        assert [row.state for row in alignment.rows] == [AlignmentState.DESIGNED_AND_DELIVERED]

    def test_designed_but_not_built_is_not_started(self, config) -> None:
        alignment = assemble(config, design=[designed("wh_a__thing_fact")])
        assert alignment.rows[0].state is AlignmentState.DESIGNED_NOT_STARTED

    def test_built_but_switched_off_is_its_own_state(self, config) -> None:
        """Six pilot models are built and disabled by a dbt variable. Calling
        those designed-not-started would be six false findings."""
        alignment = assemble(
            config,
            disabled=[warehouse_model("wh_a__thing_fact")],
            design=[designed("wh_a__thing_fact")],
        )
        row = alignment.rows[0]
        assert row.state is AlignmentState.BUILT_DISABLED
        assert row.repo is Presence.DISABLED

    def test_built_without_a_design_is_off_plan(self, config) -> None:
        alignment = assemble(config, models=[warehouse_model("wh_a__thing_fact")])
        assert alignment.rows[0].state is AlignmentState.BUILT_OFF_PLAN

    def test_an_approved_off_plan_build_is_labelled_as_approved(self, config) -> None:
        """It still appears, so the approval is visible rather than invisible."""
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
        alignment = assemble(
            config, models=[warehouse_model("wh_a__thing_fact")], register=register
        )
        row = alignment.rows[0]
        assert row.state is AlignmentState.APPROVED_OFF_PLAN
        assert row.approved_off_plan
        assert "year-end close" in row.approval_reason

    def test_a_business_entity_with_nothing_below_it_is_the_design_backlog(self, config) -> None:
        alignment = assemble(config, concepts=[ConceptualEntity(name="wh_a__things", domain="a")])
        row = alignment.rows[0]
        assert row.state is AlignmentState.CONCEPTUAL_ONLY
        assert "design backlog" in row.state_meaning

    def test_a_data_flow_entity_alone_is_labelled_as_such(self, config) -> None:
        logical = LogicalData(entities={"wh_a__vendor_thing": "vendor thing"})
        alignment = assemble(config, logical=logical)
        assert alignment.rows[0].state is AlignmentState.LOGICAL_ONLY

    def test_the_warehouse_column_is_unknown_not_absent(self, config) -> None:
        """FR17.7: saying Hunter did not look beats assuming it is missing."""
        alignment = assemble(
            config,
            models=[warehouse_model("wh_a__thing_fact")],
            design=[designed("wh_a__thing_fact")],
        )
        assert alignment.rows[0].warehouse is Presence.UNKNOWN
        assert not alignment.warehouse_known


class TestScopeOfTheChain:
    def test_staging_and_integration_models_are_not_entities(self, config) -> None:
        """Including them would report 129 pilot staging models as off-plan."""
        staging = Model(
            name="stg_x__thing",
            unique_id="model.my_project.stg_x__thing",
            path="models/staging/stg_x/thing.sql",
            package="my_project",
        )
        alignment = assemble(config, models=[staging])
        assert alignment.rows == []

    def test_vendored_models_are_not_entities(self, config) -> None:
        vendored = warehouse_model("elementary_thing")
        vendored.package = "elementary"
        vendored.vendored = True
        alignment = assemble(config, models=[vendored])
        assert alignment.rows == []


class TestMatching:
    def test_a_design_and_a_model_named_differently_still_pair_up(self, config) -> None:
        alignment = assemble(
            config,
            models=[warehouse_model("wh_a__things")],
            design=[designed("wh_a__thing_fact")],
        )
        assert len(alignment.rows) == 1
        row = alignment.rows[0]
        assert row.state is AlignmentState.DESIGNED_AND_DELIVERED
        assert row.match_method == "normalised"
        assert row.match_confidence < 1.0

    def test_a_register_mapping_settles_a_name_difference(self, config) -> None:
        register = Register.model_validate(
            {"models": {"wh_a__completely_different": {"implements": "wh_a__thing_fact"}}}
        )
        alignment = assemble(
            config,
            models=[warehouse_model("wh_a__completely_different")],
            design=[designed("wh_a__thing_fact")],
            register=register,
        )
        assert len(alignment.rows) == 1
        assert alignment.rows[0].state is AlignmentState.DESIGNED_AND_DELIVERED


class TestStaleClaims:
    """The conceptual diagram's colour coding is a claim, not truth."""

    def test_a_diagram_claiming_built_when_nothing_exists_is_reported(self, config) -> None:
        alignment = assemble(
            config,
            concepts=[ConceptualEntity(name="wh_a__things", domain="a", claimed_status="built")],
        )
        row = alignment.rows[0]
        assert row.claim_matches_reality is False
        assert alignment.stale_claims() == [row]

    def test_a_diagram_claiming_planned_when_it_is_built_is_reported(self, config) -> None:
        alignment = assemble(
            config,
            models=[warehouse_model("wh_a__thing_fact")],
            design=[designed("wh_a__thing_fact")],
            concepts=[ConceptualEntity(name="wh_a__things", domain="a", claimed_status="planned")],
        )
        assert alignment.rows[0].claim_matches_reality is False

    def test_an_accurate_claim_is_not_reported(self, config) -> None:
        alignment = assemble(
            config,
            models=[warehouse_model("wh_a__thing_fact")],
            design=[designed("wh_a__thing_fact")],
            concepts=[ConceptualEntity(name="wh_a__things", domain="a", claimed_status="built")],
        )
        assert alignment.rows[0].claim_matches_reality is True
        assert alignment.stale_claims() == []

    def test_a_deviation_marker_carries_no_expectation(self, config) -> None:
        alignment = assemble(
            config,
            concepts=[ConceptualEntity(name="wh_a__things", domain="a", claimed_status="flagged")],
        )
        assert alignment.rows[0].claim_matches_reality is None

    def test_no_claim_means_nothing_to_check(self, config) -> None:
        alignment = assemble(config, concepts=[ConceptualEntity(name="wh_a__things", domain="a")])
        assert alignment.rows[0].claim_matches_reality is None


class TestCoverage:
    def test_delivery_and_design_coverage(self, config) -> None:
        alignment = assemble(
            config,
            models=[warehouse_model("wh_a__built_fact")],
            design=[designed("wh_a__built_fact"), designed("wh_a__unbuilt_fact")],
            concepts=[
                ConceptualEntity(name="wh_a__builts", domain="a"),
                ConceptualEntity(name="wh_a__unbuilts", domain="a"),
                ConceptualEntity(name="wh_a__undesigneds", domain="a"),
            ],
        )
        coverage = alignment.coverage
        assert coverage.designed_entities == 2
        assert coverage.designed_and_built == 1
        assert coverage.delivery_coverage == 50.0
        assert coverage.conceptual_entities == 3
        assert coverage.conceptual_designed == 2
        assert coverage.design_coverage == pytest.approx(66.7, abs=0.1)

    def test_table_and_column_documentation_are_counted_apart(self, config) -> None:
        """The pilot documents 1,615 of 1,615 columns and 0 of 54 tables. One
        figure would call that undocumented."""
        from hunter.model.entities import Column

        model = warehouse_model("wh_a__thing_fact")
        model.columns = [Column(name="thing_pk", description="The key.")]
        alignment = assemble(config, models=[model], design=[designed("wh_a__thing_fact")])

        coverage = alignment.coverage
        assert coverage.documentation_coverage == 0.0
        assert coverage.column_documentation_coverage == 100.0

    def test_key_tests_count_towards_test_coverage_and_weak_ones_do_not(self, config) -> None:
        weak = TestRef(
            unique_id="test.1",
            name="at_least_one",
            kind="at_least_one",
            tests_model="wh_a__weak_fact",
        )
        strong = TestRef(
            unique_id="test.2",
            name="unique",
            kind="unique",
            tests_model="wh_a__strong_fact",
        )
        alignment = assemble(
            config,
            models=[warehouse_model("wh_a__weak_fact"), warehouse_model("wh_a__strong_fact")],
            design=[designed("wh_a__weak_fact"), designed("wh_a__strong_fact")],
            tests=[weak, strong],
        )
        assert alignment.coverage.built_entities == 2
        assert alignment.coverage.tested_entities == 1
        assert alignment.coverage.test_coverage == 50.0

    def test_percentages_are_none_rather_than_zero_when_there_is_no_denominator(
        self, config
    ) -> None:
        alignment = assemble(config)
        assert alignment.coverage.delivery_coverage is None
        assert alignment.coverage.design_coverage is None


class TestPresentation:
    def test_rows_carry_a_business_label_and_a_technical_name(self, config) -> None:
        """FR14.3: the business name reads first, the physical name on demand."""
        alignment = assemble(
            config,
            models=[warehouse_model("wh_a__thing_fact")],
            design=[designed("wh_a__thing_fact", grain="one row per thing")],
            concepts=[ConceptualEntity(name="wh_a__things", business_name="Things", domain="a")],
        )
        row = alignment.rows[0]
        assert row.label == "Things"
        assert row.technical_name == "wh_a__thing_fact"
        assert row.grain == "one row per thing"

    def test_every_state_has_a_label_and_a_plain_meaning(self, config) -> None:
        for state in AlignmentState:
            from hunter.enums import ALIGNMENT_STATE_LABELS, ALIGNMENT_STATE_MEANINGS

            assert ALIGNMENT_STATE_LABELS[state].strip()
            assert ALIGNMENT_STATE_MEANINGS[state].strip()

    def test_rows_are_grouped_by_domain_for_the_site(self, config) -> None:
        alignment = assemble(
            config,
            models=[warehouse_model("wh_alpha__one_fact"), warehouse_model("wh_beta__two_fact")],
            design=[designed("wh_alpha__one_fact"), designed("wh_beta__two_fact")],
        )
        grouped = alignment.by_domain()
        assert sorted(grouped) == ["alpha", "beta"]

    def test_state_counts_are_sorted_for_a_stable_trend(self, config) -> None:
        alignment = assemble(
            config,
            models=[warehouse_model("wh_a__one_fact")],
            design=[designed("wh_a__one_fact"), designed("wh_a__two_fact")],
        )
        counts = alignment.state_counts()
        assert list(counts) == sorted(counts, key=lambda state: state.value)
