"""Reading committed Droughty output, with no warehouse credential."""

from __future__ import annotations

from pathlib import Path

from hunter.ingest.droughty import (
    dropped_overrides,
    load_droughty,
    missing_doc_blocks,
    orphan_doc_blocks,
    parse_field_descriptions,
    parse_generated_schema,
    parse_project_file,
)

PROJECT_FILE = """
profile: warehouse
dbt_path: dbt/models/
dbml_path: dbt/docs/db_docs/
field_description_path: dbt/models
field_description_file_name: field_descriptions.md
dbt_tests_filename: droughty_schema
lookml_path: dbt/lookml/base/

test_overwrite:
  models:
    wh_sales__order_fact:
      order_pk:
        - not_null
        - unique
      customer_fk:
        - not_null
        - relationships:
            to: ref('wh_sales__customer_dim')
            field: customer_pk
    wh_sales__customer_dim:
      customer_status:
        - accepted_values:
            values: ['active', 'closed']

test_ignore:
  models:
    - stg_legacy__events
    - stg_broken__ledger
"""

GENERATED_SCHEMA = """
version: 2
models:
  - name: wh_sales__order_fact
    columns:
      - name: order_pk
        description: '{{doc("order_pk")}}'
        tests:
          - not_null
          - unique
      - name: customer_fk
        description: '{{doc("customer_fk")}}'
        tests:
          - not_null
          - relationships:
              to: ref('wh_sales__customer_dim')
              field: customer_pk
      - name: order_amount
        description: '{{doc("order_amount")}}'
        tests:
          - dbt_utils.at_least_one
  - name: wh_sales__customer_dim
    columns:
      - name: customer_pk
        description: '{{doc("customer_pk")}}'
        tests:
          - not_null
          - unique
      - name: customer_status
        description: '{{doc("customer_status")}}'
        tests:
          - accepted_values:
              values: ['active', 'closed']
"""

FIELD_DESCRIPTIONS = """
{% docs order_pk %}
Surrogate key for the order.
{% enddocs %}

{% docs customer_fk %}
Reference to the customer.
{% enddocs %}

{% docs order_amount %}
Order value, net of returns.
{% enddocs %}

{% docs customer_pk %}
Surrogate key for the customer.
{% enddocs %}

{% docs customer_status %}
{% enddocs %}

{% docs never_referenced %}
A description nothing uses any more.
{% enddocs %}
"""


def build_project(tmp_path: Path, *, schema: str = GENERATED_SCHEMA) -> Path:
    """A miniature repository laid out the way Droughty expects."""
    root = tmp_path
    (root / "dbt" / "models").mkdir(parents=True)
    (root / "dbt" / "docs" / "db_docs").mkdir(parents=True)
    (root / "dbt" / "droughty_project.yaml").write_text(PROJECT_FILE, encoding="utf-8")
    (root / "dbt" / "models" / "droughty_schema.yml").write_text(schema, encoding="utf-8")
    (root / "dbt" / "models" / "field_descriptions.md").write_text(
        FIELD_DESCRIPTIONS, encoding="utf-8"
    )
    (root / "dbt" / "docs" / "db_docs" / "warehouse.dbml").write_text(
        "table wh_sales__order_fact {\n  order_pk varchar [pk]\n  order_amount numeric\n}\n",
        encoding="utf-8",
    )
    return root


class TestProjectFile:
    def test_paths_are_read(self, tmp_path: Path) -> None:
        path = tmp_path / "droughty_project.yaml"
        path.write_text(PROJECT_FILE, encoding="utf-8")
        paths, _, _, issues = parse_project_file(path)
        assert paths.dbt_tests_filename == "droughty_schema"
        assert paths.field_description_file_name == "field_descriptions.md"
        assert issues == []

    def test_hand_authored_overrides_are_read(self, tmp_path: Path) -> None:
        path = tmp_path / "droughty_project.yaml"
        path.write_text(PROJECT_FILE, encoding="utf-8")
        _, overrides, _, _ = parse_project_file(path)
        assert len(overrides) == 5
        names = {(spec.model, spec.column, spec.test_name) for spec in overrides}
        assert ("wh_sales__order_fact", "order_pk", "unique") in names
        assert ("wh_sales__order_fact", "customer_fk", "relationships") in names

    def test_excluded_models_are_read_as_authored_intent(self, tmp_path: Path) -> None:
        """Hunter must not re-report a decision the team already recorded."""
        path = tmp_path / "droughty_project.yaml"
        path.write_text(PROJECT_FILE, encoding="utf-8")
        _, _, ignored, _ = parse_project_file(path)
        assert ignored == ["stg_broken__ledger", "stg_legacy__events"]

    def test_malformed_yaml_is_reported_not_raised(self, tmp_path: Path) -> None:
        path = tmp_path / "droughty_project.yaml"
        path.write_text("test_overwrite: [unclosed", encoding="utf-8")
        _, overrides, _, issues = parse_project_file(path)
        assert overrides == []
        assert len(issues) == 1
        assert issues[0].recoverable


class TestGeneratedSchema:
    def test_tests_are_normalised_by_what_they_prove(self, tmp_path: Path) -> None:
        path = tmp_path / "droughty_schema.yml"
        path.write_text(GENERATED_SCHEMA, encoding="utf-8")
        specs, _, _, _ = parse_generated_schema(path)
        kinds = {(spec.model, spec.column, spec.kind) for spec in specs}
        assert ("wh_sales__order_fact", "order_pk", "unique") in kinds
        # dbt_utils.at_least_one and a bare at_least_one normalise the same way
        assert ("wh_sales__order_fact", "order_amount", "at_least_one") in kinds

    def test_doc_references_are_collected(self, tmp_path: Path) -> None:
        path = tmp_path / "droughty_schema.yml"
        path.write_text(GENERATED_SCHEMA, encoding="utf-8")
        _, _, refs, _ = parse_generated_schema(path)
        assert "order_pk" in refs
        assert "customer_status" in refs

    def test_models_covered_are_listed(self, tmp_path: Path) -> None:
        path = tmp_path / "droughty_schema.yml"
        path.write_text(GENERATED_SCHEMA, encoding="utf-8")
        specs, descriptions, _, _ = parse_generated_schema(path)
        assert {spec.model for spec in specs} == {
            "wh_sales__order_fact",
            "wh_sales__customer_dim",
        }
        assert "order_pk" in descriptions["wh_sales__order_fact"]


class TestFieldDescriptions:
    def test_blocks_are_found(self, tmp_path: Path) -> None:
        path = tmp_path / "field_descriptions.md"
        path.write_text(FIELD_DESCRIPTIONS, encoding="utf-8")
        defined, _empty, _ = parse_field_descriptions(path)
        assert "order_pk" in defined
        assert "never_referenced" in defined

    def test_an_empty_block_is_flagged(self, tmp_path: Path) -> None:
        path = tmp_path / "field_descriptions.md"
        path.write_text(FIELD_DESCRIPTIONS, encoding="utf-8")
        _, empty, _ = parse_field_descriptions(path)
        assert empty == ["customer_status"]

    def test_a_missing_file_is_reported_not_raised(self, tmp_path: Path) -> None:
        defined, _empty, issues = parse_field_descriptions(tmp_path / "absent.md")
        assert defined == []
        assert len(issues) == 1


class TestLoadDroughty:
    def test_declared_paths_resolve_from_the_repository_root(self, tmp_path: Path) -> None:
        """Droughty's paths are repo-relative while its config sits below the
        root, so resolution has to try more than one base."""
        root = build_project(tmp_path)
        data = load_droughty(root / "dbt", repo_root=root)

        assert data.found_any
        assert data.issues == []
        assert len(data.artifacts.generated_tests) == 8
        assert len(data.artifacts.test_overrides) == 5
        assert len(data.artifacts.introspected) == 1

    def test_a_repository_with_no_droughty_output_is_not_an_error(self, tmp_path: Path) -> None:
        data = load_droughty(tmp_path)
        assert not data.found_any
        assert data.issues == []
        assert data.artifacts.generated_tests == []

    def test_orphan_descriptions_are_found(self, tmp_path: Path) -> None:
        root = build_project(tmp_path)
        artifacts = load_droughty(root / "dbt", repo_root=root).artifacts
        assert orphan_doc_blocks(artifacts) == ["never_referenced"]

    def test_missing_descriptions_are_found(self, tmp_path: Path) -> None:
        schema = (
            GENERATED_SCHEMA
            + """
      - name: order_channel
        description: '{{doc("order_channel")}}'
        tests:
          - not_null
"""
        )
        root = build_project(tmp_path, schema=schema)
        artifacts = load_droughty(root / "dbt", repo_root=root).artifacts
        assert missing_doc_blocks(artifacts) == ["order_channel"]

    def test_empty_descriptions_are_carried_through(self, tmp_path: Path) -> None:
        root = build_project(tmp_path)
        artifacts = load_droughty(root / "dbt", repo_root=root).artifacts
        assert artifacts.doc_blocks_empty == ["customer_status"]


class TestDroppedOverrides:
    """The check that replaces the pilot team's manual verification.

    Droughty has silently applied only the first override per model and dropped
    the rest, so their config carries a note telling whoever regenerates it to
    hand-check the result.
    """

    def test_a_clean_regeneration_reports_nothing(self, tmp_path: Path) -> None:
        root = build_project(tmp_path)
        artifacts = load_droughty(root / "dbt", repo_root=root).artifacts
        assert dropped_overrides(artifacts) == []

    def test_an_override_that_never_landed_is_found(self, tmp_path: Path) -> None:
        """Remove the second override on a model, as the known bug would."""
        schema = GENERATED_SCHEMA.replace(
            "        tests:\n          - not_null\n          - unique\n",
            "        tests:\n          - not_null\n",
            1,
        )
        root = build_project(tmp_path, schema=schema)
        artifacts = load_droughty(root / "dbt", repo_root=root).artifacts

        dropped = dropped_overrides(artifacts)
        assert [(spec.model, spec.column, spec.test_name) for spec in dropped] == [
            ("wh_sales__order_fact", "order_pk", "unique")
        ]

    def test_no_generated_schema_means_no_false_alarm(self, tmp_path: Path) -> None:
        """With the schema unread, every override would look dropped. The
        missing file is the finding, not 168 phantom ones."""
        root = tmp_path
        (root / "dbt").mkdir()
        (root / "dbt" / "droughty_project.yaml").write_text(PROJECT_FILE, encoding="utf-8")
        artifacts = load_droughty(root / "dbt", repo_root=root).artifacts
        assert artifacts.test_overrides
        assert dropped_overrides(artifacts) == []
