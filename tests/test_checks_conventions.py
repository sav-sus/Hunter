"""Documentation, naming and SQL structure rules."""

from __future__ import annotations

from conftest import build_context, column, designed, model, rules_fired
from hunter.checks import documentation, naming, structure
from hunter.checks.structure import hardcoded_references, strip_noise
from hunter.config.register import Register


class TestDocumentation:
    def test_a_documented_owned_model_passes(self, config) -> None:
        context = build_context(
            config,
            models=[
                model(
                    "wh_a__thing_fact",
                    description="One row per thing, held for the commerce team.",
                    owner="commerce",
                    columns=[column("thing_pk", description="The surrogate key.")],
                )
            ],
        )
        assert documentation.run(context) == []

    def test_a_missing_description_is_reported(self, config) -> None:
        context = build_context(config, models=[model("wh_a__thing_fact", owner="team")])
        assert "documentation.model_description_missing" in rules_fired(documentation.run(context))

    def test_a_placeholder_description_is_reported_separately(self, config) -> None:
        context = build_context(
            config, models=[model("wh_a__thing_fact", description="TBD", owner="team")]
        )
        fired = rules_fired(documentation.run(context))
        assert "documentation.model_description_placeholder" in fired
        assert "documentation.model_description_missing" not in fired

    def test_a_staging_model_needs_no_table_description(self, config) -> None:
        """The house ruleset asks for table descriptions in the warehouse layer
        only, because that is the layer people read."""
        context = build_context(config, models=[model("stg_x__thing", layer="staging")])
        assert "documentation.model_description_missing" not in rules_fired(
            documentation.run(context)
        )

    def test_a_two_word_column_description_is_accepted(self, config) -> None:
        """ "Order date" is a useful column description, unlike a table one."""
        context = build_context(
            config,
            models=[
                model(
                    "wh_a__thing_fact",
                    description="One row per thing, held for commerce.",
                    owner="commerce",
                    columns=[column("order_dt", description="Order date")],
                )
            ],
        )
        assert documentation.run(context) == []

    def test_a_designed_entity_with_no_grain_is_reported(self, config) -> None:
        context = build_context(
            config,
            design=[designed("wh_a__thing_fact", note="A thing.", grain=None)],
        )
        assert "documentation.design_grain_missing" in rules_fired(documentation.run(context))

    def test_a_designed_entity_with_no_note_is_reported(self, config) -> None:
        context = build_context(
            config, design=[designed("wh_a__thing_fact", note=None, grain=None)]
        )
        fired = rules_fired(documentation.run(context))
        assert "documentation.design_note_missing" in fired
        # Not both: the missing note is the finding, not the missing grain too
        assert "documentation.design_grain_missing" not in fired


class TestNaming:
    def test_a_conventional_model_passes(self, config) -> None:
        context = build_context(
            config,
            models=[
                model(
                    "wh_a__thing_fact",
                    columns=[column("thing_pk"), column("created_dt")],
                )
            ],
        )
        assert naming.run(context) == []

    def test_a_wrong_layer_prefix_is_reported(self, config) -> None:
        context = build_context(config, models=[model("base_a__thing_fact", layer="staging")])
        assert "naming.layer_prefix_wrong" in rules_fired(naming.run(context))

    def test_a_warehouse_model_with_no_entity_suffix_is_reported(self, config) -> None:
        context = build_context(config, models=[model("wh_a__thing")])
        assert "naming.entity_suffix_missing" in rules_fired(naming.run(context))

    def test_a_fact_with_no_key_column_is_reported(self, config) -> None:
        context = build_context(
            config, models=[model("wh_a__thing_fact", columns=[column("thing_name")])]
        )
        assert "naming.primary_key_column_missing" in rules_fired(naming.run(context))

    def test_a_date_column_without_a_suffix_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[
                model(
                    "wh_a__thing_fact",
                    columns=[column("thing_pk"), column("ORDER_DATE")],
                )
            ],
        )
        assert "naming.date_column_suffix" in rules_fired(naming.run(context))

    def test_a_layer_reading_above_itself_is_reported(self, config) -> None:
        """Integration may read staging and integration, not warehouse."""
        context = build_context(
            config,
            models=[
                model("wh_a__thing_fact", columns=[column("thing_pk")]),
                model("int_a__thing", layer="integration", deps=["wh_a__thing_fact"]),
            ],
        )
        finding = next(
            item for item in naming.run(context) if item.rule == "naming.layer_boundary_violation"
        )
        assert finding.subject == "int_a__thing"

    def test_a_warehouse_model_reading_a_source_directly_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[
                model(
                    "wh_a__thing_fact",
                    columns=[column("thing_pk")],
                    sources=["raw.orders"],
                )
            ],
        )
        assert "naming.direct_source_reference" in rules_fired(naming.run(context))

    def test_a_staging_model_reading_a_source_is_fine(self, config) -> None:
        context = build_context(
            config, models=[model("stg_x__thing", layer="staging", sources=["raw.orders"])]
        )
        assert "naming.direct_source_reference" not in rules_fired(naming.run(context))

    def test_a_forbidden_materialisation_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[
                model(
                    "wh_a__thing_fact",
                    columns=[column("thing_pk")],
                    materialised="view",
                )
            ],
        )
        assert "naming.materialisation_not_permitted" in rules_fired(naming.run(context))

    def test_a_model_in_no_declared_layer_is_reported(self, config) -> None:
        context = build_context(config, models=[model("mystery", layer="none")])
        assert "naming.model_outside_every_layer" in rules_fired(naming.run(context))


class TestStructureHelpers:
    def test_comments_are_removed_and_line_numbers_survive(self) -> None:
        sql = "select 1\n-- a comment\nfrom x\n"
        cleaned = strip_noise(sql)
        assert "comment" not in cleaned
        assert cleaned.count("\n") == sql.count("\n")

    def test_ref_and_source_get_distinct_markers(self) -> None:
        from hunter.checks.structure import REF_MARKER, SOURCE_MARKER

        assert REF_MARKER in strip_noise("select * from {{ ref('x') }}")
        assert SOURCE_MARKER in strip_noise("select * from {{ source('a', 'b') }}")

    def test_is_distinct_from_is_not_a_from_clause(self) -> None:
        """A real false positive: it invented a hardcoded table reference."""
        sql = "select 1 where a.x is distinct from prev.y"
        assert hardcoded_references(strip_noise(sql), set()) == []

    def test_extract_from_is_not_a_from_clause(self) -> None:
        sql = "select extract(day from order_dt.value) from {{ ref('x') }}"
        assert hardcoded_references(strip_noise(sql), set()) == []

    def test_a_real_dotted_table_is_found(self) -> None:
        sql = "select 1 from project.dataset.table_name"
        found = hardcoded_references(strip_noise(sql), set())
        assert found == [("project.dataset.table_name", 1)]

    def test_a_cte_name_is_not_a_hardcoded_reference(self) -> None:
        sql = "with mine as (select 1) select * from mine.x"
        assert hardcoded_references(strip_noise(sql), {"mine"}) == []


class TestStructure:
    def test_selecting_everything_from_a_ref_is_ordinary_dbt_style(self, config) -> None:
        """This fired on 226 of 228 pilot models before being narrowed."""
        context = build_context(
            config,
            models=[
                model(
                    "wh_a__thing_fact",
                    columns=[column("thing_pk")],
                    sql="select * from {{ ref('int_a__thing') }}\n",
                )
            ],
        )
        assert "structure.select_star_from_source" not in rules_fired(structure.run(context))

    def test_selecting_everything_from_a_source_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[
                model(
                    "stg_x__thing",
                    layer="staging",
                    sql="select * from {{ source('raw', 'orders') }}\n",
                )
            ],
        )
        assert "structure.select_star_from_source" in rules_fired(structure.run(context))

    def test_selecting_everything_from_an_internal_step_is_fine(self, config) -> None:
        context = build_context(
            config,
            models=[
                model(
                    "wh_a__thing_fact",
                    columns=[column("thing_pk")],
                    sql="with final as (select 1 as x)\nselect * from final\n",
                )
            ],
        )
        assert "structure.select_star_from_source" not in rules_fired(structure.run(context))

    def test_a_hardcoded_table_reference_is_reported_with_its_line(self, config) -> None:
        context = build_context(
            config,
            models=[
                model(
                    "wh_a__thing_fact",
                    columns=[column("thing_pk")],
                    sql="select 1\nfrom `project.dataset.thing`\n",
                )
            ],
        )
        finding = next(
            item for item in structure.run(context) if item.rule == "structure.hardcoded_reference"
        )
        assert finding.line == 2

    def test_a_long_model_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[
                model(
                    "wh_a__thing_fact",
                    columns=[column("thing_pk")],
                    sql="select 1\n" * 500,
                )
            ],
        )
        assert "structure.model_too_long" in rules_fired(structure.run(context))

    def test_too_many_joins_is_reported(self, config) -> None:
        joins = "\n".join(f"join t{index} on true" for index in range(9))
        context = build_context(
            config,
            models=[
                model(
                    "wh_a__thing_fact",
                    columns=[column("thing_pk")],
                    sql=f"select 1 from {{{{ ref('a') }}}}\n{joins}\n",
                )
            ],
        )
        assert "structure.too_many_joins" in rules_fired(structure.run(context))

    def test_a_badly_named_step_is_reported(self, config) -> None:
        context = build_context(
            config,
            models=[
                model(
                    "wh_a__thing_fact",
                    columns=[column("thing_pk")],
                    sql="with BadName as (select 1)\nselect 1 from BadName\n",
                )
            ],
        )
        assert "structure.cte_name_invalid" in rules_fired(structure.run(context))

    def test_a_seed_has_no_sql_to_check(self, config) -> None:
        context = build_context(
            config,
            models=[model("a_seed", layer="seeds", resource_type="seed")],
        )
        assert structure.run(context) == []


class TestSilencedRuleStillListed:
    def test_a_silenced_finding_is_reported_with_its_reason(self, config) -> None:
        register = Register.model_validate(
            {
                "ignores": [
                    {
                        "rule": "naming.layer_prefix_wrong",
                        "models": ["base_*"],
                        "reason": "base models are a deliberate convention here",
                        "expires": "2027-01-31",
                    }
                ]
            }
        )
        context = build_context(
            config,
            models=[model("base_a__thing_fact", layer="staging")],
            register=register,
        )
        finding = next(
            item for item in naming.run(context) if item.rule == "naming.layer_prefix_wrong"
        )
        assert finding.suppressed
        assert finding.effective_points == 0.0
        assert "deliberate convention" in finding.suppression_reason
