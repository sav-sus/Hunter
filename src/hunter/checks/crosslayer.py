"""Do dbt and LookML still agree?

F4. This is the check that answers "will a column rename break a dashboard",
and it is the reason FR4.2 exists: a dbt column rename that silently breaks a
report should be found in the pull request that made it, not by the client.

Every LookML field that reads a column is mapped to the dbt model column it
depends on. Where the column is gone, the field is broken now, whether or not
anyone has noticed.

Derived tables are recorded and skipped, per risk 6 in section 15. On the pilot
that is 13 of 80 views, and the reason is scope: analysing derived-table SQL is
a second SQL parser's worth of work for a small share of the estate.
"""

from __future__ import annotations

from hunter.checks.base import REQ_LOOKML, REQ_MANIFEST, CheckContext, Findings, plural, rule
from hunter.enums import Dimension, Severity
from hunter.model.entities import LookmlView, Model

FIELD_REFERENCES_MISSING_COLUMN = rule(
    "crosslayer.field_references_missing_column",
    dimension=Dimension.CROSS_LAYER_SYNC,
    severity=Severity.HIGH,
    points=2.0,
    title=("{phrase} in view {subject} read columns {model} no longer produces: {columns}"),
    consequence=(
        "These report fields are broken now. Anyone opening a report that uses them "
        "gets an error or a blank, and the cause is a column that was renamed or "
        "removed in {model}."
    ),
    plain_heading="Do the reports still match the data",
    requires=(REQ_MANIFEST, REQ_LOOKML),
)

VIEW_MODEL_MISSING = rule(
    "crosslayer.view_model_missing",
    dimension=Dimension.CROSS_LAYER_SYNC,
    severity=Severity.HIGH,
    points=2.0,
    title="View {subject} reads {table}, which no model produces",
    consequence=(
        "This report view points at a table nothing in the project builds. Either "
        "the table is produced outside dbt, or the view is pointing at something "
        "that no longer exists."
    ),
    plain_heading="Do the reports still match the data",
    requires=(REQ_MANIFEST, REQ_LOOKML),
    exposure_weighted=False,
)

VIEW_TABLE_UNRESOLVABLE = rule(
    "crosslayer.view_table_unresolvable",
    dimension=Dimension.CROSS_LAYER_SYNC,
    severity=Severity.LOW,
    points=0.3,
    title="View {subject} names its table in a way Hunter cannot resolve: {table!r}",
    consequence=(
        "Hunter could not tell which table this report view reads, so its fields "
        "were not checked against the data. Nothing here says it is broken; it says "
        "it was not checked."
    ),
    plain_heading="What was not checked",
    requires=(REQ_LOOKML,),
    exposure_weighted=False,
    about_coverage=True,
)

EXPLORE_NO_CACHING = rule(
    "crosslayer.explore_no_caching_policy",
    dimension=Dimension.CROSS_LAYER_SYNC,
    severity=Severity.LOW,
    points=0.4,
    title="Explore {subject} has no caching policy",
    consequence=(
        "Every query against this explore goes to the warehouse, so it costs more "
        "than it needs to and is slower for whoever is waiting."
    ),
    plain_heading="Reporting setup",
    requires=(REQ_LOOKML,),
    exposure_weighted=False,
)

DUPLICATE_MEASURE = rule(
    "crosslayer.duplicate_measure",
    dimension=Dimension.CROSS_LAYER_SYNC,
    severity=Severity.MEDIUM,
    points=1.0,
    title="{subject} defines {phrase} that {model} already computes: {columns}",
    consequence=(
        "The same figure is worked out in two places. When one is changed and the "
        "other is not, two reports show different numbers for the same thing and "
        "nobody can tell which is right."
    ),
    plain_heading="Where the numbers are worked out",
    requires=(REQ_MANIFEST, REQ_LOOKML),
    exposure_weighted=False,
)

EXPOSURE_MISSING = rule(
    "crosslayer.exposure_missing",
    dimension=Dimension.CROSS_LAYER_SYNC,
    severity=Severity.LOW,
    points=0.4,
    title="{subject} feeds {phrase} but declares no exposure",
    consequence=(
        "Nothing in the project records that reports depend on {label}, so anyone "
        "changing it has no way to see what they would break."
    ),
    plain_heading="Do the reports still match the data",
    requires=(REQ_MANIFEST, REQ_LOOKML),
)

#: LookML measure types that aggregate, so a same-named dbt column computing
#: the same thing is a duplicate rather than a pass-through.
AGGREGATING_TYPES = frozenset(
    {"sum", "count", "count_distinct", "average", "min", "max", "median", "percentile"}
)


def run(context: CheckContext) -> Findings:
    """Compare the semantic layer against the models beneath it."""
    findings = Findings()
    if not context.has(REQ_LOOKML):
        return findings

    spec = context.config.cross_layer
    project = context.project

    for view in sorted(project.lookml_views.values(), key=lambda item: item.name):
        if view.is_derived_table and spec.skip_derived_tables:
            continue

        if view.model_name is None:
            context.examine(VIEW_TABLE_UNRESOLVABLE.id, view.name)
            findings.add(
                context.finding(
                    VIEW_TABLE_UNRESOLVABLE.id,
                    subject=view.name,
                    subject_kind="lookml_view",
                    file=view.file,
                    evidence={"table": view.sql_table_name or "not stated"},
                )
            )
            continue

        model = project.any_model(view.model_name)

        context.examine(VIEW_MODEL_MISSING.id, view.name)
        if model is None:
            findings.add(
                context.finding(
                    VIEW_MODEL_MISSING.id,
                    subject=view.name,
                    subject_kind="lookml_view",
                    file=view.file,
                    evidence={"table": view.model_name},
                )
            )
            continue

        findings.extend_from(_broken_fields(context, view, model))
        if spec.flag_duplicate_measures:
            findings.extend_from(_duplicate_measures(context, view, model))

    if spec.require_datagroup_on_explores:
        for explore in sorted(project.explores.values(), key=lambda item: item.name):
            context.examine(EXPLORE_NO_CACHING.id, explore.name)
            if not explore.has_caching_policy:
                findings.add(
                    context.finding(
                        EXPLORE_NO_CACHING.id,
                        subject=explore.name,
                        subject_kind="explore",
                        file=explore.file,
                    )
                )

    if spec.generate_missing_exposures:
        findings.extend_from(_missing_exposures(context))

    return findings


def _broken_fields(context: CheckContext, view: LookmlView, model: Model) -> Findings:
    """FR4.2: report fields reading columns the model no longer produces."""
    findings = Findings()
    if not model.columns:
        # Nothing to compare against: a model with no described columns cannot
        # prove a field is broken.
        return findings

    context.examine(FIELD_REFERENCES_MISSING_COLUMN.id, model.name, weight=model.exposure_weight)
    available = model.column_names()
    broken: list[str] = []
    for field in view.fields:
        for column in field.referenced_columns:
            if column.lower() not in available:
                broken.append(f"{field.name} -> {column}")

    if broken:
        findings.add(
            context.finding(
                FIELD_REFERENCES_MISSING_COLUMN.id,
                subject=view.name,
                subject_kind="lookml_view",
                file=view.file,
                exposure_weight=model.exposure_weight,
                evidence={
                    "count": len(broken),
                    "phrase": plural(len(broken), "report field"),
                    "columns": ", ".join(sorted(broken)[:8]),
                    "model": model.name,
                },
            )
        )
    return findings


def _duplicate_measures(context: CheckContext, view: LookmlView, model: Model) -> Findings:
    """FR4.4: the same figure computed in both layers."""
    findings = Findings()
    measures = [
        field for field in view.measures if (field.lookml_type or "").lower() in AGGREGATING_TYPES
    ]
    if not measures:
        return findings

    context.examine(DUPLICATE_MEASURE.id, view.name)
    available = model.column_names()
    duplicated = [field.name for field in measures if field.name.lower() in available]
    if duplicated:
        findings.add(
            context.finding(
                DUPLICATE_MEASURE.id,
                subject=view.name,
                subject_kind="lookml_view",
                file=view.file,
                points_scale=len(duplicated) / len(measures),
                evidence={
                    "count": len(duplicated),
                    "phrase": plural(len(duplicated), "figure"),
                    "columns": ", ".join(sorted(duplicated)[:6]),
                    "model": model.name,
                },
            )
        )
    return findings


def _missing_exposures(context: CheckContext) -> Findings:
    """FR4.7: models the semantic layer consumes with no exposure declared."""
    findings = Findings()
    declared = {
        name for exposure in context.project.exposures for name in exposure.depends_on_models
    }

    for model in context.project.sorted_models():
        if not model.is_scoreable:
            continue
        views = context.project.views_for_model(model.name)
        if not views:
            continue
        context.examine(EXPOSURE_MISSING.id, model.name)
        if model.name in declared:
            continue
        findings.add(
            context.finding(
                EXPOSURE_MISSING.id,
                subject=model.name,
                file=model.path,
                evidence={
                    "count": len(views),
                    "phrase": plural(len(views), "report view"),
                    "views": ", ".join(sorted(view.name for view in views)[:6]),
                },
            )
        )
    return findings
