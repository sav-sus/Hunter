"""The normalised internal model.

Every ingest module writes into these types, and no check ever reads a raw
source. That rule is what makes adding Snowflake or another semantic layer a
change to one file in ``ingest/`` and nothing else. Section 11.3.

Four levels are represented here, and the distinction matters because the
alignment chain compares them:

* ``ConceptualEntity`` -- a business entity, in business language.
* ``DesignedEntity`` -- an authored DBML table: the physical design.
* ``Model`` -- a dbt model: what the repository actually builds.
* warehouse objects -- not modelled at this version, reported as unknown.

Collections are sorted before emitting, per section 11.9. Unsorted dictionary
iteration is the usual cause of non-deterministic output.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from hunter.config.register import Register
from hunter.config.schema import HunterConfig
from hunter.enums import EntityKind, Persistence, PersistenceSignal


class Node(BaseModel):
    """Base for everything Hunter ingests."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Physical: the dbt repository
# ---------------------------------------------------------------------------


class DbtTest(Node):
    """One dbt test, normalised.

    ``kind`` matters more than ``name``. A project can reach the same guarantee
    through several test packages, and the score cares what a test proves, not
    which package it came from.
    """

    unique_id: str
    name: str
    kind: str
    tests_model: str | None = None
    column: str | None = None
    severity: str = "error"
    to_model: str | None = None
    to_field: str | None = None
    file: str | None = None

    @property
    def is_key_test(self) -> bool:
        return self.kind in {"unique", "not_null"}

    @property
    def is_relationship_test(self) -> bool:
        return self.kind == "relationships"

    @property
    def is_weak(self) -> bool:
        """Proves a column is not entirely null. Does not prove a key."""
        return self.kind == "at_least_one"

    @property
    def is_enforced(self) -> bool:
        """A warn-severity test reports but never fails a build."""
        return self.severity == "error"


class Column(Node):
    """One column of a dbt model, as the manifest describes it."""

    name: str
    data_type: str | None = None
    description: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    @property
    def has_description(self) -> bool:
        return bool(self.description and self.description.strip())


class Model(Node):
    """One dbt model.

    ``raw_code`` is excluded from serialisation. It is needed for the structure
    checks and would otherwise put several megabytes of client SQL into
    ``report.json``.
    """

    name: str
    unique_id: str
    path: str
    resource_type: str = "model"

    #: dbt package this model belongs to. Models from an installed package are
    #: vendored code the client did not write and cannot fix, so they are
    #: excluded from scoring. The pilot has 57 of them across three packages.
    package: str | None = None
    vendored: bool = False

    schema_name: str | None = None
    database: str | None = None
    alias: str | None = None
    relation_name: str | None = None
    materialisation: str = "view"
    enabled: bool = True
    description: str | None = None
    columns: list[Column] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
    depends_on_models: list[str] = Field(default_factory=list)
    depends_on_sources: list[str] = Field(default_factory=list)
    raw_code: str = Field(default="", exclude=True)

    # Derived during normalisation
    layer: str | None = None
    domain: str | None = None
    persistence: Persistence = Persistence.UNKNOWN
    persistence_signal: PersistenceSignal = PersistenceSignal.NONE
    entity_kind_declared: EntityKind = EntityKind.UNKNOWN
    entity_kind_inferred: EntityKind = EntityKind.UNKNOWN
    inference_confidence: float = 0.0
    owner: str | None = None
    downstream_models: list[str] = Field(default_factory=list)
    exposure_weight: float = 1.0

    #: The schema.yml that documents this model, from the manifest's
    #: patch_path. Needed to tell whether the documentation has kept up with
    #: the SQL. FR2.5.
    schema_file: str | None = None
    docs_modified_at: dt.date | None = None

    # Git attribution, filled by ingest.git when history is available
    created_by: str | None = None
    created_at: dt.date | None = None
    last_modified_by: str | None = None
    last_modified_at: dt.date | None = None
    created_in_pr: str | None = None

    @property
    def has_description(self) -> bool:
        return bool(self.description and self.description.strip())

    @property
    def is_ephemeral(self) -> bool:
        return self.materialisation == "ephemeral"

    @property
    def is_seed(self) -> bool:
        return self.resource_type == "seed"

    @property
    def is_snapshot(self) -> bool:
        return self.resource_type == "snapshot"

    @property
    def is_sql_model(self) -> bool:
        """A model written in SQL. Seeds are CSV and have no SQL to check."""
        return self.resource_type == "model"

    @property
    def is_scoreable(self) -> bool:
        """Whether findings on this model should affect the score."""
        return not self.vendored

    @property
    def is_temporary(self) -> bool:
        return self.persistence is Persistence.TEMPORARY

    @property
    def is_lasting(self) -> bool:
        """Permanent or verified. Judged as a finished table either way."""
        return self.persistence.is_lasting

    @property
    def is_verified(self) -> bool:
        return self.persistence is Persistence.VERIFIED

    @property
    def downstream_count(self) -> int:
        return len(self.downstream_models)

    def column(self, name: str) -> Column | None:
        lowered = name.lower()
        for column in self.columns:
            if column.name.lower() == lowered:
                return column
        return None

    def column_names(self) -> set[str]:
        return {column.name.lower() for column in self.columns}


class Source(Node):
    """One dbt source table."""

    name: str
    unique_id: str
    source_name: str
    schema_name: str | None = None
    database: str | None = None
    description: str | None = None
    columns: list[Column] = Field(default_factory=list)
    relation_name: str | None = None


class Exposure(Node):
    """One dbt exposure: a declared downstream consumer."""

    name: str
    unique_id: str
    exposure_type: str | None = None
    owner: str | None = None
    depends_on_models: list[str] = Field(default_factory=list)
    url: str | None = None


# ---------------------------------------------------------------------------
# Design: authored DBML
# ---------------------------------------------------------------------------


class DesignedColumn(Node):
    """One column of an authored DBML table."""

    name: str
    data_type: str | None = None
    note: str | None = None
    is_primary_key: bool = False
    is_unique: bool = False
    is_not_null: bool = False

    @property
    def has_note(self) -> bool:
        return bool(self.note and self.note.strip())


class DesignedRef(Node):
    """One relationship declared in DBML."""

    from_table: str
    from_columns: list[str]
    to_table: str
    to_columns: list[str]
    cardinality: str | None = None

    @property
    def key(self) -> str:
        return (
            f"{self.from_table}.{'+'.join(self.from_columns)}"
            f"->{self.to_table}.{'+'.join(self.to_columns)}"
        )


class DesignedEntity(Node):
    """One authored DBML table: the design, not the build."""

    name: str
    columns: list[DesignedColumn] = Field(default_factory=list)
    note: str | None = None
    grain_note: str | None = None
    domain: str | None = None
    source_file: str | None = None
    file_modified_at: dt.date | None = None

    @property
    def primary_key_columns(self) -> list[str]:
        return [column.name for column in self.columns if column.is_primary_key]

    @property
    def has_primary_key(self) -> bool:
        return bool(self.primary_key_columns)

    @property
    def entity_kind_declared(self) -> EntityKind:
        return EntityKind.UNKNOWN

    def column(self, name: str) -> DesignedColumn | None:
        lowered = name.lower()
        for column in self.columns:
            if column.name.lower() == lowered:
                return column
        return None

    def column_names(self) -> set[str]:
        return {column.name.lower() for column in self.columns}


# ---------------------------------------------------------------------------
# Conceptual: the business model
# ---------------------------------------------------------------------------


class ConceptualEntity(Node):
    """One business entity.

    ``claimed_status`` is what the authored diagram says. Hunter never treats it
    as truth: the diagram is hand-maintained and drifts, so the alignment check
    compares this claim against computed reality and reports the gap.
    """

    name: str
    business_name: str | None = None
    domain: str | None = None
    note: str | None = None
    claimed_status: str | None = None
    source_file: str | None = None

    @property
    def label(self) -> str:
        return self.business_name or self.name.replace("_", " ")


# ---------------------------------------------------------------------------
# Semantic layer: LookML
# ---------------------------------------------------------------------------


class LookmlField(Node):
    """One LookML dimension, dimension group or measure."""

    name: str
    view: str
    field_type: str
    lookml_type: str | None = None
    sql: str | None = None
    label: str | None = None
    description: str | None = None
    hidden: bool = False
    referenced_columns: list[str] = Field(default_factory=list)
    file: str | None = None

    @property
    def qualified_name(self) -> str:
        return f"{self.view}.{self.name}"

    @property
    def is_measure(self) -> bool:
        return self.field_type == "measure"


class LookmlView(Node):
    """One LookML view."""

    name: str
    sql_table_name: str | None = None
    is_derived_table: bool = False
    extends: list[str] = Field(default_factory=list)
    fields: list[LookmlField] = Field(default_factory=list)
    file: str | None = None

    #: Files carrying ``view: +name`` refinements of this view. Looker layers
    #: definitions this way, and the pilot uses it heavily: generated base views
    #: are refined with hand-written measures. A reader that treats a refinement
    #: as a redefinition misattributes every field in it.
    refined_by: list[str] = Field(default_factory=list)

    # Derived during normalisation
    model_name: str | None = None

    @property
    def measures(self) -> list[LookmlField]:
        return [field for field in self.fields if field.is_measure]


class ExploreJoin(Node):
    name: str
    relationship: str | None = None
    join_type: str | None = None
    sql_on: str | None = None


class Explore(Node):
    """One LookML explore."""

    name: str
    view_name: str | None = None
    label: str | None = None
    datagroup: str | None = None
    persist_for: str | None = None
    joins: list[ExploreJoin] = Field(default_factory=list)
    file: str | None = None

    @property
    def has_caching_policy(self) -> bool:
        return bool(self.datagroup or self.persist_for)

    def joined_views(self) -> list[str]:
        return [join.name for join in self.joins]


# ---------------------------------------------------------------------------
# Droughty artifacts
# ---------------------------------------------------------------------------


class DroughtyTestSpec(Node):
    """One test Droughty says should exist."""

    model: str
    column: str
    test_name: str
    kind: str


class DroughtyArtifacts(Node):
    """Committed Droughty output, read from files.

    Live introspection against the warehouse needs credentials and is milestone
    M1. This is the half that needs none, and it is the useful half.
    """

    project_file: str | None = None
    schema_file: str | None = None
    schema_modified_at: dt.date | None = None
    generated_tests: list[DroughtyTestSpec] = Field(default_factory=list)
    generated_descriptions: dict[str, list[str]] = Field(default_factory=dict)
    doc_refs: list[str] = Field(default_factory=list)
    doc_blocks_defined: list[str] = Field(default_factory=list)
    doc_blocks_empty: list[str] = Field(default_factory=list)
    test_ignore_models: list[str] = Field(default_factory=list)
    test_overrides: list[DroughtyTestSpec] = Field(default_factory=list)
    introspected: dict[str, DesignedEntity] = Field(default_factory=dict)

    @property
    def covered_models(self) -> set[str]:
        return {spec.model for spec in self.generated_tests}


# ---------------------------------------------------------------------------
# Parse problems
# ---------------------------------------------------------------------------


class ParseIssue(Node):
    """Something Hunter could not read.

    Carried through to the findings rather than raised, so one malformed block
    degrades one table instead of killing a whole score dimension. The pilot's
    main design file fails to parse as-is, which is why this exists.
    """

    source: str
    subject: str | None = None
    message: str
    line: int | None = None
    recoverable: bool = True


# ---------------------------------------------------------------------------
# The whole normalised world
# ---------------------------------------------------------------------------


class Project(Node):
    """Everything Hunter ingested, normalised and cross-referenced."""

    #: Layers found in the models directory that the ruleset did not declare.
    #: Names only; the specs themselves are appended to the resolved config.
    discovered_layers: list[str] = Field(default_factory=list)

    models: dict[str, Model] = Field(default_factory=dict)
    sources: dict[str, Source] = Field(default_factory=dict)
    exposures: list[Exposure] = Field(default_factory=list)
    tests: list[DbtTest] = Field(default_factory=list)
    disabled_models: dict[str, Model] = Field(default_factory=dict)
    designed: dict[str, DesignedEntity] = Field(default_factory=dict)
    designed_refs: list[DesignedRef] = Field(default_factory=list)
    conceptual: dict[str, ConceptualEntity] = Field(default_factory=dict)
    lookml_views: dict[str, LookmlView] = Field(default_factory=dict)
    explores: dict[str, Explore] = Field(default_factory=dict)
    droughty: DroughtyArtifacts | None = None
    parse_issues: list[ParseIssue] = Field(default_factory=list)

    # What was available this run. Drives weight renormalisation, so a score is
    # never quietly computed on a smaller basis than the reader assumes.
    has_manifest: bool = False
    has_dbml: bool = False
    has_conceptual: bool = False
    has_lookml: bool = False
    has_droughty: bool = False
    has_warehouse: bool = False
    has_git: bool = False

    # ---- lookups ----

    def model(self, name: str) -> Model | None:
        return self.models.get(name)

    def any_model(self, name: str) -> Model | None:
        """Enabled or disabled. Both exist in the repository."""
        return self.models.get(name) or self.disabled_models.get(name)

    def model_names(self) -> set[str]:
        return set(self.models) | set(self.disabled_models)

    def tests_for(self, model_name: str) -> list[DbtTest]:
        return [test for test in self.tests if test.tests_model == model_name]

    def tests_for_column(self, model_name: str, column: str) -> list[DbtTest]:
        lowered = column.lower()
        return [
            test
            for test in self.tests_for(model_name)
            if test.column and test.column.lower() == lowered
        ]

    def models_in_layer(self, layer: str) -> list[Model]:
        return sorted(
            (model for model in self.models.values() if model.layer == layer),
            key=lambda model: model.name,
        )

    def views_for_model(self, model_name: str) -> list[LookmlView]:
        return sorted(
            (view for view in self.lookml_views.values() if view.model_name == model_name),
            key=lambda view: view.name,
        )

    def sorted_models(self) -> list[Model]:
        return [self.models[name] for name in sorted(self.models)]

    def sorted_designed(self) -> list[DesignedEntity]:
        return [self.designed[name] for name in sorted(self.designed)]

    def refs_from(self, table: str) -> list[DesignedRef]:
        return [ref for ref in self.designed_refs if ref.from_table == table]

    def has_column_types(self) -> bool:
        """Whether enough column types are known to compare them.

        Types come from ``catalog.json``, not the manifest. Where they are
        absent the type comparison reports that it could not run, rather than
        reporting no drift.
        """
        total = sum(len(model.columns) for model in self.models.values())
        typed = sum(
            1 for model in self.models.values() for column in model.columns if column.data_type
        )
        return total > 0 and typed >= total * 0.5


# ---------------------------------------------------------------------------
# Derived classification
# ---------------------------------------------------------------------------

#: Matches the grain sentence the pilot writes into DBML table notes, e.g.
#: "Table Grain: One row per unique session."
GRAIN_NOTE_PATTERN = re.compile(r"(?:table\s+)?grain\s*[:\-]\s*(?P<grain>[^\n]+)", re.IGNORECASE)


def extract_grain(note: str | None) -> str | None:
    """Pull a plain-English grain sentence out of a DBML note."""
    if not note:
        return None
    match = GRAIN_NOTE_PATTERN.search(note)
    if not match:
        return None
    grain = match.group("grain").strip().rstrip(".")
    return grain or None


def domain_of(model_name: str, layer_prefix: str | None = None) -> str | None:
    """Domain implied by a name like ``wh_commerce__store_dim`` -> ``commerce``.

    The convention is ``<layer><domain>__<entity>``. Returns None where the name
    does not follow it, rather than guessing.
    """
    if "__" not in model_name:
        return None
    head = model_name.split("__", 1)[0]
    if layer_prefix and head.startswith(layer_prefix):
        head = head[len(layer_prefix) :]
    return head or None


def classify_persistence(
    model: Model,
    config: HunterConfig,
    register: Register,
    *,
    downstream_count: int | None = None,
    warehouse_expires: bool | None = None,
) -> tuple[Persistence, PersistenceSignal]:
    """Decide whether a model is meant to last, and say which signal decided it.

    FR1.2 sets the precedence. FR1.3 requires reporting the deciding signal, so
    this returns both rather than just the answer.

    The register comes first, ahead of the requirements document's order. A
    person stating intent outranks anything Hunter can infer, and the
    declaration costs them a written reason.
    """
    declared = register.declared_persistence(model.name)
    if declared is not None:
        return declared, PersistenceSignal.REGISTER

    if warehouse_expires is True:
        return Persistence.TEMPORARY, PersistenceSignal.TABLE_EXPIRATION

    if model.is_ephemeral:
        return Persistence.TEMPORARY, PersistenceSignal.EPHEMERAL

    if model.layer:
        layer = config.layer(model.layer)
        if layer is not None and layer.persistence is not Persistence.UNKNOWN:
            return layer.persistence, PersistenceSignal.LAYER

    if model.materialisation in {"table", "incremental"}:
        return Persistence.PERSISTENT, PersistenceSignal.MATERIALISATION
    if model.materialisation == "view":
        count = downstream_count if downstream_count is not None else model.downstream_count
        if count == 0:
            return Persistence.TEMPORARY, PersistenceSignal.DOWNSTREAM_COUNT
        return Persistence.TEMPORARY, PersistenceSignal.MATERIALISATION

    return Persistence.UNKNOWN, PersistenceSignal.NONE
