"""Is it tested, and do the tests prove anything?

The distinction this module rests on: what a test proves matters more than how
many tests exist. The pilot repository has 3,926 tests, of which 3,492 are
``at_least_one`` (the column is not entirely null) and 100 are uniqueness tests.
Counting tests would score it well while its keys go largely unverified.

So ``at_least_one`` is recorded as coverage and never credited as key cover, and
the rules here ask three questions instead of one:

* Does the primary key have a uniqueness test and a not-null test?
* Does every foreign key have a relationship test proving it resolves?
* Does anything cover the grain the design declares?

Test coverage is weighted by downstream exposure, per FR7.4: a missing key test
on a model feeding 12 report fields costs more than the same gap on an orphan.
"""

from __future__ import annotations

from hunter.checks.base import REQ_DBML, REQ_MANIFEST, CheckContext, Findings, plural, rule
from hunter.config.schema import ColumnNamingSpec
from hunter.enums import Dimension, EntityKind, Severity
from hunter.model.entities import DbtTest, Model

KEY_UNIQUENESS_MISSING = rule(
    "testing.key_uniqueness_missing",
    dimension=Dimension.TESTING,
    severity=Severity.HIGH,
    points=2.0,
    title="Nothing tests that {key} is unique on {subject}",
    consequence=(
        "Nothing checks that {label} holds one row per {grain}. If duplicates "
        "appear, every total built from it is overstated and nobody is told. "
        "{consumers}."
    ),
    plain_heading="What is tested",
)

KEY_NOT_NULL_MISSING = rule(
    "testing.key_not_null_missing",
    dimension=Dimension.TESTING,
    severity=Severity.HIGH,
    points=1.5,
    title="Nothing tests that {key} is always populated on {subject}",
    consequence=(
        "Rows with no key can appear in {label}. They drop out of joins silently, "
        "so figures come out low with no error to explain why."
    ),
    plain_heading="What is tested",
)

RELATIONSHIP_TEST_MISSING = rule(
    "testing.relationship_test_missing",
    dimension=Dimension.TESTING,
    severity=Severity.MEDIUM,
    points=1.0,
    title="{phrase} on {subject} have no relationship test: {columns}",
    consequence=(
        "Nothing checks that these references in {label} point at rows that exist. "
        "Where they do not, joined figures come out low and the rows simply vanish."
    ),
    plain_heading="Keys and joins",
)

NO_TESTS_AT_ALL = rule(
    "testing.no_tests_at_all",
    dimension=Dimension.TESTING,
    severity=Severity.HIGH,
    points=2.0,
    title="{subject} has no tests of any kind",
    consequence=(
        "Nothing at all checks {label}. Any problem in it reaches whoever reads the "
        "numbers before anyone who could fix it, and {consumers}."
    ),
    plain_heading="What is tested",
)

ONLY_WEAK_TESTS = rule(
    "testing.only_weak_tests",
    dimension=Dimension.TESTING,
    severity=Severity.MEDIUM,
    points=1.0,
    title="{subject} has {phrase} but none of them prove a key",
    consequence=(
        "The tests on {label} check that columns are not entirely empty. None of "
        "them check that it has one row per thing, or that its references resolve."
    ),
    plain_heading="What is tested",
)

DECLARED_GRAIN_UNTESTED = rule(
    "testing.declared_grain_untested",
    dimension=Dimension.TESTING,
    severity=Severity.MEDIUM,
    points=1.2,
    title="The declared grain of {subject} is not tested",
    consequence=(
        "The design says {label} holds {grain}, and nothing checks that it does. If "
        "the grain is wrong, figures double-count with no test to catch it."
    ),
    plain_heading="What one row means",
    requires=(REQ_MANIFEST, REQ_DBML),
)

WARN_ONLY_KEY_TEST = rule(
    "testing.key_test_warns_only",
    dimension=Dimension.TESTING,
    severity=Severity.MEDIUM,
    points=0.8,
    title="The key tests on {subject} are set to warn, so they never fail a build",
    consequence=(
        "The uniqueness check on {label} reports a problem but lets the build carry "
        "on, so bad data reaches reports anyway. Someone has to be watching the log."
    ),
    plain_heading="What is tested",
)

#: Entity kinds whose keys Hunter expects to be tested.
KEYED_KINDS = frozenset(
    {EntityKind.FACT, EntityKind.DIMENSION, EntityKind.AGGREGATE, EntityKind.BRIDGE}
)


def _grain_phrase(context: CheckContext, model: Model) -> str:
    """Plain phrase for what one row should be, for the consequence line."""
    for row in context.alignment.rows:
        if row.model_name == model.name and row.grain:
            return row.grain.rstrip(".").lower()
    entry = context.register.entry(model.name)
    if entry and entry.grain:
        return entry.grain.rstrip(".").lower()
    return "thing"


def _primary_key_columns(context: CheckContext, model: Model) -> list[str]:
    """Key columns, from the design if it says, otherwise from the naming."""
    suffix = context.config.column_naming.primary_key_suffix
    for row in context.alignment.rows:
        if row.model_name != model.name or row.designed_name is None:
            continue
        design = context.project.designed.get(row.designed_name)
        if design and design.primary_key_columns:
            declared = [
                name for name in design.primary_key_columns if model.column(name) is not None
            ]
            if declared:
                return sorted(declared)
    return sorted(column.name for column in model.columns if column.name.lower().endswith(suffix))


def run(context: CheckContext) -> Findings:
    """Check what the tests actually prove."""
    findings = Findings()
    naming = context.config.column_naming
    spec = context.config.testing

    for model in context.project.sorted_models():
        if not model.is_scoreable or model.is_seed:
            continue
        layer = context.config.layer(model.layer) if model.layer else None
        if layer is None:
            continue

        tests = context.project.tests_for(model.name)
        consumers = context.consumer_summary(model.name)
        grain = _grain_phrase(context, model)

        if layer.in_alignment:
            context.examine(NO_TESTS_AT_ALL.id, model.name)
            if not tests:
                findings.add(
                    context.finding(
                        NO_TESTS_AT_ALL.id,
                        subject=model.name,
                        file=model.path,
                        evidence={"consumers": consumers, "grain": grain},
                    )
                )
                continue

            context.examine(ONLY_WEAK_TESTS.id, model.name)
            if tests and not any(test.is_key_test or test.is_relationship_test for test in tests):
                findings.add(
                    context.finding(
                        ONLY_WEAK_TESTS.id,
                        subject=model.name,
                        file=model.path,
                        evidence={
                            "count": len(tests),
                            "phrase": plural(len(tests), "test"),
                            "consumers": consumers,
                        },
                    )
                )

        if layer.requires_key_tests and model.entity_kind_declared in KEYED_KINDS:
            findings.extend(_key_tests(context, model, tests, consumers, grain))

        if spec.require_relationship_test_per_foreign_key and layer.in_alignment:
            findings.extend(_relationship_tests(context, model, tests, naming))

        if spec.require_unique_test_on_declared_grain and context.has(REQ_DBML):
            findings.extend(_grain_test(context, model, tests, grain))

    return findings


def _key_tests(
    context: CheckContext,
    model: Model,
    tests: list[DbtTest],
    consumers: str,
    grain: str,
) -> Findings:
    findings = Findings()
    keys = _primary_key_columns(context, model)
    if not keys:
        # The missing key column itself is reported by the naming check. Testing
        # a column that does not exist is not a separate failure.
        return findings

    key_label = ", ".join(keys)
    unique_columns = {
        test.column.lower() for test in tests if test.kind == "unique" and test.column
    }
    not_null_columns = {
        test.column.lower() for test in tests if test.kind == "not_null" and test.column
    }
    # A composite uniqueness test names no single column, so treat a
    # model-level uniqueness test as covering the declared key.
    model_level_unique = any(test.kind == "unique" and not test.column for test in tests)

    context.examine(KEY_UNIQUENESS_MISSING.id, model.name)
    covered = model_level_unique or any(key.lower() in unique_columns for key in keys)
    if not covered:
        findings.add(
            context.finding(
                KEY_UNIQUENESS_MISSING.id,
                subject=model.name,
                file=model.path,
                evidence={"key": key_label, "consumers": consumers, "grain": grain},
            )
        )
    else:
        context.examine(WARN_ONLY_KEY_TEST.id, model.name)
        enforcing = [test for test in tests if test.kind == "unique" and test.is_enforced]
        if not enforcing:
            findings.add(
                context.finding(
                    WARN_ONLY_KEY_TEST.id,
                    subject=model.name,
                    file=model.path,
                    evidence={"key": key_label},
                )
            )

    context.examine(KEY_NOT_NULL_MISSING.id, model.name)
    if not any(key.lower() in not_null_columns for key in keys):
        findings.add(
            context.finding(
                KEY_NOT_NULL_MISSING.id,
                subject=model.name,
                file=model.path,
                evidence={"key": key_label, "consumers": consumers},
            )
        )
    return findings


def _relationship_tests(
    context: CheckContext, model: Model, tests: list[DbtTest], naming: ColumnNamingSpec
) -> Findings:
    foreign_keys = [
        column.name
        for column in model.columns
        if column.name.lower().endswith(naming.foreign_key_suffix)
    ]
    if not foreign_keys:
        return Findings()

    context.examine(RELATIONSHIP_TEST_MISSING.id, model.name)
    tested = {test.column.lower() for test in tests if test.is_relationship_test and test.column}
    untested = [name for name in foreign_keys if name.lower() not in tested]
    if not untested:
        return Findings()

    finding = context.finding(
        RELATIONSHIP_TEST_MISSING.id,
        subject=model.name,
        file=model.path,
        points_scale=len(untested) / len(foreign_keys),
        evidence={
            "count": len(untested),
            "phrase": plural(len(untested), "foreign key"),
            "total": len(foreign_keys),
            "columns": ", ".join(sorted(untested)[:8]),
        },
    )
    out = Findings()
    out.add(finding)
    return out


def _grain_test(context: CheckContext, model: Model, tests: list[DbtTest], grain: str) -> Findings:
    """Is the grain the design states actually verified?"""
    row = next((item for item in context.alignment.rows if item.model_name == model.name), None)
    if row is None or not row.grain or row.designed_name is None:
        return Findings()

    context.examine(DECLARED_GRAIN_UNTESTED.id, model.name)
    proves_grain = any(test.kind == "unique" for test in tests)
    if proves_grain:
        return Findings()

    finding = context.finding(
        DECLARED_GRAIN_UNTESTED.id,
        subject=model.name,
        file=model.path,
        evidence={"grain": grain, "design": row.designed_name},
    )
    out = Findings()
    out.add(finding)
    return out
