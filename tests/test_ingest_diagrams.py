"""Reading authored Mermaid diagrams for the conceptual and logical models."""

from __future__ import annotations

from pathlib import Path

from hunter.ingest.diagrams import (
    is_furniture,
    parse_conceptual,
    parse_logical,
    parse_node,
    parse_style_props,
)

CONCEPTUAL = """
---
title: "Conceptual Data Model"
---
block-beta
  columns 3

  block:header:3
  title("Conceptual Data Model")
  end

  block:legend:3
    legend__label("Legend:")
    legend__built("built")
    legend__planned("planned")
    legend__flagged("deviates")
  end

  block:sales:1
    columns 5
    space:2
    sales__label("Sales")
    sales__orders("orders")
    sales__returns("returns")
    sales__refunds("refunds ⚠")
    sales__quotes("quotes (draft)")
  end

style legend__built fill:#EFEFEF,stroke:#666,stroke-width:1px
style legend__planned fill:#EFEFEF,stroke:#666,stroke-width:1px,stroke-dasharray:4 3,opacity:0.6
style legend__flagged fill:#EFEFEF,stroke:#c0392b,stroke-width:2px
style sales fill:#BAD7E9,stroke:#BAD7E9
style sales__label fill:#BAD7E9,stroke:#BAD7E9,stroke-width:0px
style sales__returns stroke-dasharray:4 3,opacity:0.6
style sales__refunds stroke:#c0392b,stroke-width:2px
"""

LOGICAL = """
---
title: Data Flow Diagram (Level 1)
---
flowchart LR
subgraph dfd_container["<b>Warehouse</b>"]
subgraph subgraph__erp["<b>ERP</b>"]
    data_source__database__sap[(<i class="fa"></i> SAP R1)]:::classdef__database_sources
end
    wh_sales__orders["orders"]
    wh_sales__order_lines["order lines"]
    dashboard__sales["Sales dashboard"]
    data_source__database__sap --> wh_sales__orders
    wh_sales__orders --> wh_sales__order_lines
    wh_sales__order_lines --> dashboard__sales
end
classDef classdef__database_sources fill:#eee
"""


class TestParseNode:
    def test_quoted_label_in_round_brackets(self) -> None:
        assert parse_node('  sales__orders("orders")') == ("sales__orders", "orders")

    def test_unquoted_label_in_square_brackets(self) -> None:
        assert parse_node("  a__b[orders]") == ("a__b", "orders")

    def test_label_containing_brackets_is_not_truncated(self) -> None:
        """A pilot entity is labelled "billing document (billed sales)"."""
        assert parse_node('  a__b["billing document (billed sales)"]') == (
            "a__b",
            "billing document (billed sales)",
        )

    def test_cylinder_shape(self) -> None:
        assert parse_node("  ds__x[(SAP R1)]") == ("ds__x", "SAP R1")

    def test_html_in_a_label_is_stripped(self) -> None:
        node_id, label = parse_node('  ds__x[(<i class="fa"></i> SAP R1)]')
        assert (node_id, label) == ("ds__x", "SAP R1")

    def test_a_line_with_no_node_returns_none(self) -> None:
        assert parse_node("  style a fill:#fff") is None
        assert parse_node("flowchart LR") is None
        assert parse_node("") is None


class TestFurniture:
    def test_scaffolding_is_recognised(self) -> None:
        assert is_furniture("title")
        assert is_furniture("legend__built")
        assert is_furniture("sales__label")
        assert is_furniture("data_source__database__sap")
        assert is_furniture("dashboard__sales")

    def test_a_real_entity_is_not_furniture(self) -> None:
        assert not is_furniture("sales__orders")
        assert not is_furniture("wh_finance__budget_fact")


class TestStyleProps:
    def test_parses_comma_separated_properties(self) -> None:
        props = parse_style_props("fill:#EFEFEF,stroke:#666,stroke-width:1px")
        assert props == {"fill": "#efefef", "stroke": "#666", "stroke-width": "1px"}

    def test_ignores_parts_with_no_colon(self) -> None:
        assert parse_style_props("fill:#fff,,junk") == {"fill": "#fff"}


class TestConceptual:
    def test_entities_names_labels_and_domains(self, tmp_path: Path) -> None:
        path = tmp_path / "conceptual.mermaid"
        path.write_text(CONCEPTUAL, encoding="utf-8")
        data = parse_conceptual(path)

        assert set(data.entities) == {
            "sales__orders",
            "sales__returns",
            "sales__refunds",
            "sales__quotes",
        }
        assert data.entities["sales__orders"].business_name == "orders"
        assert data.entities["sales__orders"].domain == "sales"
        assert data.issues == []

    def test_the_colour_code_is_learnt_from_the_legend(self, tmp_path: Path) -> None:
        path = tmp_path / "conceptual.mermaid"
        path.write_text(CONCEPTUAL, encoding="utf-8")
        data = parse_conceptual(path)
        assert set(data.legend) == {"built", "planned", "flagged"}

    def test_claimed_status_is_read_from_the_style(self, tmp_path: Path) -> None:
        path = tmp_path / "conceptual.mermaid"
        path.write_text(CONCEPTUAL, encoding="utf-8")
        entities = parse_conceptual(path).entities

        assert entities["sales__returns"].claimed_status == "planned"
        assert entities["sales__refunds"].claimed_status == "flagged"
        # Unstyled nodes take the legend's "built" entry
        assert entities["sales__orders"].claimed_status == "built"

    def test_a_warning_glyph_marks_a_deviation(self, tmp_path: Path) -> None:
        path = tmp_path / "conceptual.mermaid"
        path.write_text(CONCEPTUAL, encoding="utf-8")
        entity = parse_conceptual(path).entities["sales__refunds"]
        assert entity.claimed_status == "flagged"
        # The glyph is stripped from the business name a reader sees
        assert entity.business_name == "refunds"

    def test_a_label_with_brackets_survives(self, tmp_path: Path) -> None:
        path = tmp_path / "conceptual.mermaid"
        path.write_text(CONCEPTUAL, encoding="utf-8")
        assert parse_conceptual(path).entities["sales__quotes"].business_name == "quotes (draft)"

    def test_a_file_with_no_entities_is_reported(self, tmp_path: Path) -> None:
        path = tmp_path / "conceptual.mermaid"
        path.write_text("flowchart LR\n  a --> b\n", encoding="utf-8")
        data = parse_conceptual(path)
        assert data.entities == {}
        assert len(data.issues) == 1
        assert data.issues[0].recoverable

    def test_an_unreadable_file_is_reported_not_raised(self, tmp_path: Path) -> None:
        data = parse_conceptual(tmp_path / "absent.mermaid")
        assert data.entities == {}
        assert not data.issues[0].recoverable


class TestLogical:
    def test_entities_and_data_sources_are_separated(self, tmp_path: Path) -> None:
        path = tmp_path / "logical.mermaid"
        path.write_text(LOGICAL, encoding="utf-8")
        data = parse_logical(path)

        assert set(data.entities) == {"wh_sales__orders", "wh_sales__order_lines"}
        assert set(data.data_sources) == {"data_source__database__sap"}

    def test_flows_are_captured_and_sorted(self, tmp_path: Path) -> None:
        path = tmp_path / "logical.mermaid"
        path.write_text(LOGICAL, encoding="utf-8")
        data = parse_logical(path)
        assert ("data_source__database__sap", "wh_sales__orders") in data.flows
        assert data.flows == sorted(data.flows)

    def test_sources_feeding_an_entity(self, tmp_path: Path) -> None:
        path = tmp_path / "logical.mermaid"
        path.write_text(LOGICAL, encoding="utf-8")
        data = parse_logical(path)
        assert data.sources_for("wh_sales__orders") == ["data_source__database__sap"]
        assert data.sources_for("wh_sales__order_lines") == []
