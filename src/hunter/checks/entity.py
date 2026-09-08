"""Does the table behave like the thing its name says it is?

FR3.1 to FR3.3 and FR3.6. A table named ``_fact`` that behaves like a dimension,
or the reverse, is the cause of the grain errors and double counting that take
days to root-cause. The name is a claim; the columns are evidence.

Inference is deliberately conservative, because the risk register says that
false positives here lose trust early. Every finding carries a confidence, and
anything below the configured floor is reported as a suggestion and excluded
from the score. Where the signals genuinely conflict, Hunter says so rather than
guessing.

Without warehouse access there is no uniqueness ratio and no row count to work
from, so the inference rests on column shape alone. That is stated in the
evidence so a reader knows what the judgement was based on.
"""

from __future__ import annotations

from dataclasses import dataclass

from hunter.checks.base import CheckContext, Findings, plural, rule
from hunter.config.schema import ColumnNamingSpec, EntityInferenceSpec
from hunter.enums import Dimension, EntityKind, Severity
from hunter.model.entities import Model

TYPE_MISMATCH = rule(
    "entity.declared_type_mismatch",
    dimension=Dimension.ENTITY_MODELLING,
    severity=Severity.HIGH,
    points=2.0,
    title=(
        "{subject} is named as {declared_article} {declared} but behaves like "
        "{inferred_article} {inferred}"
    ),
    consequence=(
        "{label} is used as though it were {declared_article} {declared}, but its columns "
        "say it is {inferred_article} {inferred}. Joining or summing it as the name "
        "suggests will give the wrong "
        "answer. Evidence: {evidence_text}."
    ),
    plain_heading="Are the tables the shape they claim",
    confidence=0.8,
)

TYPE_UNCLEAR = rule(
    "entity.type_unclear",
    dimension=Dimension.ENTITY_MODELLING,
    severity=Severity.LOW,
    points=0.5,
    title=(
        "{subject} is named as {declared_article} {declared}, and its shape neither "
        "clearly agrees nor disagrees"
    ),
    consequence=(
        "Hunter could not tell from its columns whether {label} really is "
        "{declared_article} {declared}. Worth a human look rather than a change. "
        "Evidence: "
        "{evidence_text}."
    ),
    plain_heading="Are the tables the shape they claim",
    confidence=0.4,
)

SURROGATE_KEY_MISSING = rule(
    "entity.surrogate_key_missing",
    dimension=Dimension.ENTITY_MODELLING,
    severity=Severity.HIGH,
    points=1.5,
    title="{subject} is {declared_article} {declared} with no surrogate key column",
    consequence=(
        "{label} has no single column identifying a row, so nothing can prove it has "
        "one row per thing and joins to it cannot be checked."
    ),
    plain_heading="Keys and joins",
)

FACT_WITHOUT_MEASURES = rule(
    "entity.fact_without_measures",
    dimension=Dimension.ENTITY_MODELLING,
    severity=Severity.MEDIUM,
    points=1.0,
    title="{subject} is named as a fact but has no numeric columns to add up",
    consequence=(
        "{label} is named as something you would total, and there is nothing in it "
        "to total. Either it is really a dimension or a bridge, or the measures are "
        "missing."
    ),
    plain_heading="Are the tables the shape they claim",
)

DIMENSION_WITH_MEASURES = rule(
    "entity.dimension_with_measures",
    dimension=Dimension.ENTITY_MODELLING,
    severity=Severity.MEDIUM,
    points=1.0,
    title="{subject} is named as a dimension but carries {phrase}",
    consequence=(
        "{label} is named as a lookup table but holds figures. Anyone joining it and "
        "summing those figures will multiply them by however many rows the join "
        "returns. Columns: {columns}."
    ),
    plain_heading="Are the tables the shape they claim",
)

#: Warehouse types that can be added up.
NUMERIC_TYPES = frozenset(
    {
        "int64",
        "integer",
        "int",
        "smallint",
        "bigint",
        "numeric",
        "bignumeric",
        "decimal",
        "float64",
        "float",
        "double",
        "real",
    }
)

#: Words that mean a column holds something you would add up.
#:
#: Matched as tokens anywhere in the name, not as a suffix. The pilot has
#: columns like ``store_visitor_count_actual`` and
#: ``store_visitor_count_estimated``, where the measure word sits in the middle
#: and a suffix test misses it, reporting a fact with measures as a fact with
#: none.
MEASURE_WORDS = frozenset(
    {
        "amount",
        "count",
        "qty",
        "quantity",
        "value",
        "total",
        "sum",
        "avg",
        "average",
        "revenue",
        "cost",
        "price",
        "rate",
        "ratio",
        "units",
        "hours",
        "days",
        "score",
        "weight",
        "spend",
        "sales",
        "margin",
        "discount",
        "tax",
        "volume",
        "duration",
        "seconds",
        "minutes",
        "percent",
        "pct",
        "asp",
        "upt",
        "atv",
    }
)


#: Endings that mean a column describes rather than measures, even when a
#: measure word appears in the name. ``exchange_rate_from_currency`` holds a
#: currency code, and ``employee_cost_centre_name`` holds a name.
NON_MEASURE_ENDINGS = (
    "_name",
    "_code",
    "_id",
    "_type",
    "_status",
    "_currency",
    "_description",
    "_desc",
    "_label",
    "_key",
    "_group",
    "_category",
    "_centre",
    "_center",
    "_url",
    "_email",
    "_bucket",
    "_band",
    "_segment",
    "_reason",
    "_comment",
)


def looks_like_boolean(name: str, prefixes: list[str], suffixes: list[str]) -> bool:
    """Whether a column name says it holds a yes or no.

    Matches the marker anywhere, not only at the start: the pilot has
    ``exchange_rate_is_carried_forward``, where ``is_`` sits in the middle.
    """
    lowered = name.lower()
    if lowered.endswith(tuple(suffixes)):
        return True
    return any(lowered.startswith(prefix) or f"_{prefix}" in lowered for prefix in prefixes)


def looks_like_measure(name: str) -> bool:
    """Whether a column name says it holds something additive."""
    lowered = name.lower()
    if lowered.endswith(NON_MEASURE_ENDINGS):
        return False
    return bool(MEASURE_WORDS.intersection(lowered.split("_")))


def article(word: str) -> str:
    """``a`` or ``an``, so consequence lines read properly."""
    return "an" if word[:1].lower() in "aeiou" else "a"


#: String-ish types that describe rather than measure.
TEXT_TYPES = frozenset({"string", "varchar", "text", "char", "bytes"})


@dataclass(frozen=True)
class Shape:
    """What a model's columns say about it."""

    primary_keys: int = 0
    foreign_keys: int = 0
    natural_keys: int = 0
    measures: int = 0
    measure_names: tuple[str, ...] = ()
    dates: int = 0
    booleans: int = 0
    attributes: int = 0
    total: int = 0
    typed_columns: int = 0

    @property
    def types_available(self) -> bool:
        """Whether column types were known for most columns.

        Data types live in ``catalog.json``, which ``dbt docs generate``
        produces. A manifest alone carries almost none, so the inference rests
        on naming and says so.
        """
        return self.total > 0 and self.typed_columns >= self.total * 0.5

    @property
    def described(self) -> str:
        """Plain summary, for the consequence line."""
        from hunter.checks.base import plural

        parts = [
            plural(self.foreign_keys, "foreign key"),
            f"{plural(self.measures, 'column')} to add up",
            f"{plural(self.attributes, 'descriptive column')}",
            "a date grain" if self.dates else "no date grain",
        ]
        summary = ", ".join(parts)
        if not self.types_available:
            summary += " (judged from names, since column types were not available)"
        return summary


def describe_shape(model: Model, naming: ColumnNamingSpec) -> Shape:
    """Classify a model's columns by the role their name and type imply."""
    primary = foreign = natural = measures = dates = booleans = attributes = 0
    measure_names: list[str] = []

    for column in model.columns:
        name = column.name.lower()
        data_type = (column.data_type or "").strip().lower()

        if name.endswith(naming.primary_key_suffix):
            primary += 1
            continue
        if name.endswith(naming.foreign_key_suffix):
            foreign += 1
            continue
        if name.endswith(naming.natural_key_suffix):
            natural += 1
            continue
        if name.endswith((naming.date_suffix, naming.timestamp_suffix)):
            dates += 1
            continue
        if looks_like_boolean(name, naming.boolean_prefixes, naming.boolean_suffixes):
            booleans += 1
            continue
        if data_type in {"bool", "boolean"}:
            booleans += 1
            continue
        if data_type in NUMERIC_TYPES or looks_like_measure(name):
            measures += 1
            measure_names.append(column.name)
            continue
        if data_type in TEXT_TYPES or not data_type:
            attributes += 1
            continue
        attributes += 1

    return Shape(
        primary_keys=primary,
        foreign_keys=foreign,
        natural_keys=natural,
        measures=measures,
        measure_names=tuple(sorted(measure_names)),
        dates=dates,
        booleans=booleans,
        attributes=attributes,
        total=len(model.columns),
        typed_columns=sum(1 for column in model.columns if column.data_type),
    )


def infer_kind(shape: Shape, spec: EntityInferenceSpec) -> tuple[EntityKind, float]:
    """Behavioural entity kind, with a confidence between 0 and 1.

    Confidence is the share of the signals that agree. It never reaches 1.0
    without warehouse access, because uniqueness and row counts are part of the
    evidence and neither is available from the repository alone.
    """
    if shape.total == 0:
        return EntityKind.UNKNOWN, 0.0

    scores: dict[EntityKind, int] = dict.fromkeys(EntityKind, 0)
    signals = 0

    signals += 1
    if shape.foreign_keys >= spec.fact_min_foreign_keys:
        scores[EntityKind.FACT] += 1
        scores[EntityKind.AGGREGATE] += 1
        scores[EntityKind.BRIDGE] += 1
    elif shape.foreign_keys <= spec.dimension_max_foreign_keys:
        scores[EntityKind.DIMENSION] += 1

    signals += 1
    if shape.measures >= spec.aggregate_min_measures:
        scores[EntityKind.AGGREGATE] += 1
        scores[EntityKind.FACT] += 1
    elif shape.measures >= spec.fact_min_measures:
        scores[EntityKind.FACT] += 1
    else:
        scores[EntityKind.DIMENSION] += 1
        scores[EntityKind.BRIDGE] += 1

    signals += 1
    if shape.dates:
        scores[EntityKind.FACT] += 1
        scores[EntityKind.AGGREGATE] += 1
    else:
        scores[EntityKind.DIMENSION] += 1
        scores[EntityKind.BRIDGE] += 1

    signals += 1
    if shape.attributes >= spec.dimension_min_attributes:
        scores[EntityKind.DIMENSION] += 1
    else:
        scores[EntityKind.BRIDGE] += 1
        scores[EntityKind.FACT] += 1

    best = max(scores.items(), key=lambda item: (item[1], item[0].value))
    if best[1] == 0:
        return EntityKind.UNKNOWN, 0.0

    runners_up = sorted(scores.values(), reverse=True)
    margin = best[1] - (runners_up[1] if len(runners_up) > 1 else 0)
    # A clean sweep with a clear margin is the most Hunter will claim without
    # warehouse evidence: 0.85, not 1.0. Without column types it claims less
    # still, because half the evidence is then naming convention.
    ceiling = 0.85 if shape.types_available else 0.65
    confidence = min(ceiling, (best[1] / signals) * (0.6 + 0.4 * min(1.0, margin / 2)))
    return best[0], round(confidence, 2)


#: Kinds that are close enough not to be worth reporting as a mismatch.
COMPATIBLE: dict[EntityKind, frozenset[EntityKind]] = {
    EntityKind.FACT: frozenset({EntityKind.FACT, EntityKind.AGGREGATE}),
    EntityKind.AGGREGATE: frozenset({EntityKind.AGGREGATE, EntityKind.FACT}),
    EntityKind.DIMENSION: frozenset({EntityKind.DIMENSION}),
    EntityKind.BRIDGE: frozenset({EntityKind.BRIDGE, EntityKind.FACT}),
    EntityKind.SNAPSHOT: frozenset({EntityKind.SNAPSHOT, EntityKind.DIMENSION}),
}


def run(context: CheckContext) -> Findings:
    """Compare each model's declared entity type against how it behaves."""
    findings = Findings()
    naming = context.config.column_naming
    spec = context.config.entity_inference

    for model in context.project.sorted_models():
        if not model.is_scoreable or not model.columns:
            continue
        layer = context.config.layer(model.layer) if model.layer else None
        if layer is None or not layer.expected_entity_kinds:
            continue

        declared = model.entity_kind_declared
        if declared is EntityKind.UNKNOWN:
            # Reported by the naming check; nothing to compare against here.
            continue

        shape = describe_shape(model, naming)
        inferred, confidence = infer_kind(shape, spec)
        model.entity_kind_inferred = inferred
        model.inference_confidence = confidence

        entity_spec = context.config.entity(declared)

        if entity_spec is not None and entity_spec.requires_surrogate_key:
            context.examine(SURROGATE_KEY_MISSING.id, model.name)
            if shape.primary_keys == 0:
                findings.add(
                    context.finding(
                        SURROGATE_KEY_MISSING.id,
                        subject=model.name,
                        file=model.path,
                        evidence={
                            "declared": str(declared),
                            "declared_article": article(str(declared)),
                        },
                    )
                )

        specific_finding = False

        if declared is EntityKind.FACT:
            context.examine(FACT_WITHOUT_MEASURES.id, model.name)
            if shape.measures == 0:
                specific_finding = True
                findings.add(
                    context.finding(
                        FACT_WITHOUT_MEASURES.id,
                        subject=model.name,
                        file=model.path,
                        evidence={"shape": shape.described},
                    )
                )

        if declared is EntityKind.DIMENSION and shape.measures:
            context.examine(DIMENSION_WITH_MEASURES.id, model.name)
            specific_finding = True
            findings.add(
                context.finding(
                    DIMENSION_WITH_MEASURES.id,
                    subject=model.name,
                    file=model.path,
                    points_scale=min(1.0, shape.measures / max(1, shape.total)) or 1.0,
                    evidence={
                        "count": shape.measures,
                        "phrase": plural(shape.measures, "numeric column"),
                        "columns": ", ".join(shape.measure_names[:6]),
                    },
                )
            )

        context.examine(TYPE_MISMATCH.id, model.name)
        if inferred is EntityKind.UNKNOWN:
            continue

        compatible = COMPATIBLE.get(declared, frozenset({declared}))
        if inferred in compatible:
            continue

        # A specific rule has already named the same observation in plainer
        # terms. Reporting the general mismatch as well would count one problem
        # twice and read as two.
        if specific_finding:
            continue

        rule_id = (
            TYPE_MISMATCH.id if confidence >= spec.min_confidence_to_score else TYPE_UNCLEAR.id
        )
        findings.add(
            context.finding(
                rule_id,
                subject=model.name,
                file=model.path,
                confidence=confidence,
                evidence={
                    "declared": str(declared),
                    "declared_article": article(str(declared)),
                    "inferred": str(inferred),
                    "inferred_article": article(str(inferred)),
                    "evidence_text": shape.described,
                },
            )
        )

    return findings
