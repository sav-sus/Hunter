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
from hunter.emit.dashboard import dashboard_html
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

    def test_nothing_is_fetched_from_the_network(self, page: str) -> None:
        """A report is opened offline. Anything remote would silently not draw.

        Data URIs are the exception: those are the logo and the favicon, which
        are inlined from the package rather than fetched.
        """
        remote = re.findall(r'(?:src|href)="(?!#|data:)([^"]+)"', page)
        assert remote == [], f"the dashboard references files it does not carry: {remote}"

    def test_there_is_no_script_tag(self, page: str) -> None:
        assert "<script" not in page.lower()

    def test_the_logo_is_inlined(self, page: str) -> None:
        assert "data:image/png;base64," in page

    def test_one_file_holds_the_whole_stylesheet(self, page: str) -> None:
        assert "<style>" in page
        assert brand.PRIMARY in page


class TestWellFormed:
    def test_every_chart_parses_as_xml(self, page: str) -> None:
        """A malformed path or an unescaped label would show as a blank panel."""
        found = re.findall(r"<svg\b.*?</svg>", page, re.S)
        assert len(found) >= 6, f"expected the charts to be drawn, found {len(found)}"
        for svg in found:
            ElementTree.fromstring(svg)  # raises if the SVG is not well formed

    def test_the_page_has_no_unfilled_placeholders(self, page: str) -> None:
        assert "{" not in page.split("<style>")[0]
        body = page.split("</style>", 1)[1]
        assert "{" not in body and "}" not in body


class TestContent:
    def test_the_score_is_the_headline(self, page: str, result: RunResult) -> None:
        assert f"{result.score.total:g}" in page
        assert f"Grade {result.score.grade}" in page

    def test_the_systemic_gaps_sit_above_the_score(self, page: str, result: RunResult) -> None:
        """FR14.1: one decision nobody took, not a rounding error."""
        gaps = page.index("Needs a decision, not a fix")
        panels = page.index("Where the ground is being lost")
        assert gaps < panels

    def test_an_unmeasured_area_is_named_rather_than_scored_zero(self, page: str) -> None:
        assert "Not measured" in page
        assert "What it costs to run" in page

    def test_the_off_plan_table_is_named_by_its_technical_name(self, page: str) -> None:
        """A business label of "legacy" is no use to whoever has to act."""
        assert "wh_shop__legacy_fact" in page

    def test_the_attribution_is_present(self, page: str, result: RunResult) -> None:
        assert result.config.branding.attribution in page


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
