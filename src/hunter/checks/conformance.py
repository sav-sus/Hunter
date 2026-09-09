"""Does the warehouse match the authored design?

F16. Compares the DBML design against what dbt describes, column by column and
relationship by relationship. The plain-language requirement in FR16.2 matters
here more than anywhere: "the Store table is designed with one row per store,
but the warehouse holds duplicates" rather than "uniqueness assertion failed".

Column types are compared only where they are known. Types live in
``catalog.json``, which ``dbt docs generate`` writes; a manifest alone carries
almost none. Where they are unavailable Hunter reports that the comparison could
not run, rather than reporting no drift and letting a reader assume there is
none.
"""

from __future__ import annotations

from hunter.checks.base import REQ_DBML, REQ_MANIFEST, CheckContext, Findings, plural, rule
from hunter.config.schema import ColumnNamingSpec
from hunter.enums import Dimension, Severity
from hunter.model.align import AlignmentRow
from hunter.model.entities import DesignedEntity, Model

COLUMN_MISSING_FROM_MODEL = rule(
    "conformance.column_missing_from_model",
    dimension=Dimension.MODEL_CONFORMANCE,
    severity=Severity.HIGH,
    points=1.2,
    title="{subject} is missing {phrase} that the design specifies: {columns}",
    consequence=(
        "{label} was designed to hold these columns and does not. Anything that "
        "expected them, including a report built from the design, has nothing to "
        "read."
    ),
    plain_heading="Does what was built match the design",
)

COLUMN_MISSING_FROM_DESIGN = rule(
    "conformance.column_missing_from_design",
    dimension=Dimension.MODEL_CONFORMANCE,
    severity=Severity.LOW,
    points=0.5,
    title="{subject} has {phrase} the design does not include: {columns}",
    consequence=(
        "{label} holds columns nobody designed, so they are undocumented and their "
        "business meaning is not recorded anywhere."
    ),
    plain_heading="Does what was built match the design",
)

TYPE_DRIFT = rule(
    "conformance.type_drift",
    dimension=Dimension.MODEL_CONFORMANCE,
    severity=Severity.MEDIUM,
    points=1.0,
    title="{subject} has {phrase} built with a different type than designed: {columns}",
    consequence=(
        "These columns of {label} hold a different kind of value than the design "
        "says. Depending on the difference, figures may be rounded, truncated or "
        "compared wrongly."
    ),
    plain_heading="Does what was built match the design",
    requires=(REQ_MANIFEST, REQ_DBML),
)

TYPES_UNAVAILABLE = rule(
    "conformance.types_unavailable",
    dimension=Dimension.MODEL_CONFORMANCE,
    severity=Severity.INFO,
    points=0.0,
    title="Column types were not available, so designed and built types were not compared",
    consequence=(
        "Hunter could not check whether columns are built with the types the design "
        "specifies, because the project has no catalogue file. Running "
        "'dbt docs generate' alongside the build would let this run. Nothing here "
        "means the types are wrong; it means they were not checked."
    ),
    plain_heading="What was not checked",
    requires=(REQ_MANIFEST, REQ_DBML),
    exposure_weighted=False,
    about_coverage=True,
)

RELATIONSHIP_NOT_TESTED = rule(
    "conformance.relationship_not_tested",
    dimension=Dimension.MODEL_CONFORMANCE,
    severity=Severity.MEDIUM,
    points=1.0,
    title="The designed link from {subject}.{column} to {target} has no test",
    consequence=(
        "The design says every row of {label} points at a row of {target}, and "
        "nothing checks it. Where it does not hold, those rows drop out of joins "
        "and figures come out low with no error."
    ),
    plain_heading="Keys and joins",
    requires=(REQ_MANIFEST, REQ_DBML),
)

RELATIONSHIP_KEY_MISSING = rule(
    "conformance.relationship_key_missing",
    dimension=Dimension.MODEL_CONFORMANCE,
    severity=Severity.HIGH,
    points=1.5,
    title=(
        "The designed link from {subject}.{column} points at "
        "{target}.{target_column}, which does not exist"
    ),
    consequence=(
        "The design connects {label} to something that is not there. Either the "
        "design is out of date or the table it points at was never built as "
        "designed."
    ),
    plain_heading="Keys and joins",
    requires=(REQ_DBML,),
)

DESIGN_NO_PRIMARY_KEY = rule(
    "conformance.design_no_primary_key",
    dimension=Dimension.MODEL_CONFORMANCE,
    severity=Severity.HIGH,
    points=1.5,
    title="The design for {subject} declares no primary key",
    consequence=(
        "Nothing in the design says what makes a row of {label} unique, so nobody "
        "can tell what one row means or check that duplicates have not crept in."
    ),
    plain_heading="Keys and joins",
    requires=(REQ_DBML,),
    exposure_weighted=False,
)

DESIGN_ENTITY_SUFFIX = rule(
    "conformance.design_entity_suffix_missing",
    dimension=Dimension.MODEL_CONFORMANCE,
    severity=Severity.LOW,
    points=0.5,
    title="The designed name {subject} declares no entity type",
    consequence=(
        "The design does not say whether {label} is a fact, a dimension or an "
        "aggregate, so a reader cannot tell how it is meant to be used. Expected "
        "one of: {expected}."
    ),
    plain_heading="Naming conventions",
    requires=(REQ_DBML,),
    exposure_weighted=False,
)

DESIGN_KEY_NAMING = rule(
    "conformance.design_key_naming",
    dimension=Dimension.MODEL_CONFORMANCE,
    severity=Severity.LOW,
    points=0.4,
    title="The design for {subject} has {phrase} named outside the key rules: {columns}",
    consequence=(
        "Keys in the design of {label} are not named the way the standard says, so "
        "it is not obvious which columns identify a row and which point elsewhere."
    ),
    plain_heading="Naming conventions",
    requires=(REQ_DBML,),
    exposure_weighted=False,
)

DESIGN_NOT_BUILT = rule(
    "conformance.design_not_built",
    dimension=Dimension.MODEL_CONFORMANCE,
    severity=Severity.MEDIUM,
    points=1.0,
    title="{subject} is designed but no model builds it",
    consequence=(
        "{label} was designed and agreed, and nothing in the repository produces it "
        "yet. It is on the plan and not started."
    ),
    plain_heading="What was designed against what exists",
    requires=(REQ_DBML,),
    exposure_weighted=False,
)

#: Types that mean the same thing in different words, so a difference here is
#: spelling rather than drift.
TYPE_ALIASES: dict[str, str] = {
    "varchar": "string",
    "text": "string",
    "char": "string",
    "int": "integer",
    "int64": "integer",
    "bigint": "integer",
    "smallint": "integer",
    "decimal": "numeric",
    "bignumeric": "numeric",
    "float": "float",
    "float64": "float",
    "double": "float",
    "real": "float",
    "bool": "boolean",
    "datetime": "timestamp",
    "timestamptz": "timestamp",
}


def canonical_type(value: str | None) -> str | None:
    """Reduce a type name to a comparable form."""
    if not value:
        return None
    lowered = value.strip().lower()
    lowered = lowered.split("(", 1)[0].strip()
    lowered = lowered.removeprefix("array<").removesuffix(">")
    return TYPE_ALIASES.get(lowered, lowered)


def run(context: CheckContext) -> Findings:
    """Compare the authored design against what dbt describes."""
    findings = Findings()
    if not context.has(REQ_DBML):
        return findings

    naming = context.config.column_naming
    types_known = context.project.has_column_types()

    if not types_known and context.project.designed:
        findings.add(
            context.finding(
                TYPES_UNAVAILABLE.id,
                subject="project",
                subject_kind="project",
            )
        )

    rows_by_design = {row.designed_name: row for row in context.alignment.rows if row.designed_name}

    for entity in context.project.sorted_designed():
        findings.extend_from(_design_standard(context, entity, naming))

        row = rows_by_design.get(entity.name)
        model = context.project.model(row.model_name) if row and row.model_name else None

        context.examine(DESIGN_NOT_BUILT.id, entity.name)
        if model is None:
            if row is None or row.repo.value not in {"present", "disabled"}:
                findings.add(
                    context.finding(
                        DESIGN_NOT_BUILT.id,
                        subject=entity.name,
                        subject_kind="designed_entity",
                        file=entity.source_file,
                    )
                )
            continue

        designed_columns = entity.column_names()
        built_columns = model.column_names()

        context.examine(COLUMN_MISSING_FROM_MODEL.id, model.name)
        missing = sorted(designed_columns - built_columns)
        if missing:
            findings.add(
                context.finding(
                    COLUMN_MISSING_FROM_MODEL.id,
                    subject=model.name,
                    file=model.path,
                    points_scale=len(missing) / max(1, len(designed_columns)),
                    evidence={
                        "count": len(missing),
                        "phrase": plural(len(missing), "column"),
                        "columns": ", ".join(missing[:8]),
                        "design": entity.name,
                    },
                )
            )

        context.examine(COLUMN_MISSING_FROM_DESIGN.id, model.name)
        extra = sorted(built_columns - designed_columns)
        if extra:
            findings.add(
                context.finding(
                    COLUMN_MISSING_FROM_DESIGN.id,
                    subject=model.name,
                    file=model.path,
                    points_scale=len(extra) / max(1, len(built_columns)),
                    evidence={
                        "count": len(extra),
                        "phrase": plural(len(extra), "column"),
                        "columns": ", ".join(extra[:8]),
                        "design": entity.name,
                    },
                )
            )

        if types_known:
            findings.extend_from(_type_drift(context, entity, model))

        findings.extend_from(_relationships(context, entity, model, rows_by_design))

    return findings


def _design_standard(
    context: CheckContext, entity: DesignedEntity, naming: ColumnNamingSpec
) -> Findings:
    """FR16.6 and FR16.8: the design against the house standard."""
    findings = Findings()

    context.examine(DESIGN_NO_PRIMARY_KEY.id, entity.name)
    if not entity.has_primary_key:
        findings.add(
            context.finding(
                DESIGN_NO_PRIMARY_KEY.id,
                subject=entity.name,
                subject_kind="designed_entity",
                file=entity.source_file,
            )
        )

    context.examine(DESIGN_ENTITY_SUFFIX.id, entity.name)
    spec = context.config.entity_for_name(entity.name)
    if spec is None:
        findings.add(
            context.finding(
                DESIGN_ENTITY_SUFFIX.id,
                subject=entity.name,
                subject_kind="designed_entity",
                file=entity.source_file,
                evidence={"expected": ", ".join(item.suffix for item in context.config.entities)},
            )
        )

    context.examine(DESIGN_KEY_NAMING.id, entity.name)
    wrong: list[str] = []
    for column in entity.columns:
        name = column.name.lower()
        if column.is_primary_key and not name.endswith(naming.primary_key_suffix):
            wrong.append(column.name)
    if wrong:
        findings.add(
            context.finding(
                DESIGN_KEY_NAMING.id,
                subject=entity.name,
                subject_kind="designed_entity",
                file=entity.source_file,
                points_scale=len(wrong) / max(1, len(entity.columns)),
                evidence={
                    "count": len(wrong),
                    "phrase": plural(len(wrong), "key"),
                    "columns": ", ".join(sorted(wrong)[:6]),
                },
            )
        )
    return findings


def _type_drift(context: CheckContext, entity: DesignedEntity, model: Model) -> Findings:
    """FR16.4, where types are known."""
    findings = Findings()
    context.examine(TYPE_DRIFT.id, model.name)

    drifted: list[str] = []
    for designed_column in entity.columns:
        built = model.column(designed_column.name)
        if built is None:
            continue
        want = canonical_type(designed_column.data_type)
        got = canonical_type(built.data_type)
        if want and got and want != got:
            drifted.append(f"{designed_column.name} ({want} designed, {got} built)")

    if drifted:
        findings.add(
            context.finding(
                TYPE_DRIFT.id,
                subject=model.name,
                file=model.path,
                points_scale=len(drifted) / max(1, len(entity.columns)),
                evidence={
                    "count": len(drifted),
                    "phrase": plural(len(drifted), "column"),
                    "columns": "; ".join(drifted[:6]),
                },
            )
        )
    return findings


def _relationships(
    context: CheckContext,
    entity: DesignedEntity,
    model: Model,
    rows_by_design: dict[str, AlignmentRow],
) -> Findings:
    """FR16.5: every designed link backed by a test, pointing at something real."""
    findings = Findings()
    tests = context.project.tests_for(model.name)
    tested_columns = {
        test.column.lower() for test in tests if test.is_relationship_test and test.column
    }

    for ref in context.project.refs_from(entity.name):
        column = ref.from_columns[0] if ref.from_columns else None
        if column is None:
            continue

        target_entity = context.project.designed.get(ref.to_table)
        target_column = ref.to_columns[0] if ref.to_columns else None

        context.examine(RELATIONSHIP_KEY_MISSING.id, model.name)
        if (
            target_entity is not None
            and target_column is not None
            and target_entity.column(target_column) is None
        ):
            findings.add(
                context.finding(
                    RELATIONSHIP_KEY_MISSING.id,
                    subject=model.name,
                    file=model.path,
                    evidence={
                        "column": column,
                        "target": ref.to_table,
                        "target_column": target_column,
                    },
                )
            )
            continue

        if model.column(column) is None:
            # The missing column is already reported by the column comparison.
            continue

        context.examine(RELATIONSHIP_NOT_TESTED.id, model.name)
        if column.lower() not in tested_columns:
            target_row = rows_by_design.get(ref.to_table)
            target_label = target_row.label if target_row else ref.to_table
            findings.add(
                context.finding(
                    RELATIONSHIP_NOT_TESTED.id,
                    subject=model.name,
                    file=model.path,
                    evidence={
                        "column": column,
                        "target": target_label,
                        "target_model": ref.to_table,
                        "cardinality": ref.cardinality or "unstated",
                    },
                )
            )
    return findings
