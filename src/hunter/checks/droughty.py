"""Does the generated schema match the project, and is it still current?

FR4.6 and section 16.6, read from committed files rather than by running
Droughty against the warehouse. That half needs no credential, and it is the
half that turns installing at a client from a security review into a config
change.

One rule here exists because the pilot team wrote the need for it into their own
config: Droughty regeneration "has previously applied only the first override
per model and silently dropped the rest with no warning. Hand-verify this block
against models/droughty_schema.yml after any regeneration." That hand check is
deterministic, so Hunter does it.

``test_ignore`` and ``test_overwrite`` are read as authored intent. Hunter never
re-reports a decision the team has already recorded there.
"""

from __future__ import annotations

import datetime as dt

from hunter.checks.base import REQ_DROUGHTY, REQ_MANIFEST, CheckContext, Findings, plural, rule
from hunter.config.schema import DroughtySpec
from hunter.enums import Dimension, Severity
from hunter.ingest.droughty import dropped_overrides, missing_doc_blocks, orphan_doc_blocks
from hunter.model.entities import DroughtyArtifacts

OVERRIDE_DROPPED = rule(
    "droughty.override_dropped",
    dimension=Dimension.CROSS_LAYER_SYNC,
    severity=Severity.HIGH,
    points=1.5,
    title="{phrase} declared for {subject} never reached the generated schema: {tests}",
    consequence=(
        "Someone wrote these tests into the Droughty config on purpose and the "
        "regeneration dropped them without saying so. {label} is being tested less "
        "than whoever configured it believes."
    ),
    plain_heading="What is tested",
    requires=(REQ_DROUGHTY,),
)

GENERATED_TEST_MISSING = rule(
    "droughty.generated_test_missing",
    dimension=Dimension.CROSS_LAYER_SYNC,
    severity=Severity.MEDIUM,
    points=0.8,
    title="{phrase} in the generated schema for {subject} are not in the project: {tests}",
    consequence=(
        "The generated schema says these tests should exist on {label}, and dbt does "
        "not have them. Either the generated file has not been applied, or something "
        "removed them by hand."
    ),
    plain_heading="What is tested",
    requires=(REQ_MANIFEST, REQ_DROUGHTY),
)

MODEL_NOT_COVERED = rule(
    "droughty.model_not_covered",
    dimension=Dimension.CROSS_LAYER_SYNC,
    severity=Severity.MEDIUM,
    points=0.8,
    title="{subject} is not described in the generated schema",
    consequence=(
        "{label} was skipped when the schema was generated, so it has neither the "
        "generated tests nor the generated descriptions the rest of the project has."
    ),
    plain_heading="What is documented",
    requires=(REQ_MANIFEST, REQ_DROUGHTY),
)

DESCRIPTION_UNDEFINED = rule(
    "droughty.description_undefined",
    dimension=Dimension.DOCUMENTATION,
    severity=Severity.MEDIUM,
    points=0.6,
    title="{phrase} referenced by the generated schema are not defined: {blocks}",
    consequence=(
        "The schema points at descriptions that do not exist, so those columns show "
        "up in the catalogue with nothing written against them."
    ),
    plain_heading="What is documented",
    requires=(REQ_DROUGHTY,),
    exposure_weighted=False,
)

DESCRIPTION_EMPTY = rule(
    "droughty.description_empty",
    dimension=Dimension.DOCUMENTATION,
    severity=Severity.MEDIUM,
    points=0.6,
    title="{phrase} are defined but say nothing: {blocks}",
    consequence=(
        "These descriptions exist and are blank, so the column counts as documented "
        "in the catalogue while explaining nothing to a reader."
    ),
    plain_heading="What is documented",
    requires=(REQ_DROUGHTY,),
    exposure_weighted=False,
)

DESCRIPTION_ORPHANED = rule(
    "droughty.description_orphaned",
    dimension=Dimension.DOCUMENTATION,
    severity=Severity.LOW,
    points=0.1,
    title="{phrase} are defined and never used",
    consequence=(
        "The description file has grown past the model it describes. These entries "
        "describe columns that no longer exist, so anyone reading the file to "
        "understand the data will be misled by them."
    ),
    plain_heading="What is documented",
    requires=(REQ_DROUGHTY,),
    exposure_weighted=False,
)

SCHEMA_STALE = rule(
    "droughty.schema_stale",
    dimension=Dimension.CROSS_LAYER_SYNC,
    severity=Severity.MEDIUM,
    points=1.0,
    title="The generated schema is {days} days old, over the {limit} day window",
    consequence=(
        "Every comparison against the generated schema is being made against an "
        "out-of-date picture. Regenerating it would either clear these findings or "
        "show real ones."
    ),
    plain_heading="What was not checked",
    requires=(REQ_DROUGHTY,),
    exposure_weighted=False,
)

INTROSPECTED_COLUMN_UNDESIGNED = rule(
    "droughty.introspected_column_undesigned",
    dimension=Dimension.MODEL_CONFORMANCE,
    severity=Severity.LOW,
    points=0.4,
    title="{subject} holds {phrase} in the warehouse that the design does not include: {columns}",
    consequence=(
        "The warehouse picture taken by Droughty shows columns on {label} that "
        "nobody designed, so their business meaning is not recorded."
    ),
    plain_heading="Does what was built match the design",
    requires=(REQ_DROUGHTY, "dbml"),
    exposure_weighted=False,
)


def run(context: CheckContext) -> Findings:
    """Compare the committed Droughty output against the project."""
    findings = Findings()
    artifacts = context.project.droughty
    if artifacts is None or not context.has(REQ_DROUGHTY):
        return findings

    spec = context.config.integrations.droughty
    if not spec.enabled:
        return findings

    findings.extend_from(_staleness(context, artifacts, spec))
    findings.extend_from(_dropped(context, artifacts, spec))
    findings.extend_from(_generated_tests(context, artifacts))
    findings.extend_from(_coverage(context, artifacts))
    findings.extend_from(_descriptions(context, artifacts, spec))
    findings.extend_from(_introspected(context, artifacts))
    return findings


def _staleness(context: CheckContext, artifacts: DroughtyArtifacts, spec: DroughtySpec) -> Findings:
    findings = Findings()
    if artifacts.schema_modified_at is None:
        return findings
    context.examine(SCHEMA_STALE.id, "droughty_schema")
    age = (context.as_of - artifacts.schema_modified_at).days
    if age > spec.stale_after_days:
        findings.add(
            context.finding(
                SCHEMA_STALE.id,
                subject="droughty_schema",
                subject_kind="droughty",
                file=artifacts.schema_file,
                evidence={"days": age, "limit": spec.stale_after_days},
            )
        )
    return findings


def _dropped(context: CheckContext, artifacts: DroughtyArtifacts, spec: DroughtySpec) -> Findings:
    """The check that replaces the pilot team's manual verification."""
    findings = Findings()
    if not spec.flag_dropped_overrides:
        return findings

    by_model: dict[str, list[str]] = {}
    for override in dropped_overrides(artifacts):
        by_model.setdefault(override.model, []).append(f"{override.column}: {override.test_name}")

    for model_name in sorted({spec_.model for spec_ in artifacts.test_overrides}):
        context.examine(OVERRIDE_DROPPED.id, model_name)

    for model_name, entries in sorted(by_model.items()):
        model = context.project.any_model(model_name)
        findings.add(
            context.finding(
                OVERRIDE_DROPPED.id,
                subject=model_name,
                file=model.path if model else artifacts.project_file,
                evidence={
                    "count": len(entries),
                    "phrase": plural(len(entries), "test"),
                    "tests": "; ".join(sorted(entries)[:6]),
                },
            )
        )
    return findings


def _generated_tests(context: CheckContext, artifacts: DroughtyArtifacts) -> Findings:
    """Tests the generated schema declares that dbt does not have."""
    findings = Findings()
    if not artifacts.generated_tests or not context.has(REQ_MANIFEST):
        return findings

    ignored = set(artifacts.test_ignore_models)
    wanted: dict[str, set[tuple[str, str]]] = {}
    for spec in artifacts.generated_tests:
        if spec.model in ignored:
            continue
        wanted.setdefault(spec.model, set()).add((spec.column.lower(), spec.kind))

    for model_name, expected in sorted(wanted.items()):
        model = context.project.any_model(model_name)
        if model is None or not model.is_scoreable:
            continue
        context.examine(GENERATED_TEST_MISSING.id, model_name)
        have = {
            (test.column.lower(), test.kind)
            for test in context.project.tests_for(model_name)
            if test.column
        }
        missing = sorted(expected - have)
        if not missing:
            continue
        findings.add(
            context.finding(
                GENERATED_TEST_MISSING.id,
                subject=model_name,
                file=model.path,
                points_scale=len(missing) / max(1, len(expected)),
                evidence={
                    "count": len(missing),
                    "phrase": plural(len(missing), "test"),
                    "tests": "; ".join(f"{column}: {kind}" for column, kind in missing[:6]),
                },
            )
        )
    return findings


def _coverage(context: CheckContext, artifacts: DroughtyArtifacts) -> Findings:
    """Models the generated schema skipped, excluding ones excluded on purpose."""
    findings = Findings()
    if not artifacts.generated_tests or not context.has(REQ_MANIFEST):
        return findings

    covered = artifacts.covered_models
    ignored = set(artifacts.test_ignore_models)

    for model in context.project.sorted_models():
        if not model.is_scoreable or model.is_seed:
            continue
        layer = context.config.layer(model.layer) if model.layer else None
        if layer is None or not layer.in_alignment:
            continue
        if model.name in ignored:
            continue
        context.examine(MODEL_NOT_COVERED.id, model.name)
        if model.name not in covered:
            findings.add(
                context.finding(
                    MODEL_NOT_COVERED.id,
                    subject=model.name,
                    file=model.path,
                )
            )
    return findings


def _descriptions(
    context: CheckContext, artifacts: DroughtyArtifacts, spec: DroughtySpec
) -> Findings:
    """Description blocks: missing, empty, and defined-but-unused."""
    findings = Findings()
    if not artifacts.doc_refs and not artifacts.doc_blocks_defined:
        return findings

    context.examine(DESCRIPTION_UNDEFINED.id, "field_descriptions")
    missing = missing_doc_blocks(artifacts)
    if missing:
        findings.add(
            context.finding(
                DESCRIPTION_UNDEFINED.id,
                subject="field_descriptions",
                subject_kind="droughty",
                evidence={
                    "count": len(missing),
                    "phrase": plural(len(missing), "description"),
                    "blocks": ", ".join(missing[:8]),
                },
            )
        )

    context.examine(DESCRIPTION_EMPTY.id, "field_descriptions")
    if artifacts.doc_blocks_empty:
        findings.add(
            context.finding(
                DESCRIPTION_EMPTY.id,
                subject="field_descriptions",
                subject_kind="droughty",
                evidence={
                    "count": len(artifacts.doc_blocks_empty),
                    "phrase": plural(len(artifacts.doc_blocks_empty), "description"),
                    "blocks": ", ".join(artifacts.doc_blocks_empty[:8]),
                },
            )
        )

    if spec.flag_orphan_descriptions:
        context.examine(DESCRIPTION_ORPHANED.id, "field_descriptions")
        orphans = orphan_doc_blocks(artifacts)
        if orphans:
            findings.add(
                context.finding(
                    DESCRIPTION_ORPHANED.id,
                    subject="field_descriptions",
                    subject_kind="droughty",
                    evidence={
                        "count": len(orphans),
                        "phrase": plural(len(orphans), "description"),
                        "blocks": ", ".join(orphans[:10]),
                    },
                )
            )
    return findings


def _introspected(context: CheckContext, artifacts: DroughtyArtifacts) -> Findings:
    """Droughty's warehouse picture against the authored design."""
    findings = Findings()
    if not artifacts.introspected or not context.project.designed:
        return findings

    from hunter.model.match import Index

    design_index = Index.build(sorted(context.project.designed))

    for name, introspected in sorted(artifacts.introspected.items()):
        match = design_index.find(name)
        if match.target is None:
            continue
        designed = context.project.designed[match.target]
        context.examine(INTROSPECTED_COLUMN_UNDESIGNED.id, match.target)
        extra = sorted(introspected.column_names() - designed.column_names())
        if not extra:
            continue
        findings.add(
            context.finding(
                INTROSPECTED_COLUMN_UNDESIGNED.id,
                subject=match.target,
                subject_kind="designed_entity",
                file=designed.source_file,
                points_scale=len(extra) / max(1, len(introspected.column_names())),
                evidence={
                    "count": len(extra),
                    "phrase": plural(len(extra), "column"),
                    "columns": ", ".join(extra[:8]),
                    "introspected_as": name,
                },
            )
        )
    return findings


def days_old(when: dt.date | None, as_of: dt.date) -> int | None:
    """How many days ago a file was last written."""
    return None if when is None else (as_of - when).days
