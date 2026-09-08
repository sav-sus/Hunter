"""LookML reading: refinements, table resolution and field references."""

from __future__ import annotations

from pathlib import Path

import pytest

from hunter.ingest.lookml import (
    is_refinement,
    load_lookml,
    parse_file,
    refinement_target,
    resolve_paths,
    table_to_model_name,
)

BASE_VIEW = """
view: orders_fact {
  sql_table_name: wh_sales__orders_fact ;;
  dimension: order_pk {
    primary_key: yes
    type: string
    sql: ${TABLE}.order_pk ;;
    description: "Surrogate key."
  }
  dimension: order_status {
    type: string
    sql: ${TABLE}.order_status ;;
  }
}
"""

REFINEMENT = """
view: +orders_fact {
  measure: order_count {
    type: count
    description: "Orders."
  }
  dimension: order_status {
    type: string
    sql: ${TABLE}.order_status_renamed ;;
  }
}
"""


class TestTableToModelName:
    @pytest.mark.parametrize(
        ("given", "expected"),
        [
            ("wh_sales__orders_fact", "wh_sales__orders_fact"),
            ("project.dataset.table_name", "table_name"),
            ("`project.dataset.table_name`", "table_name"),
            ("dataset.table_name ;;", "table_name"),
            ("  spaced_name  ", "spaced_name"),
            ("dataset.{{ table }}", None),
            ("{{ everything }}", None),
            ("123_starts_with_a_digit", None),
            (None, None),
            ("", None),
        ],
    )
    def test_resolution(self, given: str | None, expected: str | None) -> None:
        assert table_to_model_name(given) == expected

    def test_liquid_project_and_dataset_are_stripped(self) -> None:
        """The pilot templates the project and dataset, not the table."""
        value = (
            "\"{{ _user_attributes['gcp_project_id'] }}."
            "{{ _user_attributes['gcp_dataset_name'] }}_ai.`ai_commerce__briefing`\""
        )
        assert table_to_model_name(value) == "ai_commerce__briefing"


class TestRefinements:
    """``view: +name`` layers onto a view. Treating it as a redefinition
    misattributes every field inside it."""

    def test_prefix_is_recognised(self) -> None:
        assert is_refinement("+orders_fact")
        assert not is_refinement("orders_fact")
        assert refinement_target("+orders_fact") == "orders_fact"

    def test_refinement_fields_are_added_to_the_base_view(self, tmp_path: Path) -> None:
        (tmp_path / "a_base.lkml").write_text(BASE_VIEW, encoding="utf-8")
        (tmp_path / "b_agg.lkml").write_text(REFINEMENT, encoding="utf-8")

        data = load_lookml(resolve_paths(tmp_path, ["*.lkml"]))

        assert set(data.views) == {"orders_fact"}
        view = data.views["orders_fact"]
        assert {field.name for field in view.fields} == {
            "order_pk",
            "order_status",
            "order_count",
        }
        assert [measure.name for measure in view.measures] == ["order_count"]
        assert data.issues == []

    def test_a_refinement_field_replaces_what_it_sets(self, tmp_path: Path) -> None:
        (tmp_path / "a_base.lkml").write_text(BASE_VIEW, encoding="utf-8")
        (tmp_path / "b_agg.lkml").write_text(REFINEMENT, encoding="utf-8")

        view = load_lookml(resolve_paths(tmp_path, ["*.lkml"])).views["orders_fact"]
        status = next(field for field in view.fields if field.name == "order_status")
        assert status.referenced_columns == ["order_status_renamed"]

    def test_a_refinement_keeps_what_it_does_not_set(self, tmp_path: Path) -> None:
        """The standard layered structure refines generated dimensions purely to
        add a label. Replacing the whole field drops its column reference, and
        the cross-layer check then has nothing to check. On the pilot that hid
        629 of 4,314 field references."""
        (tmp_path / "a_base.lkml").write_text(BASE_VIEW, encoding="utf-8")
        (tmp_path / "b_stg.lkml").write_text(
            "view: +orders_fact {\n"
            "  dimension: order_pk {\n"
            '    label: "Order Key"\n'
            '    group_label: "Identifiers"\n'
            "  }\n"
            "}\n",
            encoding="utf-8",
        )
        view = load_lookml(resolve_paths(tmp_path, ["*.lkml"])).views["orders_fact"]
        key = next(field for field in view.fields if field.name == "order_pk")

        assert key.label == "Order Key"
        assert key.referenced_columns == ["order_pk"]
        assert key.sql is not None
        assert key.description == "Surrogate key."

    def test_the_base_view_keeps_its_table_mapping(self, tmp_path: Path) -> None:
        (tmp_path / "a_base.lkml").write_text(BASE_VIEW, encoding="utf-8")
        (tmp_path / "b_agg.lkml").write_text(REFINEMENT, encoding="utf-8")

        view = load_lookml(resolve_paths(tmp_path, ["*.lkml"])).views["orders_fact"]
        assert view.model_name == "wh_sales__orders_fact"
        assert len(view.refined_by) == 1

    def test_a_refinement_loading_before_its_base_still_merges(self, tmp_path: Path) -> None:
        """File order must not matter: refinements are applied after every read."""
        (tmp_path / "a_agg.lkml").write_text(REFINEMENT, encoding="utf-8")
        (tmp_path / "z_base.lkml").write_text(BASE_VIEW, encoding="utf-8")

        view = load_lookml(resolve_paths(tmp_path, ["*.lkml"])).views["orders_fact"]
        assert "order_count" in {field.name for field in view.fields}

    def test_a_refinement_overriding_the_table_name_wins(self, tmp_path: Path) -> None:
        (tmp_path / "a_base.lkml").write_text(BASE_VIEW, encoding="utf-8")
        (tmp_path / "b_agg.lkml").write_text(
            "view: +orders_fact {\n  sql_table_name: wh_sales__orders_v2 ;;\n}\n",
            encoding="utf-8",
        )
        view = load_lookml(resolve_paths(tmp_path, ["*.lkml"])).views["orders_fact"]
        assert view.model_name == "wh_sales__orders_v2"

    def test_a_refinement_with_no_base_view_is_reported(self, tmp_path: Path) -> None:
        (tmp_path / "only_refinement.lkml").write_text(REFINEMENT, encoding="utf-8")
        data = load_lookml(resolve_paths(tmp_path, ["*.lkml"]))
        assert data.views == {}
        assert len(data.issues) == 1
        assert data.issues[0].subject == "orders_fact"
        assert "not defined anywhere" in data.issues[0].message


class TestFieldReferences:
    """FR4.1: every LookML field mapped to the dbt column it depends on."""

    def test_table_column_references_are_extracted(self, tmp_path: Path) -> None:
        path = tmp_path / "v.lkml"
        path.write_text(BASE_VIEW, encoding="utf-8")
        view = parse_file(path).views["orders_fact"]
        pk = next(field for field in view.fields if field.name == "order_pk")
        assert pk.referenced_columns == ["order_pk"]

    def test_multiple_columns_in_one_expression(self, tmp_path: Path) -> None:
        path = tmp_path / "v.lkml"
        path.write_text(
            "view: v {\n"
            "  sql_table_name: m ;;\n"
            "  measure: total {\n"
            "    type: sum\n"
            "    sql: ${TABLE}.gross - ${TABLE}.discount ;;\n"
            "  }\n"
            "}\n",
            encoding="utf-8",
        )
        field = parse_file(path).views["v"].fields[0]
        assert field.referenced_columns == ["discount", "gross"]

    def test_a_field_with_no_column_reference_has_an_empty_list(self, tmp_path: Path) -> None:
        path = tmp_path / "v.lkml"
        path.write_text(
            "view: v {\n  sql_table_name: m ;;\n  measure: c {\n    type: count\n  }\n}\n",
            encoding="utf-8",
        )
        assert parse_file(path).views["v"].fields[0].referenced_columns == []

    def test_hidden_is_read(self, tmp_path: Path) -> None:
        path = tmp_path / "v.lkml"
        path.write_text(
            "view: v {\n"
            "  sql_table_name: m ;;\n"
            "  dimension: a {\n    hidden: yes\n    sql: ${TABLE}.a ;;\n  }\n"
            "  dimension: b {\n    sql: ${TABLE}.b ;;\n  }\n"
            "}\n",
            encoding="utf-8",
        )
        fields = {field.name: field for field in parse_file(path).views["v"].fields}
        assert fields["a"].hidden
        assert not fields["b"].hidden


class TestExplores:
    def test_explore_base_view_and_caching_are_read(self, tmp_path: Path) -> None:
        path = tmp_path / "e.lkml"
        path.write_text(
            "explore: sales {\n"
            "  view_name: orders_fact\n"
            "  persist_with: daily_datagroup\n"
            "  join: customers_dim {\n"
            "    relationship: many_to_one\n"
            "    type: left_outer\n"
            "    sql_on: ${orders_fact.customer_fk} = ${customers_dim.customer_pk} ;;\n"
            "  }\n"
            "}\n",
            encoding="utf-8",
        )
        explore = parse_file(path).explores["sales"]
        assert explore.view_name == "orders_fact"
        assert explore.datagroup == "daily_datagroup"
        assert explore.has_caching_policy
        assert explore.joined_views() == ["customers_dim"]

    def test_from_takes_precedence_over_view_name(self, tmp_path: Path) -> None:
        path = tmp_path / "e.lkml"
        path.write_text(
            "explore: sales {\n  from: orders_v2\n  view_name: orders_fact\n}\n",
            encoding="utf-8",
        )
        assert parse_file(path).explores["sales"].view_name == "orders_v2"

    def test_an_explore_with_no_caching_policy_is_visible(self, tmp_path: Path) -> None:
        path = tmp_path / "e.lkml"
        path.write_text("explore: sales {\n  view_name: orders_fact\n}\n", encoding="utf-8")
        assert not parse_file(path).explores["sales"].has_caching_policy


class TestLoading:
    def test_derived_tables_are_recorded_and_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "v.lkml"
        path.write_text(
            "view: v {\n"
            "  derived_table: {\n    sql: select 1 as x ;;\n  }\n"
            "  dimension: x {\n    sql: ${TABLE}.x ;;\n  }\n"
            "}\n",
            encoding="utf-8",
        )
        view = parse_file(path).views["v"]
        assert view.is_derived_table
        assert view.model_name is None

    def test_a_view_defined_in_full_twice_is_reported(self, tmp_path: Path) -> None:
        (tmp_path / "a.lkml").write_text(BASE_VIEW, encoding="utf-8")
        (tmp_path / "b.lkml").write_text(BASE_VIEW, encoding="utf-8")
        data = load_lookml(resolve_paths(tmp_path, ["*.lkml"]))
        assert len(data.views) == 1
        assert any("defined in full in both" in issue.message for issue in data.issues)

    def test_an_unparseable_file_is_reported_not_raised(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.lkml"
        path.write_text("view: { this is not lookml ][", encoding="utf-8")
        data = parse_file(path)
        assert data.views == {}
        assert len(data.issues) == 1
        assert data.issues[0].recoverable

    def test_dashboard_files_are_excluded(self, tmp_path: Path) -> None:
        (tmp_path / "v.lkml").write_text(BASE_VIEW, encoding="utf-8")
        (tmp_path / "x.dashboard.lookml").write_text("- dashboard: d\n", encoding="utf-8")
        paths = resolve_paths(tmp_path, ["*.lkml", "*.lookml"])
        assert [path.name for path in paths] == ["v.lkml"]

    def test_no_files_is_an_empty_result(self) -> None:
        data = load_lookml([])
        assert data.views == {}
        assert data.issues == []
