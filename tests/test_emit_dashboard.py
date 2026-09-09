"""The dashboard and the SVG charts it draws.

Two things matter here beyond "it renders". The file has to be genuinely
self-contained, because it gets emailed and opened offline, so a test asserts
there is no reference to any external host. And every chart has to be well
formed SVG rather than a string that happens to look like one, so the whole
page is parsed as XML.
"""

from __future__ import annotations

import datetime as dt
import re
import xml.etree.ElementTree as ElementTree
from pathlib import Path

import pytest

from hunter import brand
from hunter.emit import charts
from hunter.emit.charts import Slice
from hunter.emit.dashboard import (
    MERMAID_URL,
    ROADMAP_LANES,
    checklist,
    dashboard_html,
    journey,
    readiness_rows,
    roadmap_lanes,
)
from hunter.enums import AlignmentState
from hunter.run import RunResult, run

EXAMPLE = Path(__file__).parent.parent / "examples" / "tiny-shop"
AS_OF = dt.date(2026, 9, 8)
GENERATED = dt.datetime(2026, 9, 8, 12, 0, 0)


@pytest.fixture(scope="module")
def result() -> RunResult:
    return run(EXAMPLE, as_of=AS_OF, read_git=False)


@pytest.fixture(scope="module")
def page(result: RunResult) -> str:
    return dashboard_html(result, generated_at=GENERATED)


class TestSelfContained:
    """The reason the charts are hand-drawn instead of a library."""

    def test_the_only_thing_fetched_is_the_diagram_library(self, page: str) -> None:
        """A report is opened offline. Anything remote would silently not draw.

        Data URIs are the logo and the favicon, inlined from the package. The
        one allowed remote reference is the pinned Mermaid build that draws the
        model diagrams, and the page has to survive it not arriving.
        """
        remote = re.findall(r'(?:src|href)="(?!#|data:)([^"]+)"', page)
        assert remote == [MERMAID_URL], f"unexpected remote references: {remote}"

    def test_the_diagram_library_is_pinned(self) -> None:
        assert re.search(r"mermaid@\d+\.\d+\.\d+/", MERMAID_URL)

    def test_the_page_degrades_when_the_library_does_not_load(self, page: str) -> None:
        """The diagram source is in the HTML, and a note explains what happened."""
        assert "<pre class='mermaid'>" in page
        assert "could not be loaded" in page
        assert 'onerror="window.hunterDiagramsOffline=true"' in page

    def test_the_logo_is_inlined(self, page: str) -> None:
        assert "data:image/png;base64," in page

    def test_one_file_holds_the_whole_stylesheet(self, page: str) -> None:
        assert "<style>" in page
        assert brand.PRIMARY in page


class TestWellFormed:
    def test_every_chart_parses_as_xml(self, page: str) -> None:
        """A malformed path or an unescaped label would show as a blank panel."""
        found = re.findall(r"<svg\b.*?</svg>", page, re.S)
        assert len(found) >= 1, f"expected at least the score ring, found {len(found)}"
        for svg in found:
            ElementTree.fromstring(svg)  # raises if the SVG is not well formed

    def test_the_page_has_no_unfilled_placeholders(self, page: str) -> None:
        """A rule title is a template. One reaching the page renders as raw
        "{subject} is built but switched off", which this catches.

        The stylesheet, the scripts (including the JSON the selector reads) and
        the diagram source are all full of braces by nature, so they are
        removed before looking.
        """
        body = re.sub(r"<style>.*?</style>", "", page, flags=re.S)
        body = re.sub(r"<script[^>]*>.*?</script>", "", body, flags=re.S)
        # Entity-relationship diagram source is "table { column }" by design.
        body = re.sub(r"<pre class='mermaid'>.*?</pre>", "", body, flags=re.S)
        assert "{" not in body and "}" not in body


class TestContent:
    def test_the_score_is_the_headline(self, page: str, result: RunResult) -> None:
        assert f"{result.score.total:g}" in page
        assert f"Grade {result.score.grade}" in page

    def test_the_checklist_comes_before_everything_else(self, page: str) -> None:
        """The statements are the value. They sit directly under the score."""
        assert page.index('id="top"') < page.index("id='checklist'")
        assert page.index("id='checklist'") < page.index('id="alignment"')
        assert page.index('id="alignment"') < page.index('id="readiness"')

    def test_the_repository_is_named_in_the_headline(self, page: str, result: RunResult) -> None:
        """A product owner opens this and should know whose repository it is."""
        assert f"<h1>{result.meta['repo']}</h1>" in page

    def test_the_hero_counts_how_many_checks_hold(self, page: str, result: RunResult) -> None:
        checks = [check for section in checklist(result) for check in section.checks]
        holding = sum(1 for check in checks if check.holds)
        assert f"{holding} of {len(checks)}</b><span>checks hold" in page

    def test_the_removed_panels_stay_removed(self, page: str) -> None:
        for title in (
            "What everything else is built on",
            "Do these first",
            "What this score is not based on",
            "Every file this was computed from",
        ):
            assert title not in page

    def test_the_off_plan_table_is_named_by_its_technical_name(self, page: str) -> None:
        """A business label of "legacy" is no use to whoever has to act."""
        assert "wh_commerce__legacy_fact" in page

    def test_the_attribution_is_present(self, page: str, result: RunResult) -> None:
        assert result.config.branding.attribution in page


class TestJourney:
    """The strip from what was asked for to what people can use."""

    def test_every_level_hunter_read_is_a_stage(self, result: RunResult) -> None:
        labels = [stage.label for stage in journey(result)]
        assert labels == [
            "Asked for by the business",
            "Designed",
            "Built",
            "Live in the warehouse",
            "Reachable in Looker",
        ]

    def test_each_drop_is_counted_on_its_own_terms(self, result: RunResult) -> None:
        """Built includes an off-plan table, so built is not designed minus a drop."""
        by_label = {stage.label: stage for stage in journey(result)}
        assert by_label["Asked for by the business"].dropped == 1
        assert by_label["Designed"].dropped == 1
        assert by_label["Built"].count == 6
        assert by_label["Built"].dropped == 2

    def test_a_drop_is_written_in_words_on_the_page(self, page: str) -> None:
        assert "&minus;1 not designed" in page
        assert "&minus;3 not in Looker" in page


class TestChecklist:
    """The statements under the score, grouped by what they are about."""

    def test_a_section_only_appears_where_its_source_was_read(self, result: RunResult) -> None:
        titles = [section.title for section in checklist(result)]
        assert titles == [
            "Design to build",
            "Warehouse to Looker",
            "Droughty",
            "Documentation",
            "Tests",
        ]

    def test_the_section_titles_are_what_the_sync_checks_group_by(self, result: RunResult) -> None:
        """hunter.sync reads sections by title, so a rename here breaks a CI check."""
        titles = {section.title for section in checklist(result)}
        assert {"Design to build", "Warehouse to Looker", "Droughty"} <= titles

    def test_a_failing_statement_names_what_let_it_down(self, result: RunResult) -> None:
        """A fraction says there is a problem. A name says where it is."""
        by_statement = {
            check.statement: check for section in checklist(result) for check in section.checks
        }
        design = by_statement["Every built table has a design"]
        assert design.done < design.total
        assert "wh_commerce__legacy_fact" in design.missing

    def test_a_switched_off_model_still_counts_as_built(self, result: RunResult) -> None:
        """The code was written, reviewed and merged. It is not unbuilt."""
        by_statement = {
            check.statement: check for section in checklist(result) for check in section.checks
        }
        assert (
            "wh_commerce__forecast_fact"
            not in by_statement["Every designed table is built"].missing
        )

    def test_rule_backed_statements_trace_to_the_rule(self, result: RunResult) -> None:
        """Every figure on the page has a finding behind it."""
        by_statement = {
            check.statement: check for section in checklist(result) for check in section.checks
        }
        owner = by_statement["Every table has a named owner"]
        assert owner.rule == "documentation.owner_missing"
        assert owner.total == result.examined[owner.rule].checked
        assert owner.missing == ("wh_master__customer_dim",)

    def test_a_rule_that_examined_nothing_makes_no_statement(self, result: RunResult) -> None:
        """Passing a check with nothing to check is not passing."""
        statements = {check.statement for section in checklist(result) for check in section.checks}
        rendered = dashboard_html(result, generated_at=GENERATED)
        for statement in statements:
            assert statement in rendered

    def test_the_verdict_is_yes_only_when_nothing_is_missing(self) -> None:
        from hunter.emit.dashboard import Check

        assert Check("s", 6, 6).verdict == "yes"
        assert Check("s", 5, 6).verdict == "mostly"
        assert Check("s", 3, 6).verdict == "no"
        assert Check("s", 0, 0).holds is False


class TestDataFlow:
    """The DAG card: every area together, then one tab per area."""

    def test_the_card_has_a_tab_for_every_area_and_one_for_all(self, page: str) -> None:
        card = page[page.index('id="dag"') :]
        card = card[: card.index("</section>")]
        assert "data-pane='all'" in card
        assert "data-pane='dag-commerce'" in card
        assert "data-pane='dag-master'" in card
        assert "data-pane='overview'" not in card
        assert "subgraph sources[&quot;raw sources&quot;]" in card

    def test_each_area_carries_its_graph_as_data_for_the_selector(self, page: str) -> None:
        """The browser redraws a dbt-style selection from this, not from the picture."""
        card = page[page.index('id="dag"') :]
        card = card[: card.index("</section>")]
        assert card.count("class='dag-spec'") == 3
        assert "list='dag-names'" in card
        assert "<option value='wh_commerce__order_fact'>" in card

    def test_each_tab_group_is_self_contained(self, page: str) -> None:
        """Two tabbed cards on one page must not share pane ids."""
        assert page.count("class='tabbed'") == 2
        assert "id='pane-" not in page


class TestDiagrams:
    """The three models a stakeholder can switch between."""

    def test_the_three_levels_are_carried_as_source(self, page: str) -> None:
        for key in ("conceptual", "logical", "physical"):
            assert f"data-key='{key}'" in page
        assert "data-key='built'" not in page, "built is the physical model as it exists"

    def test_the_logical_tab_is_the_authored_data_flow_diagram(
        self, page: str, result: RunResult
    ) -> None:
        """The team's own picture, coloured by state, without the front matter."""
        assert result.logical_source is not None
        card = page[page.index("data-key='logical'") :]
        card = card[: card.index("</pre>")]
        assert "Shop Platform" in card, "an authored label survives"
        assert "layout: elk" not in card and "title:" not in card
        assert "style wh_commerce__orders fill:#d6ead6" in card, "designed and delivered"
        assert "style data_source__database__shop fill:#e1f6fe" in card

    def test_the_colour_key_is_html_under_the_canvas_not_a_box_in_the_diagram(
        self, page: str
    ) -> None:
        assert 'subgraph legend["What the colours mean"]' not in page
        card = page[page.index("data-key='conceptual'") :]
        card = card[: card.index("data-key='logical'")]
        assert "class='heat-key'" in card
        assert "Designed and delivered" in card

    def test_the_conceptual_model_is_cards_by_area_coloured_by_state(self, page: str) -> None:
        """The business model needs no library: entity cards, one section per area."""
        card = page[page.index("data-key='conceptual'") :]
        card = card[: card.index("data-key='logical'")]
        assert "class='concept'" in card
        assert card.count("<section class='erd-group'>") == 2, "commerce and master"
        assert "<b>returns</b><span>On the business model only</span>" in card
        assert "<code>wh_commerce__order_fact</code>" in card, "technical name under the label"

    def test_the_physical_tab_is_the_dbml_design_as_cards(self, page: str) -> None:
        """Cards, not a library drawing: they render offline and carry the notes."""
        card = page[page.index("data-key='physical'") :]
        card = card[: card.index('id="dag"')]  # up to the next card; groups are sections too
        assert "pre class='mermaid'" not in card
        assert "data-table='wh_master__supplier_dim'" in card, "designed but unbuilt"
        assert "<span class='grain'>One row per order</span>" in card
        assert "data-ref='wh_master__customer_dim.customer_pk'" in card, "a drawn relationship"
        assert "<em class='pk'>PK</em>" in card and "<em class='fk'>FK</em>" in card
        assert "title='Surrogate key for the order.'" in card, "the column note, on hover"

    def test_the_diagrams_card_has_a_find_box(self, page: str) -> None:
        card = page[page.index('id="diagrams"') :]
        card = card[: card.index("</section>")]
        assert "placeholder='Find a table or entity in this diagram'" in card

    def test_the_diagram_source_is_escaped(self, page: str, result: RunResult) -> None:
        """A quote in a business label must not end the pre element early."""
        from hunter.emit import mermaid

        raw = mermaid.conceptual_diagram(result.alignment).strip()
        assert raw not in page or "&quot;" in page or '"' not in raw


class TestReadiness:
    """Every built table, and what it still needs to be finished."""

    def test_only_built_tables_are_listed(self, result: RunResult) -> None:
        names = {row.name for row in readiness_rows(result)}
        assert "wh_master__supplier_dim" not in names, "designed, not built"
        assert "wh_commerce__forecast_fact" in names, "built, even though switched off"
        assert "stg_shop__orders" not in names, "a staging step, not a warehouse table"

    def test_each_table_names_its_gaps_and_is_ready_only_with_none(self, result: RunResult) -> None:
        by_name = {row.name: row for row in readiness_rows(result)}
        # The best table in the example is one step short: Droughty generated a
        # test for it that dbt does not carry. Everything else about it is in place.
        assert by_name["wh_commerce__order_fact"].gaps == ("Droughty tests not applied",)
        assert by_name["wh_commerce__order_fact"].ready is False
        assert "no owner" in by_name["wh_master__customer_dim"].gaps
        assert "no LookML view" in by_name["wh_master__product_dim"].gaps
        assert "no tests" in by_name["wh_commerce__daily_sales_xa"].gaps
        assert "switched off" in by_name["wh_commerce__forecast_fact"].gaps

    def test_key_tests_distinguish_one_from_both(self, result: RunResult) -> None:
        by_name = {row.name: row for row in readiness_rows(result)}
        assert by_name["wh_commerce__order_fact"].key_tests == "yes"
        assert by_name["wh_master__customer_dim"].key_tests == "partial"
        assert by_name["wh_commerce__daily_sales_xa"].key_tests == "no"

    def test_every_dimension_gets_a_column(self, page: str) -> None:
        for head in (
            "Described",
            "Columns described",
            "Owner",
            "Key tests",
            "LookML view",
            "Droughty",
            "In the warehouse",
            "What it still needs",
        ):
            assert f"<th>{head}</th>" in page

    def test_the_rows_carry_what_the_filter_searches(self, page: str) -> None:
        assert 'data-find="' in page
        assert "id='table-search'" in page
        assert "id='table-gaps'" in page, "the gaps-only toggle"

    def test_area_tabs_match_the_data_flow_card(self, page: str) -> None:
        """Same tabs, same look: all areas first, then one per area."""
        card = page[page.index('id="readiness"') :]
        card = card[: card.index("</section>")]
        assert "id='table-areas'" in card
        assert "data-area=''>All areas</button>" in card
        assert "data-area='commerce'" in card and "data-area='master'" in card
        assert "<em class='chip gap'>no owner</em>" in card
        assert "data-gaps='1'" in page
        assert "<b>0 of 6</b><span>built tables ready" in page

    def test_the_order_does_not_move_between_runs(self, result: RunResult) -> None:
        assert [row.name for row in readiness_rows(result)] == [
            row.name for row in readiness_rows(result)
        ]


class TestAlignment:
    """The conceptual, logical and physical models against what is built."""

    def test_the_card_is_called_modelling_alignment(self, page: str) -> None:
        assert "<h2>Modelling alignment</h2>" in page

    def test_every_level_hunter_read_gets_a_column(self, page: str) -> None:
        for heading in (
            "Conceptual \u00b7 the business model",
            "Logical \u00b7 the data flow",
            "Physical \u00b7 the DBML design",
            "Built \u00b7 in the repository",
        ):
            assert heading in page

    def test_a_break_in_the_chain_is_drawn_differently_from_agreement(self, page: str) -> None:
        assert "class='lane-link ok'" in page
        assert "class='lane-link broken'" in page
        assert "class='lane-link unplanned'" in page

    def test_every_row_opens_to_what_to_do_next(self, page: str, result: RunResult) -> None:
        from hunter.emit.dashboard import NEXT_STEP

        card = page[page.index('id="alignment"') :]
        card = card[: card.index("</section>")]
        assert card.count("<details class='arow'") == len(result.alignment.rows)
        assert "Do next." in card
        assert NEXT_STEP[AlignmentState.BUILT_OFF_PLAN][:40] in card

    def test_rows_are_grouped_by_area_with_a_count(self, page: str) -> None:
        card = page[page.index('id="alignment"') :]
        card = card[: card.index("</section>")]
        assert "data-group='commerce'" in card and "data-group='master'" in card
        assert "designed and delivered</em>" in card

    def test_the_headline_chips_read_the_situation(self, page: str) -> None:
        card = page[page.index('id="alignment"') :]
        card = card[: card.index("</section>")]
        assert "asked for and now in the repository" in card
        assert "built with no design" in card
        assert "asked for, never designed" in card

    def test_rows_carry_what_the_search_matches(self, page: str) -> None:
        card = page[page.index('id="alignment"') :]
        card = card[: card.index("</section>")]
        assert "class='find'" in card
        assert 'data-find="' in card
        assert "wh_commerce__legacy_fact" in card


class TestDeterminism:
    def test_two_renders_are_identical(self, result: RunResult) -> None:
        first = dashboard_html(result, generated_at=GENERATED)
        second = dashboard_html(result, generated_at=GENERATED)
        assert first == second


class TestCharts:
    """The primitives, at their edges. Every one of these returns "" rather
    than a broken chart, because an empty panel is dropped by the page."""

    def test_no_rows_draws_nothing(self) -> None:
        assert charts.bars([]) == ""
        assert charts.donut([]) == ""
        assert charts.stacked([]) == ""
        assert charts.heat_grid([]) == ""

    def test_a_funnel_needs_two_stages(self) -> None:
        assert charts.funnel([Slice("only", 5, brand.PRIMARY)]) == ""

    def test_all_zero_values_draw_nothing_rather_than_dividing_by_zero(self) -> None:
        zeros = [Slice("a", 0, brand.PRIMARY), Slice("b", 0, brand.SKY)]
        assert charts.donut(zeros) == ""
        assert charts.stacked(zeros) == ""

    def test_a_zero_value_bar_still_draws_a_visible_stub(self) -> None:
        """Otherwise a zero row looks like a rendering failure, not a zero."""
        svg = charts.bars([Slice("nothing", 0, brand.PRIMARY)])
        widths = re.findall(r'width="([\d.]+)" height="18"', svg)
        assert widths and float(widths[-1]) >= 2.0

    def test_a_label_with_markup_in_it_is_escaped(self) -> None:
        svg = charts.bars([Slice('<script>&"', 1, brand.PRIMARY)])
        assert "<script>" not in svg
        assert "&lt;script&gt;" in svg
        ElementTree.fromstring(svg)

    def test_the_score_ring_clamps_out_of_range_values(self) -> None:
        for score in (-10.0, 0.0, 100.0, 140.0):
            ElementTree.fromstring(charts.score_ring(score, "A"))

    def test_a_meter_with_a_zero_denominator_does_not_divide_by_zero(self) -> None:
        ElementTree.fromstring(charts.meter(3, 0))

    def test_donut_slices_sum_to_the_full_circle(self) -> None:
        """A gap or an overlap would read as a wrong proportion."""
        slices = [Slice("a", 1, "#000"), Slice("b", 2, "#111"), Slice("c", 3, "#222")]
        svg = charts.donut(slices)
        spans = [float(m) for m in re.findall(r'stroke-dasharray="([\d.]+) ', svg)]
        assert len(spans) == 3
        circumference = sum(spans)
        assert circumference == pytest.approx(2 * 3.14159265 * (190 / 2 - 14), rel=1e-3)


class TestBrand:
    def test_the_palette_is_the_published_one(self) -> None:
        """Lifted from rittmananalytics.com's own design tokens, not guessed."""
        assert brand.PRIMARY == "#525aff"
        assert brand.INK == "#151d2d"

    def test_every_grade_has_a_colour(self) -> None:
        for grade in "ABCDE":
            assert brand.grade_colour(grade).startswith("#")

    def test_an_unknown_grade_falls_back_rather_than_raising(self) -> None:
        assert brand.grade_colour("?") == brand.MUTED_INK

    def test_score_colour_agrees_with_the_grade_boundaries(self) -> None:
        assert brand.score_colour(95) == brand.GRADE_COLOURS["A"]
        assert brand.score_colour(85) == brand.GRADE_COLOURS["B"]
        assert brand.score_colour(10) == brand.GRADE_COLOURS["E"]

    def test_the_packaged_assets_exist(self) -> None:
        assert brand.logo_uri().startswith("data:image/png;base64,")
        assert brand.favicon_uri().startswith("data:image/x-icon;base64,")


class TestRoadmap:
    """Every tracked entity sits in exactly one lane, and the register decides first."""

    def test_every_lane_is_on_the_page_in_order(self, page: str) -> None:
        card = page[page.index('id="roadmap"') :]
        card = card[: card.index("</section>")]
        positions = [card.index(f"data-lane='{key}'") for key, *_ in ROADMAP_LANES]
        assert positions == sorted(positions)

    def test_the_roadmap_sits_between_the_data_flow_and_the_table_list(self, page: str) -> None:
        """Reading order: alignment, diagrams, data flow, roadmap, built tables."""
        assert (
            page.index('id="alignment"')
            < page.index('id="diagrams"')
            < page.index('id="dag"')
            < page.index('id="roadmap"')
            < page.index('id="readiness"')
        )

    def test_a_verified_table_is_live_with_the_word_on_it(self, result: RunResult) -> None:
        lanes = {lane.key: lane for lane in roadmap_lanes(result)}
        order = next(
            item for item in lanes["live"].items if item.technical_name == "wh_commerce__order_fact"
        )
        assert order.status == "verified"
        assert "verified by sav" in order.next_step

    def test_a_register_declared_temporary_step_has_its_own_lane(self, result: RunResult) -> None:
        lanes = {lane.key: lane for lane in roadmap_lanes(result)}
        names = {item.technical_name for item in lanes["temporary"].items}
        assert "int_shop__orders" in names
        step = next(
            item for item in lanes["temporary"].items if item.technical_name == "int_shop__orders"
        )
        assert step.next_step == "review by 31 January 2027"

    def test_a_deprecated_status_outranks_the_chain(self, result: RunResult) -> None:
        """The legacy fact is built and live by the code. The register says it is going."""
        lanes = {lane.key: lane for lane in roadmap_lanes(result)}
        names = {item.technical_name for item in lanes["phasing_out"].items}
        assert names == {"wh_commerce__legacy_fact"}
        assert "wh_commerce__legacy_fact" not in {
            item.technical_name for item in lanes["live"].items
        }

    def test_designed_not_built_is_planned(self, result: RunResult) -> None:
        lanes = {lane.key: lane for lane in roadmap_lanes(result)}
        planned = {
            item.technical_name or item.label: item.next_step for item in lanes["planned"].items
        }
        assert planned["wh_master__supplier_dim"] == "designed, waiting to be built"
        assert planned["returns"] == "agreed, not designed yet"

    def test_a_switched_off_table_is_being_built(self, result: RunResult) -> None:
        lanes = {lane.key: lane for lane in roadmap_lanes(result)}
        names = {item.technical_name for item in lanes["building"].items}
        assert "wh_commerce__forecast_fact" in names

    def test_no_entity_sits_in_two_lanes(self, result: RunResult) -> None:
        seen: list[str] = []
        for lane in roadmap_lanes(result):
            seen += [item.technical_name or item.label for item in lane.items]
        assert len(seen) == len(set(seen))


class TestStatusColumn:
    def test_every_built_table_carries_one_of_the_three_words(self, result: RunResult) -> None:
        rows = readiness_rows(result)
        assert rows
        assert {row.status for row in rows} <= {
            "temporary",
            "verified",
            "permanent",
            "not determined",
        }

    def test_the_verified_table_says_who_verified_it(self, result: RunResult) -> None:
        row = next(row for row in readiness_rows(result) if row.name == "wh_commerce__order_fact")
        assert row.status == "verified"
        assert row.status_note == "verified by sav on 8 September 2026"

    def test_the_status_is_searchable(self, result: RunResult) -> None:
        row = next(row for row in readiness_rows(result) if row.name == "wh_commerce__order_fact")
        assert "verified" in row.searchable


class TestRoadmapSearch:
    def test_the_roadmap_has_a_find_box_like_the_other_cards(self, page: str) -> None:
        card = page[page.index('id="roadmap"') :]
        card = card[: card.index("</section>")]
        assert "class='find'" in card
        assert "class='tally'" in card

    def test_every_roadmap_item_carries_what_the_search_matches(self, page: str) -> None:
        card = page[page.index('id="roadmap"') :]
        card = card[: card.index("</section>")]
        assert card.count("<li data-find=") == card.count("<li ")
        assert "wh_commerce__legacy_fact" in card
