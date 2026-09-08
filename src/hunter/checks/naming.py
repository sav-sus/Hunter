"""Naming and layering: do the conventions hold?

FR2.1 and FR2.2. Everything here is read from ``hunter.yml``: the layer
prefixes, the entity suffixes, the column suffixes and which layers may
reference which. Hunter has no built-in opinion about any of it, which is what
makes it portable between clients.

The layer boundary rules are the ones that matter most. A mart reading straight
from a source means a source schema change reaches a dashboard with nothing in
between to catch it.
"""

from __future__ import annotations

from hunter.checks.base import CheckContext, Findings, plural, rule
from hunter.config.schema import ColumnNamingSpec, LayerSpec
from hunter.enums import Dimension, EntityKind, Severity
from hunter.model.entities import Model

LAYER_PREFIX_WRONG = rule(
    "naming.layer_prefix_wrong",
    dimension=Dimension.CONVENTIONS_STRUCTURE,
    severity=Severity.LOW,
    points=0.6,
    title="{subject} sits in the {layer} layer but does not start with {prefix!r}",
    consequence=(
        "The name does not say which layer {label} belongs to, so anyone reading a "
        "query cannot tell whether they are using a finished table or a working step."
    ),
    plain_heading="Naming conventions",
    exposure_weighted=False,
)

ENTITY_SUFFIX_MISSING = rule(
    "naming.entity_suffix_missing",
    dimension=Dimension.CONVENTIONS_STRUCTURE,
    severity=Severity.MEDIUM,
    points=0.8,
    title="{subject} is in the {layer} layer but its name declares no entity type",
    consequence=(
        "The name does not say whether {label} is a fact, a dimension or an "
        "aggregate, so nobody can tell how it is meant to be joined or summed. "
        "Expected one of: {expected}."
    ),
    plain_heading="Naming conventions",
    exposure_weighted=False,
)

PRIMARY_KEY_COLUMN_MISSING = rule(
    "naming.primary_key_column_missing",
    dimension=Dimension.CONVENTIONS_STRUCTURE,
    severity=Severity.HIGH,
    points=1.5,
    title="{subject} has no column ending in {suffix!r}",
    consequence=(
        "{label} has no identifiable key column, so nothing can check it has one row "
        "per thing, and joins to it cannot be verified."
    ),
    plain_heading="Keys and joins",
)

DATE_COLUMN_SUFFIX = rule(
    "naming.date_column_suffix",
    dimension=Dimension.CONVENTIONS_STRUCTURE,
    severity=Severity.LOW,
    points=0.4,
    title="{phrase} on {subject} do not end in {date!r} or {ts!r}",
    consequence=(
        "A reader cannot tell from the name whether these columns hold a date or a "
        "point in time, which is how time-zone errors get into reports: {columns}."
    ),
    plain_heading="Naming conventions",
)

LAYER_BOUNDARY_VIOLATION = rule(
    "naming.layer_boundary_violation",
    dimension=Dimension.CONVENTIONS_STRUCTURE,
    severity=Severity.HIGH,
    points=1.5,
    title=(
        "{subject} ({layer}) reads from {referenced} ({referenced_layer}), which is not permitted"
    ),
    consequence=(
        "{label} skips the layers in between, so a change upstream reaches it with "
        "nothing to catch the problem first. The {layer} layer may only read from: "
        "{permitted}."
    ),
    plain_heading="How the layers fit together",
)

DIRECT_SOURCE_REFERENCE = rule(
    "naming.direct_source_reference",
    dimension=Dimension.CONVENTIONS_STRUCTURE,
    severity=Severity.HIGH,
    points=1.5,
    title="{subject} ({layer}) reads directly from {phrase}",
    consequence=(
        "{label} reads raw source data with no staging step in between, so a change "
        "at the source lands straight in it. Sources read: {sources}."
    ),
    plain_heading="How the layers fit together",
)

MATERIALISATION_NOT_PERMITTED = rule(
    "naming.materialisation_not_permitted",
    dimension=Dimension.CONVENTIONS_STRUCTURE,
    severity=Severity.MEDIUM,
    points=0.8,
    title=(
        "{subject} is materialised as {materialisation!r}, which the {layer} layer does not permit"
    ),
    consequence=(
        "{label} is built in a way its layer does not allow, so it either costs more "
        "to run than intended or does not persist when it should. Permitted here: "
        "{permitted}."
    ),
    plain_heading="How the layers fit together",
)

MODEL_OUTSIDE_EVERY_LAYER = rule(
    "naming.model_outside_every_layer",
    dimension=Dimension.CONVENTIONS_STRUCTURE,
    severity=Severity.MEDIUM,
    points=1.0,
    title="{subject} is at {path} which belongs to no declared layer",
    consequence=(
        "No conventions are being applied to {label} at all, because Hunter cannot "
        "tell which layer it is meant to be in. It is unchecked rather than correct."
    ),
    plain_heading="How the layers fit together",
    exposure_weighted=False,
)

#: Warehouse column types that should carry a date or timestamp suffix.
DATE_TYPES = frozenset({"date", "datetime", "timestamp", "time"})


def _looks_like_time_column(name: str, data_type: str | None) -> bool:
    if data_type and data_type.strip().lower() in DATE_TYPES:
        return True
    lowered = name.lower()
    return lowered.endswith(("_date", "_time", "_datetime", "_timestamp"))


def run(context: CheckContext) -> Findings:
    """Check naming and layering against the configured conventions."""
    findings = Findings()
    config = context.config
    naming = config.column_naming
    layer_names = {layer.name for layer in config.layers}

    for model in context.project.sorted_models():
        if not model.is_scoreable:
            continue

        if model.layer is None:
            context.examine(MODEL_OUTSIDE_EVERY_LAYER.id, model.name)
            findings.add(
                context.finding(
                    MODEL_OUTSIDE_EVERY_LAYER.id,
                    subject=model.name,
                    file=model.path,
                    evidence={"path": model.path},
                )
            )
            continue

        layer = config.layer(model.layer)
        if layer is None:
            continue

        findings.extend(_prefix_and_suffix(context, model, layer))
        findings.extend(_key_and_date_columns(context, model, layer, naming))
        findings.extend(_references(context, model, layer, layer_names))
        findings.extend(_materialisation(context, model, layer))

    return findings


def _prefix_and_suffix(context: CheckContext, model: Model, layer: LayerSpec) -> Findings:
    findings = Findings()

    if layer.prefix:
        context.examine(LAYER_PREFIX_WRONG.id, model.name)
        if not model.name.startswith(layer.prefix):
            findings.add(
                context.finding(
                    LAYER_PREFIX_WRONG.id,
                    subject=model.name,
                    file=model.path,
                    evidence={"layer": layer.name, "prefix": layer.prefix},
                )
            )

    if layer.expected_entity_kinds and model.is_sql_model:
        context.examine(ENTITY_SUFFIX_MISSING.id, model.name)
        if model.entity_kind_declared is EntityKind.UNKNOWN:
            expected = ", ".join(
                spec.suffix
                for spec in context.config.entities
                if spec.kind in layer.expected_entity_kinds
            )
            findings.add(
                context.finding(
                    ENTITY_SUFFIX_MISSING.id,
                    subject=model.name,
                    file=model.path,
                    evidence={"layer": layer.name, "expected": expected},
                )
            )
    return findings


def _key_and_date_columns(
    context: CheckContext, model: Model, layer: LayerSpec, naming: ColumnNamingSpec
) -> Findings:
    findings = Findings()
    if not model.columns:
        return findings

    if layer.expected_entity_kinds and model.entity_kind_declared is not EntityKind.UNKNOWN:
        context.examine(PRIMARY_KEY_COLUMN_MISSING.id, model.name)
        has_key = any(
            column.name.lower().endswith(naming.primary_key_suffix) for column in model.columns
        )
        if not has_key:
            findings.add(
                context.finding(
                    PRIMARY_KEY_COLUMN_MISSING.id,
                    subject=model.name,
                    file=model.path,
                    evidence={"suffix": naming.primary_key_suffix},
                )
            )

    context.examine(DATE_COLUMN_SUFFIX.id, model.name)
    wrong = [
        column.name
        for column in model.columns
        if _looks_like_time_column(column.name, column.data_type)
        and not column.name.lower().endswith((naming.date_suffix, naming.timestamp_suffix))
    ]
    if wrong:
        findings.add(
            context.finding(
                DATE_COLUMN_SUFFIX.id,
                subject=model.name,
                file=model.path,
                points_scale=min(1.0, len(wrong) / max(1, len(model.columns))) or 1.0,
                evidence={
                    "count": len(wrong),
                    "phrase": plural(len(wrong), "date or time column"),
                    "columns": ", ".join(sorted(wrong)[:8]),
                    "date": naming.date_suffix,
                    "ts": naming.timestamp_suffix,
                },
            )
        )
    return findings


def _references(
    context: CheckContext, model: Model, layer: LayerSpec, layer_names: set[str]
) -> Findings:
    findings = Findings()

    if layer.may_reference:
        context.examine(LAYER_BOUNDARY_VIOLATION.id, model.name)
        permitted = set(layer.may_reference)
        for referenced in model.depends_on_models:
            other = context.project.any_model(referenced)
            if other is None or other.layer is None:
                continue
            if other.layer in layer_names and other.layer not in permitted:
                findings.add(
                    context.finding(
                        LAYER_BOUNDARY_VIOLATION.id,
                        subject=model.name,
                        file=model.path,
                        evidence={
                            "layer": layer.name,
                            "referenced": referenced,
                            "referenced_layer": other.layer,
                            "permitted": ", ".join(sorted(permitted)) or "nothing",
                        },
                    )
                )

    if not layer.may_reference_sources:
        context.examine(DIRECT_SOURCE_REFERENCE.id, model.name)
        if model.depends_on_sources:
            findings.add(
                context.finding(
                    DIRECT_SOURCE_REFERENCE.id,
                    subject=model.name,
                    file=model.path,
                    evidence={
                        "layer": layer.name,
                        "phrase": plural(len(model.depends_on_sources), "raw source"),
                        "sources": ", ".join(sorted(model.depends_on_sources)[:6]),
                    },
                )
            )
    return findings


def _materialisation(context: CheckContext, model: Model, layer: LayerSpec) -> Findings:
    if not layer.materialisations:
        return Findings()
    context.examine(MATERIALISATION_NOT_PERMITTED.id, model.name)
    if model.materialisation in layer.materialisations:
        return Findings()
    finding = context.finding(
        MATERIALISATION_NOT_PERMITTED.id,
        subject=model.name,
        file=model.path,
        evidence={
            "layer": layer.name,
            "materialisation": model.materialisation,
            "permitted": ", ".join(sorted(layer.materialisations)),
        },
    )
    out = Findings()
    out.add(finding)
    return out
