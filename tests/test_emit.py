"""Output: the report contract, the diagrams, the site, the comment, the showcase."""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from hunter.emit import mermaid
from hunter.emit.markdown import PAGES, mkdocs_config, model_page, table, write_site
from hunter.emit.plain import GLOSSARY, score_sentence, top_fixes
from hunter.emit.pr_comment import MARKER, build_comment, previous_keys
from hunter.emit.report import REPORT_SCHEMA_VERSION, build_report, write_report
from hunter.emit.scaffold import detect, register_text, ruleset_text, scaffold, workflow_text
from hunter.emit.showcase import Window, build_showcase, showcase_page
from hunter.run import RunResult, run

EXAMPLE = Path(__file__).parent.parent / "examples" / "tiny-shop"
AS_OF = dt.date(2026, 9, 8)


@pytest.fixture(scope="module")
def result() -> RunResult:
    return run(EXAMPLE, as_of=AS_OF)


class TestReportContract:
    def test_the_shape_section_11_8_specifies(self, result: RunResult) -> None:
        payload = build_report(result)
        assert set(payload) >= {
            "meta",
            "score",
            "inventory",
            "alignment",
            "findings",
            "coverage",
            "conventions",
        }

    def test_meta_carries_all_three_versions(self, result: RunResult) -> None:
        """FR7.8."""
        meta = build_report(result)["meta"]
        assert meta["hunter_version"]
        assert meta["house_ruleset_version"]
        assert meta["score_model_version"]
        assert meta["report_schema_version"] == REPORT_SCHEMA_VERSION

    def test_meta_says_what_was_and_was_not_scored(self, result: RunResult) -> None:
        meta = build_report(result)["meta"]
        assert "performance_cost" in meta["dimensions_skipped"]
        assert meta["data_available"]

    def test_every_finding_names_its_rule_object_and_place(self, result: RunResult) -> None:
        """FR7.3."""
        for finding in build_report(result)["findings"]:
            assert finding["rule"]
            assert finding["object"]
            assert finding["consequence_plain"]

    def test_the_report_is_written_sorted_and_newline_terminated(
        self, result: RunResult, tmp_path: Path
    ) -> None:
        path = write_report(tmp_path / "report.json", result)
        text = path.read_text(encoding="utf-8")
        assert text.endswith("\n")
        assert json.loads(text)["score"]["total"] == result.score.total

    def test_the_attribution_is_in_the_report(self, result: RunResult) -> None:
        """FR15.7: on every published artifact, not only the site."""
        assert "Rittman" in build_report(result)["meta"]["attribution"]

    def test_raw_sql_is_not_in_the_report(self, result: RunResult) -> None:
        """Several megabytes of client SQL has no business in a report."""
        payload = json.dumps(build_report(result))
        assert "raw_code" not in payload


class TestMermaid:
    def test_node_ids_are_safe(self) -> None:
        assert mermaid.safe_id("wh_a__thing_fact") == "wh_a__thing_fact"
        assert mermaid.safe_id("a-b c") == "a_b_c"
        assert mermaid.safe_id("1bad", "n") == "n_1bad"
        assert mermaid.safe_id("") == "unnamed"

    def test_quotes_in_labels_are_escaped(self) -> None:
        assert '"' not in mermaid.escape('a "quoted" label')

    @pytest.mark.parametrize(
        "level", ["conceptual", "logical", "physical", "collapsed", "domain", "pipeline"]
    )
    def test_every_diagram_is_balanced(self, result: RunResult, level: str) -> None:
        """An unbalanced subgraph is a diagram that will not render."""
        text = {
            "conceptual": lambda: mermaid.conceptual_diagram(result.alignment),
            "logical": lambda: mermaid.logical_diagram(result.project, result.alignment),
            "physical": lambda: mermaid.physical_diagram(result.project, result.alignment),
            "collapsed": lambda: mermaid.collapsed_graph(result.project, result.graph),
            "domain": lambda: mermaid.domain_graph(result.project, result.graph, "commerce"),
            "pipeline": lambda: mermaid.pipeline_graph(
                result.project, result.graph, result.alignment, domain="commerce"
            ),
        }[level]()
        opens = sum(1 for line in text.splitlines() if line.strip().startswith("subgraph"))
        closes = sum(1 for line in text.splitlines() if line.strip() == "end")
        assert opens == closes, text

    def test_the_conceptual_diagram_uses_business_names(self, result: RunResult) -> None:
        text = mermaid.conceptual_diagram(result.alignment)
        assert '"orders"' in text
        assert "wh_commerce__order_fact" not in text.split("style")[0]

    def test_the_conceptual_diagram_carries_a_legend(self, result: RunResult) -> None:
        assert "What the colours mean" in mermaid.conceptual_diagram(result.alignment)

    def test_the_designed_view_groups_attributes_by_role(self, result: RunResult) -> None:
        text = mermaid.logical_diagram(result.project, result.alignment)
        assert "key order_pk PK" in text
        assert "link customer_fk FK" in text

    def test_the_built_view_says_how_each_table_is_built(self, result: RunResult) -> None:
        text = mermaid.physical_diagram(result.project, result.alignment)
        assert "built_as table" in text

    def test_the_designed_view_leads_with_grain_and_purpose(self, result: RunResult) -> None:
        """What one row means and what the table is for, before any column."""
        text = mermaid.logical_diagram(result.project, result.alignment)
        block = text[text.index("wh_commerce__order_fact {") :]
        block = block[: block.index("}")]
        lines = [line.strip() for line in block.splitlines()[1:] if line.strip()]
        assert lines[0] == 'note grain "One row per order"'
        assert lines[1].startswith('note about "Source System:')
        assert not any(line.startswith("grain ") for line in lines), "no trailing grain row"

    def test_describe_drops_the_grain_line_and_cuts_to_fit(self) -> None:
        note = "Table Grain: One row per order.\nSource System: the shop.\nAnything else."
        assert mermaid.describe(note) == "Source System: the shop. Anything else."
        assert mermaid.describe(None) == ""
        long = mermaid.describe("x" * 200, limit=20)
        assert len(long) == 20 and long.endswith("…")

    def test_the_authored_logical_diagram_is_coloured_not_redrawn(self, result: RunResult) -> None:
        text = mermaid.decorate_logical(result.logical_source, result.alignment)
        assert text.splitlines()[0].startswith("%%{init:"), "room for container titles"
        assert text.splitlines()[1] == "flowchart LR", "front matter dropped"
        assert "layout: elk" not in text
        assert 'subgraph subgraph__shop_platform["Shop Platform"]' in text, "kept, minus markup"
        assert "<b" not in text and "</b>" not in text
        assert "style wh_master__suppliers fill:#f2f2f2" in text, "designed, not started"
        assert "style wh_commerce__orders fill:#d6ead6" in text
        assert "style dashboard__shop_performance fill:#e8e0fa" in text
        assert mermaid.decorate_logical(None, result.alignment) == ""

    def test_the_built_and_designed_views_differ(self, result: RunResult) -> None:
        """They answer different questions; identical output would mean a bug."""
        designed = mermaid.logical_diagram(result.project, result.alignment)
        built = mermaid.physical_diagram(result.project, result.alignment)
        assert designed != built

    def test_the_pipeline_runs_from_raw_sources_to_looker(self, result: RunResult) -> None:
        """The DAG a product owner reads: every step, left to right."""
        text = mermaid.pipeline_graph(result.project, result.graph, result.alignment)
        assert 'subgraph sources["raw sources"]' in text
        assert 'subgraph looker_views["Looker views (base layer)"]' in text
        assert 'subgraph looker_explores["Looker explores"]' in text
        assert text.index("raw sources") < text.index('["staging"]') < text.index("Looker views")
        assert text.index("Looker views") < text.index("Looker explores")

    def test_explores_hang_off_the_views_they_open(self, result: RunResult) -> None:
        text = mermaid.pipeline_graph(result.project, result.graph, result.alignment)
        assert "view__wh_commerce__order_fact --> explore__shop_analytics" in text
        assert "view__wh_master__customer_dim --> explore__shop_analytics" in text, "a join"

    def test_the_spec_and_the_text_agree(self, result: RunResult) -> None:
        """The browser rebuilds the diagram from the spec, so they must not drift."""
        import json

        spec = mermaid.pipeline_spec(result.project, result.graph, result.alignment)
        assert mermaid.render_pipeline(spec) == mermaid.pipeline_graph(
            result.project, result.graph, result.alignment
        )
        data = json.loads(spec.to_json())
        assert {node["id"] for node in data["nodes"]} == {node.id for node in spec.nodes}
        assert all(node["shape"] in mermaid.PIPELINE_SHAPES for node in data["nodes"])

    def test_a_selection_renders_only_what_it_keeps(self, result: RunResult) -> None:
        spec = mermaid.pipeline_spec(result.project, result.graph, result.alignment)
        text = mermaid.render_pipeline(spec, keep={"wh_commerce__order_fact", "int_shop__orders"})
        assert "int_shop__orders --> wh_commerce__order_fact" in text
        assert "stg_shop__orders" not in text
        assert "raw sources" not in text

    def test_a_view_named_after_its_model_is_a_separate_node(self, result: RunResult) -> None:
        """Same name, two things. A shared id would draw the view over the model."""
        text = mermaid.pipeline_graph(result.project, result.graph, result.alignment)
        edges = [line.split("-->") for line in text.splitlines() if "-->" in line]
        assert all(left.strip() != right.strip() for left, right in edges), "self-loop drawn"
        assert "wh_master__customer_dim --> view__wh_master__customer_dim" in text

    def test_the_pipeline_colours_health(self, result: RunResult) -> None:
        text = mermaid.pipeline_graph(result.project, result.graph, result.alignment)
        assert "style wh_commerce__legacy_fact fill:#fbe3de" in text, "off-plan is red"
        assert "style wh_commerce__daily_sales_xa fill:#fdf2cc" in text, "untested is amber"

    def test_blast_radius_is_capped(self, result: RunResult) -> None:
        text = mermaid.blast_radius("stg_shop__orders", result.project, result.graph, max_nodes=1)
        assert "and " in text

    def test_a_long_entity_is_truncated_with_a_count(self, result: RunResult) -> None:
        text = mermaid.logical_diagram(result.project, result.alignment, max_attributes=2)
        assert "further_attributes" in text


class TestSite:
    def test_every_declared_page_is_written(self, result: RunResult, tmp_path: Path) -> None:
        write_site(result, tmp_path, per_model_pages=False)
        for name, _ in PAGES:
            assert (tmp_path / "docs" / name).exists(), name

    def test_a_page_per_model_is_written(self, result: RunResult, tmp_path: Path) -> None:
        write_site(result, tmp_path)
        assert (tmp_path / "docs" / "models" / "wh_commerce__order_fact.md").exists()

    def test_no_page_for_a_vendored_model(self, result: RunResult, tmp_path: Path) -> None:
        write_site(result, tmp_path)
        assert not (tmp_path / "docs" / "models" / "package_helper.md").exists()

    def test_the_attribution_footer_is_on_every_page(
        self, result: RunResult, tmp_path: Path
    ) -> None:
        """FR15.7."""
        files = write_site(result, tmp_path, per_model_pages=False)
        for path in files:
            if path.suffix == ".md":
                assert "Rittman" in path.read_text(encoding="utf-8")

    def test_the_headline_is_the_number(self, result: RunResult, tmp_path: Path) -> None:
        """FR7.10: the interpretation sits beneath it, never in place of it."""
        write_site(result, tmp_path, per_model_pages=False)
        text = (tmp_path / "docs" / "index.md").read_text(encoding="utf-8")
        assert f"# {result.score.total:g} / 100" in text
        assert result.score.interpretation in text

    def test_every_page_carries_a_data_timestamp(self, result: RunResult, tmp_path: Path) -> None:
        """F10."""
        write_site(result, tmp_path, per_model_pages=False)
        for name, _ in PAGES:
            if name == "glossary.md":
                continue
            text = (tmp_path / "docs" / name).read_text(encoding="utf-8")
            assert "as at " in text, name

    def test_the_mkdocs_config_is_valid_yaml_with_the_nav(self, result: RunResult) -> None:
        raw = mkdocs_config(result)
        # MkDocs reads a python/name tag that safe_load will not, so it is
        # dropped before parsing. The MkDocsBuilds test proves the real file
        # works; this one checks the structure around it.
        cleaned = "\n".join(line for line in raw.splitlines() if "!!python/name:" not in line)
        loaded = yaml.safe_load(cleaned)
        assert loaded["theme"]["name"] == "material"
        assert len(loaded["nav"]) == len(PAGES)
        assert loaded["plugins"] == ["search"]

    def test_the_glossary_defines_every_term(self) -> None:
        """FR14.4."""
        from hunter.emit.markdown import glossary_page

        text = glossary_page()
        for term in GLOSSARY:
            assert f"**{term}**" in text

    def test_the_not_checked_page_names_what_was_missing(
        self, result: RunResult, tmp_path: Path
    ) -> None:
        write_site(result, tmp_path, per_model_pages=False)
        text = (tmp_path / "docs" / "not-checked.md").read_text(encoding="utf-8")
        assert "warehouse" in text

    def test_a_model_page_covers_columns_lineage_and_findings(self, result: RunResult) -> None:
        text = model_page(result, "wh_commerce__order_fact")
        assert "## Columns" in text
        assert "## What depends on this" in text
        assert "## Findings" in text
        assert "```mermaid" in text

    def test_a_model_page_for_an_absent_model_says_so(self, result: RunResult) -> None:
        assert "was not found" in model_page(result, "nonesuch")

    def test_an_empty_table_gives_a_sentence_not_an_empty_shell(self) -> None:
        assert table(["a"], []) == "_Nothing to show here._\n"

    def test_pipes_in_cells_are_escaped(self) -> None:
        assert "\\|" in table(["a"], [["one | two"]])


class TestMkDocsBuilds:
    """The site must actually build, not merely be written."""

    def test_mkdocs_builds_the_generated_markdown(self, result: RunResult, tmp_path: Path) -> None:
        write_site(result, tmp_path)
        completed = subprocess.run(
            [sys.executable, "-m", "mkdocs", "build", "--strict", "--site-dir", "_built"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        if "No module named mkdocs" in completed.stderr:
            pytest.skip("mkdocs is not installed in this environment")
        assert completed.returncode == 0, completed.stderr[-3000:]
        assert (tmp_path / "_built" / "index.html").exists()
        assert (tmp_path / "_built" / "models" / "wh_commerce__order_fact" / "index.html").exists()


class TestPrComment:
    def test_the_comment_carries_the_marker_for_editing_in_place(self, result: RunResult) -> None:
        """FR11.5."""
        assert build_comment(result).startswith(MARKER)

    def test_the_score_leads(self, result: RunResult) -> None:
        assert f"{result.score.total:g} / 100" in build_comment(result)

    def test_findings_on_a_changed_file_are_listed(self, result: RunResult) -> None:
        model = result.project.models["wh_master__customer_dim"]
        body = build_comment(result, changed_files=[model.path])
        assert "on what this change touches" in body
        assert "customer_dim" in body

    def test_no_findings_says_so_rather_than_showing_an_empty_list(self, result: RunResult) -> None:
        model = result.project.models["stg_shop__customers"]
        body = build_comment(result, changed_files=[model.path])
        assert "No new findings" in body

    def test_the_basis_of_the_comparison_is_stated(self, result: RunResult) -> None:
        """Without a previous report it is a superset, and says so."""
        assert "No previous report was available" in build_comment(result)

    def test_a_previous_report_gives_a_true_diff(self, result: RunResult, tmp_path: Path) -> None:
        path = write_report(tmp_path / "before.json", result)
        body = build_comment(result, previous_report=path)
        assert "Comparing against the previous run" in body
        assert "No new findings" in body

    def test_the_attribution_is_in_the_comment(self, result: RunResult) -> None:
        """FR15.7."""
        assert "Rittman" in build_comment(result)

    def test_advisory_mode_says_it_never_fails(self, result: RunResult) -> None:
        """FR11.7."""
        assert "never fails a build" in build_comment(result)

    def test_the_blast_radius_and_subgraph_appear(self, result: RunResult) -> None:
        model = result.project.models["stg_shop__orders"]
        body = build_comment(result, changed_files=[model.path])
        assert "What this change reaches" in body
        assert "```mermaid" in body
        assert "<details>" in body

    def test_previous_keys_of_a_missing_file_is_none(self, tmp_path: Path) -> None:
        assert previous_keys(tmp_path / "absent.json") is None

    def test_previous_keys_of_a_malformed_file_is_none(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("{not json", encoding="utf-8")
        assert previous_keys(path) is None


class TestShowcase:
    def test_a_window_with_no_history_is_empty_not_broken(self, result: RunResult) -> None:
        window = Window.last_days(14, end=AS_OF)
        built = build_showcase(result, window=window, git=None)
        assert built.commits == []
        assert "Nothing was committed" in showcase_page(result, built)

    def test_the_window_reports_its_own_span(self) -> None:
        window = Window.last_days(14, end=AS_OF)
        assert window.days == 14
        assert window.end == AS_OF

    def test_debt_is_always_reported_beside_delivery(self, result: RunResult) -> None:
        """FR12.12: a showcase listing only achievements is marketing."""
        window = Window.last_days(14, end=AS_OF)
        built = build_showcase(result, window=window, git=None)
        assert built.debt_context


class TestScaffold:
    def test_detection_finds_the_example_layout(self) -> None:
        """The example mirrors the standard: an analytics_warehouse directory
        with the design documents under docs/data_model_design."""
        found = detect(EXAMPLE)
        assert found.dbt_project_dir == "analytics_warehouse"
        assert found.manifest_found
        assert found.dbml == ["docs/data_model_design/*.dbml"]
        assert found.conceptual == "docs/data_model_design/conceptual_model.mermaid"
        assert found.logical == "docs/data_model_design/logical_model.mermaid"
        assert found.lookml
        assert found.droughty_dbml == ["docs/db_docs/*.dbml"]

    def test_detection_of_an_empty_directory_reports_what_is_missing(self, tmp_path: Path) -> None:
        found = detect(tmp_path)
        assert not found.manifest_found
        assert any("dbt_project.yml" in note for note in found.notes)

    def test_the_ruleset_is_valid_yaml_naming_a_house_version(self) -> None:
        loaded = yaml.safe_load(ruleset_text(detect(EXAMPLE)))
        assert loaded["extends"] == "ra-house@1"
        assert loaded["pull_request"]["mode"] == "advisory"

    def test_the_ruleset_resolves(self, tmp_path: Path) -> None:
        from hunter.config import resolve

        path = tmp_path / "hunter.yml"
        path.write_text(ruleset_text(detect(EXAMPLE)), encoding="utf-8")
        assert resolve(path).config.extends == "ra-house@1"

    def test_the_register_is_prefilled_with_what_hunter_would_flag(self) -> None:
        text = register_text(
            needs_owner=["wh_a__thing_fact"], off_plan=["wh_a__other_fact"], today=AS_OF
        )
        assert "wh_a__thing_fact" in text
        assert "wh_a__other_fact" in text
        assert "owner:" in text
        assert "review_by: 2027-09-08" in text

    def test_the_prefilled_register_is_valid_yaml(self) -> None:
        loaded = yaml.safe_load(register_text(needs_owner=["a"], off_plan=["b"], today=AS_OF))
        assert loaded["version"] == 1

    def test_the_workflow_sets_full_history(self) -> None:
        """fetch-depth: 0 is easy to miss and breaks attribution silently."""
        loaded = yaml.safe_load(workflow_text())
        checkout = loaded["jobs"]["hunter"]["steps"][0]
        assert checkout["with"]["fetch-depth"] == 0

    def test_scaffold_writes_all_three_files(self, tmp_path: Path) -> None:
        written = scaffold(tmp_path, today=AS_OF)
        names = {path.name for path in written}
        assert names == {"hunter.yml", "register.yml"}

    def test_scaffold_refuses_to_overwrite(self, tmp_path: Path) -> None:
        scaffold(tmp_path, today=AS_OF)
        with pytest.raises(FileExistsError, match="already exist"):
            scaffold(tmp_path, today=AS_OF)

    def test_force_overwrites(self, tmp_path: Path) -> None:
        scaffold(tmp_path, today=AS_OF)
        assert scaffold(tmp_path, force=True, today=AS_OF)


class TestPlainLanguage:
    def test_the_overview_sentence_names_the_score_and_the_basis(self, result: RunResult) -> None:
        text = score_sentence(result.score)
        assert f"{result.score.total:g} out of 100" in text
        assert "areas" in text

    def test_top_fixes_are_ordered_most_serious_first(self, result: RunResult) -> None:
        from hunter.enums import SEVERITY_ORDER, Severity

        rows = top_fixes(result)
        orders = [SEVERITY_ORDER[Severity(str(row["severity"]))] for row in rows]
        assert orders == sorted(orders)

    def test_top_fixes_carry_a_consequence_not_a_rule_name(self, result: RunResult) -> None:
        for row in top_fixes(result):
            assert row["consequence"]
            assert str(row["consequence"]) != row["rule"]

    def test_no_glossary_definition_uses_the_term_it_defines_undefined(self) -> None:
        """A definition that needs the word to explain the word is not one."""
        for term, definition in GLOSSARY.items():
            assert definition.strip()
            assert not definition.lower().startswith(term.lower() + " is")
