"""Pydantic models for ``hunter.yml`` and the house ruleset.

Section 7 of the requirements document. NFR6 requires the whole ruleset to be
declared here with no hidden thresholds, so every number a check uses is a field
on one of these models rather than a constant in a check module.
"""

from __future__ import annotations

import datetime as dt
import fnmatch
from typing import Annotated, Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from hunter.enums import (
    Dimension,
    EntityKind,
    Persistence,
    PrMode,
    ReportMode,
    Severity,
)

WEIGHT_TOTAL = 100.0
WEIGHT_TOLERANCE = 0.01


class Strict(BaseModel):
    """Base for config models. Unknown keys are an error, not a shrug.

    A typo in a client's ``hunter.yml`` must not silently disable a rule.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class LayerSpec(Strict):
    """One layer of the project, and what is allowed in it."""

    name: str
    paths: list[str] = Field(default_factory=list, description="Glob patterns under the models dir")
    prefix: str | None = Field(default=None, description="Required filename and model-name prefix")
    materialisations: list[str] = Field(
        default_factory=list,
        description="Permitted materialisations. Empty means any.",
    )
    persistence: Persistence = Persistence.UNKNOWN
    may_reference: list[str] = Field(
        default_factory=list,
        description="Layer names this layer may depend on. Empty means any.",
    )
    may_reference_sources: bool = True
    requires_model_description: bool = False
    requires_column_descriptions: bool = False
    requires_owner: bool = False
    requires_key_tests: bool = Field(
        default=False,
        description="Primary key must carry both a uniqueness and a not-null test",
    )
    expected_entity_kinds: list[EntityKind] = Field(default_factory=list)

    #: Where this layer sits in the pipeline. Declaration order is not
    #: pipeline order, and using it as a proxy produced findings like "skips
    #: the seeds layer to read a warehouse table". Declared explicitly, per
    #: NFR6. Layers sharing a stage are siblings and neither bypasses the
    #: other; 0 means the layer is not part of the flow.
    pipeline_stage: int = 0

    #: True when Hunter found this layer in the models directory rather than
    #: reading it from a ruleset. A discovered layer carries no requirements:
    #: Hunter knows the models are grouped, not what the group should look
    #: like. The report names every discovered layer so it can be declared.
    discovered: bool = False

    #: Whether models in this layer are modelled entities that belong in the
    #: alignment chain. Staging and integration models are working steps, not
    #: entities: counting them would report 129 staging models as built
    #: off-plan, which is not a finding anyone can act on. Declared explicitly
    #: rather than inferred, per NFR6.
    in_alignment: bool = False

    def matches_path(self, path: str) -> bool:
        return any(fnmatch.fnmatch(path, pattern) for pattern in self.paths)


class EntitySpec(Strict):
    """Expected shape for one entity kind. FR3.2, FR3.3."""

    kind: EntityKind
    suffix: str
    requires_surrogate_key: bool = True
    requires_unique_test: bool = True
    requires_not_null_key_test: bool = True
    expects_measures: bool = False
    expects_date_grain: bool = False
    expects_foreign_keys: bool = False
    min_descriptive_attributes: int = 0


class ColumnNamingSpec(Strict):
    """Column suffix conventions. FR2.1, FR16.8."""

    primary_key_suffix: str = "_pk"
    foreign_key_suffix: str = "_fk"
    natural_key_suffix: str = "_natural_key"
    date_suffix: str = "_dt"
    timestamp_suffix: str = "_ts"
    boolean_prefixes: list[str] = Field(default_factory=lambda: ["is_", "has_"])
    boolean_suffixes: list[str] = Field(default_factory=lambda: ["_flag"])
    #: Timestamps outside UTC must name their zone, e.g. created_cet_ts
    require_timezone_in_non_utc_timestamps: bool = True


class StructureSpec(Strict):
    """SQL structure ceilings. FR2.6."""

    max_model_lines: int = 300
    max_joins: int = 7
    forbid_select_star: bool = True
    forbid_hardcoded_refs: bool = True
    require_cte_naming_pattern: str | None = None
    cte_name_pattern: str = r"^[a-z][a-z0-9_]*$"


class LineageSpec(Strict):
    """Lineage anti-pattern thresholds. FR5.3."""

    max_fanout: int = 12
    flag_dead_models: bool = True
    flag_direct_source_joins_outside_staging: bool = True
    flag_staging_bypass: bool = True
    flag_model_rejoins: bool = True


class DocumentationSpec(Strict):
    """Documentation expectations. FR2.4, FR2.5."""

    #: Applies to table descriptions. Columns are held to the placeholder list
    #: only: "Order date" is a useful column description and a poor table one.
    min_description_words: int = 3
    min_column_description_words: int = 1
    placeholder_patterns: list[str] = Field(
        default_factory=lambda: [
            "tbd",
            "todo",
            "fixme",
            "n/a",
            "na",
            "none",
            "description",
            "no description",
            "placeholder",
            "xxx",
            "?",
        ]
    )
    require_owner_in_meta: bool = True
    owner_meta_keys: list[str] = Field(default_factory=lambda: ["owner", "team"])
    stale_after_days: int = 180
    flag_stale_descriptions: bool = True


class TestingSpec(Strict):
    """What counts as a test, and what does not. F7."""

    #: Tests that prove a key. Anything else is coverage, not key cover.
    key_test_names: list[str] = Field(default_factory=lambda: ["unique", "not_null"])
    relationship_test_names: list[str] = Field(default_factory=lambda: ["relationships"])
    #: Present in the pilot 3,492 times. Counted, never credited as key cover.
    weak_test_names: list[str] = Field(
        default_factory=lambda: ["at_least_one", "dbt_utils.at_least_one"]
    )
    require_relationship_test_per_foreign_key: bool = True
    require_unique_test_on_declared_grain: bool = True


class EntityInferenceSpec(Strict):
    """Thresholds for behavioural entity inference. FR3.1, FR3.6."""

    min_confidence_to_score: float = Field(default=0.7, ge=0.0, le=1.0)
    fact_min_foreign_keys: int = 2
    fact_min_measures: int = 1
    dimension_max_foreign_keys: int = 1
    dimension_min_attributes: int = 3
    aggregate_min_measures: int = 2


class DroughtySpec(Strict):
    """Droughty comparison settings. FR4.6, section 16.6."""

    enabled: bool = True
    #: Read from files only. Live regeneration is milestone M1.
    run_introspection: bool = False
    command: str = "droughty"
    stale_after_days: int = 30
    flag_orphan_descriptions: bool = True
    flag_dropped_overrides: bool = True


class CrossLayerSpec(Strict):
    """dbt against LookML expectations. F4."""

    flag_duplicate_measures: bool = True
    #: Report warehouse tables that LookML reads with no dbt exposure declared.
    #: It reports; it writes nothing. The old name, generate_missing_exposures,
    #: is still accepted so an existing hunter.yml keeps loading.
    report_missing_exposures: bool = Field(
        default=True,
        validation_alias=AliasChoices("report_missing_exposures", "generate_missing_exposures"),
    )

    @model_validator(mode="before")
    @classmethod
    def _retired_switch_names_its_replacement(cls, data: object) -> object:
        if isinstance(data, dict) and "require_datagroup_on_explores" in data:
            raise ValueError(
                "cross_layer.require_datagroup_on_explores was removed. It switched off "
                "one rule silently. Do it under rules instead, with a reason:\n"
                "  rules:\n"
                "    crosslayer.explore_no_caching_policy:\n"
                "      enabled: false\n"
                "      reason: <why this repository does not use datagroups>"
            )
        return data

    #: v1 records derived tables and skips them, per risk 6.
    skip_derived_tables: bool = True


class ScoringSpec(Strict):
    """Weights and thresholds. Section 9, FR7."""

    weights: dict[Dimension, float]
    exposure_weighting: bool = True
    exposure_weight_cap: float = Field(
        default=3.0,
        ge=1.0,
        description="Most a single finding's points can be multiplied by",
    )
    fail_under: int | None = None
    fail_on_regression: bool = False
    #: Findings below this confidence never affect the score. FR3.6.
    min_confidence_to_score: float = Field(default=0.7, ge=0.0, le=1.0)

    @field_validator("weights")
    @classmethod
    def _weights_complete_and_total_100(
        cls, value: dict[Dimension, float]
    ) -> dict[Dimension, float]:
        missing = set(Dimension) - set(value)
        if missing:
            names = ", ".join(sorted(str(d) for d in missing))
            raise ValueError(f"no weight given for: {names}")
        if any(weight < 0 for weight in value.values()):
            raise ValueError("weights cannot be negative")
        total = sum(value.values())
        if abs(total - WEIGHT_TOTAL) > WEIGHT_TOLERANCE:
            raise ValueError(f"weights must total {WEIGHT_TOTAL:g}, got {total:g}")
        return value


class RuleSetting(Strict):
    """Per-rule override. Lets a project turn a rule off or change its cost."""

    enabled: bool = True
    severity: Severity | None = None
    points: float | None = Field(default=None, ge=0.0)
    reason: str | None = None

    @model_validator(mode="after")
    def _disabling_needs_a_reason(self) -> RuleSetting:
        if not self.enabled and not (self.reason and self.reason.strip()):
            raise ValueError("disabling a rule requires a reason")
        return self


class IgnoreRule(Strict):
    """A silenced rule, for named models, with a reason and an end date.

    Section 7.1 makes reason and expiry mandatory. FR8.5 re-raises the finding
    once the expiry passes, which is what stops this becoming a place debt
    hides.
    """

    rule: str
    models: list[str] = Field(default_factory=lambda: ["*"])
    reason: str
    expires: dt.date

    @field_validator("reason")
    @classmethod
    def _reason_is_real(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 10:
            raise ValueError("reason must be a real sentence, at least 10 characters")
        return cleaned

    def covers(self, rule_id: str, model_name: str) -> bool:
        if self.rule != rule_id and not fnmatch.fnmatch(rule_id, self.rule):
            return False
        return any(fnmatch.fnmatch(model_name, pattern) for pattern in self.models)

    def is_expired(self, as_of: dt.date) -> bool:
        return as_of > self.expires


class PathsSpec(Strict):
    """Where things are. Configurable because no two clients agree. 16.2."""

    project_root: str = "."
    dbt_project_dir: str = "."
    manifest: str = "target/manifest.json"
    models_dir: str = "models"
    dbml: list[str] = Field(default_factory=lambda: ["models/_model/*.dbml"])
    conceptual_diagram: str | None = None
    logical_diagram: str | None = None
    lookml: list[str] = Field(default_factory=list)
    droughty_project: str | None = None
    droughty_schema: str | None = None
    field_descriptions: str | None = None
    droughty_dbml: list[str] = Field(default_factory=list)
    # Named with the _file suffix because a bare "register" shadows an
    # attribute on pydantic's BaseModel.
    register_file: str = ".hunter/register.yml"
    baseline: str = ".hunter/baseline.json"
    output_dir: str = "out"


class BigQuerySpec(Strict):
    """Read-only warehouse metadata. Optional, and unused in M0.

    A list of projects, not one, because the pilot's models span two. 16.1.
    """

    enabled: bool = False
    projects: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    job_history_days: int = 30


class JiraSpec(Strict):
    """Sprint boundaries for the showcase window. 16.9."""

    enabled: bool = False
    cloud_id: str | None = None
    board_id: str | None = None
    ticket_pattern: str = r"[A-Z]+-[0-9]+"
    #: Used when Jira is unavailable or sprint dates are unset.
    fallback_anchor_date: dt.date | None = None
    fallback_window_days: int = 14


class IntegrationsSpec(Strict):
    droughty: DroughtySpec = Field(default_factory=DroughtySpec)
    bigquery: BigQuerySpec = Field(default_factory=BigQuerySpec)
    jira: JiraSpec = Field(default_factory=JiraSpec)


class BrandingSpec(Strict):
    """F13. Assets ship in the package and are never fetched at build time."""

    theme: str = "rittman-analytics"
    report_mode: ReportMode = ReportMode.INTERNAL
    site_name: str = "Repository health"
    client_name: str | None = None
    client_logo: str | None = None
    attribution: str = "Generated by Rittman Hunter, from Rittman Analytics"
    #: A public URL for the Rittman Analytics logo, shown at the top of the
    #: pull request comment and the sync summaries. GitHub renders images in
    #: comments only from URLs it can reach, so this is opt-in: a private
    #: repository's raw file URL would show a broken image. The published
    #: documentation site is the usual place to serve it from.
    logo_url: str | None = None


class PrSpec(Strict):
    """F11. Advisory on first installation, per FR11.7."""

    mode: PrMode = PrMode.ADVISORY
    new_violations_only: bool = True
    include_blast_radius: bool = True
    include_subgraph: bool = True
    collapse_subgraph: bool = True
    max_findings_shown: int = 20


class HunterConfig(Strict):
    """The whole resolved ruleset.

    Built by ``config.loader.resolve``, which merges the built-in defaults, the
    house ruleset, the project file and any per-model overrides. Nothing
    constructs this directly except the loader and tests.
    """

    extends: str | None = Field(default=None, description="House ruleset, e.g. ra-house@1")
    house_version: str = "unknown"
    layers: list[LayerSpec] = Field(default_factory=list)
    entities: list[EntitySpec] = Field(default_factory=list)
    column_naming: ColumnNamingSpec = Field(default_factory=ColumnNamingSpec)
    structure: StructureSpec = Field(default_factory=StructureSpec)
    lineage: LineageSpec = Field(default_factory=LineageSpec)
    documentation: DocumentationSpec = Field(default_factory=DocumentationSpec)
    testing: TestingSpec = Field(default_factory=TestingSpec)
    entity_inference: EntityInferenceSpec = Field(default_factory=EntityInferenceSpec)
    cross_layer: CrossLayerSpec = Field(default_factory=CrossLayerSpec)
    scoring: ScoringSpec
    rules: dict[str, RuleSetting] = Field(default_factory=dict)
    ignores: list[IgnoreRule] = Field(default_factory=list)
    paths: PathsSpec = Field(default_factory=PathsSpec)
    integrations: IntegrationsSpec = Field(default_factory=IntegrationsSpec)
    branding: BrandingSpec = Field(default_factory=BrandingSpec)
    pull_request: PrSpec = Field(default_factory=PrSpec)

    @model_validator(mode="after")
    def _references_name_known_layers(self) -> HunterConfig:
        known = {layer.name for layer in self.layers}
        for layer in self.layers:
            unknown = [name for name in layer.may_reference if name not in known]
            if unknown:
                raise ValueError(
                    f"layer {layer.name!r} may_reference names unknown layers: "
                    f"{', '.join(sorted(unknown))}"
                )
        return self

    @model_validator(mode="after")
    def _entity_suffixes_are_unique(self) -> HunterConfig:
        seen: dict[str, EntityKind] = {}
        for spec in self.entities:
            if spec.suffix in seen:
                raise ValueError(
                    f"suffix {spec.suffix!r} claimed by both {seen[spec.suffix]} and {spec.kind}"
                )
            seen[spec.suffix] = spec.kind
        return self

    # ---- lookups used by the check modules ----

    def layer(self, name: str) -> LayerSpec | None:
        for layer in self.layers:
            if layer.name == name:
                return layer
        return None

    def entity(self, kind: EntityKind) -> EntitySpec | None:
        for spec in self.entities:
            if spec.kind == kind:
                return spec
        return None

    def entity_for_name(self, model_name: str) -> EntitySpec | None:
        """Entity spec implied by a model's suffix, longest suffix winning."""
        best: EntitySpec | None = None
        for spec in self.entities:
            if model_name.endswith(spec.suffix) and (
                best is None or len(spec.suffix) > len(best.suffix)
            ):
                best = spec
        return best

    def layer_for_path(self, path: str) -> LayerSpec | None:
        """Layer owning a file path, most specific pattern winning."""
        best: LayerSpec | None = None
        best_len = -1
        for layer in self.layers:
            for pattern in layer.paths:
                if fnmatch.fnmatch(path, pattern) and len(pattern) > best_len:
                    best, best_len = layer, len(pattern)
        return best

    def rule_setting(self, rule_id: str) -> RuleSetting:
        setting = self.rules.get(rule_id)
        return setting if setting is not None else RuleSetting()

    def is_rule_enabled(self, rule_id: str) -> bool:
        return self.rule_setting(rule_id).enabled


DEFAULT_WEIGHTS: dict[Dimension, float] = {
    Dimension.TESTING: 18.0,
    Dimension.MODEL_CONFORMANCE: 15.0,
    Dimension.LINEAGE_HEALTH: 13.0,
    Dimension.DOCUMENTATION: 13.0,
    Dimension.CROSS_LAYER_SYNC: 13.0,
    Dimension.CONVENTIONS_STRUCTURE: 13.0,
    Dimension.ENTITY_MODELLING: 8.0,
    Dimension.PERFORMANCE_COST: 7.0,
}

ConfigDict_ = Annotated[dict[str, Any], "raw configuration mapping"]
