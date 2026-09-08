"""SQL structure: shape, size, and references that bypass dbt.

FR2.3 and FR2.6. This reads the model SQL as the manifest recorded it, not the
file on disk, so the finding always matches the manifest the score was computed
from.

The analysis is deliberately shallow. It removes comments, replaces every Jinja
expression with a marker, and then looks at what is left. That is enough to find
a hardcoded table reference, a star select, a model that has grown too long and
a query with too many joins. It is not a SQL parser and does not pretend to be:
FR2.7 says wrap sqlfluff rather than reimplement it, and that wrapping is
milestone work.
"""

from __future__ import annotations

import re

from hunter.checks.base import CheckContext, Findings, plural, rule
from hunter.enums import Dimension, Severity

# Low, not medium. A source column rename changes this model's shape, but
# downstream models select named columns and so fail loudly at build time
# rather than producing quiet wrong numbers. Compare the hardcoded-reference
# rule below, where nothing warns at all. A project that wants this stricter
# reweights it in hunter.yml, and the divergence report records that it did.
SELECT_STAR = rule(
    "structure.select_star_from_source",
    dimension=Dimension.CONVENTIONS_STRUCTURE,
    severity=Severity.LOW,
    points=0.3,
    title="{subject} selects every column from {target} on line {line}",
    consequence=(
        "A column added at the source appears in {label} without anyone deciding to "
        "take it, and a renamed one disappears. Reports built on it change shape "
        "with no change made here."
    ),
    plain_heading="How the code is written",
)

HARDCODED_REFERENCE = rule(
    "structure.hardcoded_reference",
    dimension=Dimension.CONVENTIONS_STRUCTURE,
    severity=Severity.HIGH,
    points=1.5,
    title="{subject} names the table {reference!r} directly on line {line}",
    consequence=(
        "Because {label} does not go through dbt to reach this table, the dependency "
        "is invisible: it does not appear in the lineage, it is not built in the "
        "right order, and nothing warns you if the table it points at changes."
    ),
    plain_heading="How the code is written",
)

MODEL_TOO_LONG = rule(
    "structure.model_too_long",
    dimension=Dimension.CONVENTIONS_STRUCTURE,
    severity=Severity.LOW,
    points=0.6,
    title="{subject} is {lines} lines, over the {limit} line ceiling",
    consequence=(
        "{label} is long enough that reviewing a change to it is hard, so mistakes "
        "get through. It is a candidate for splitting into steps."
    ),
    plain_heading="How the code is written",
    exposure_weighted=False,
)

TOO_MANY_JOINS = rule(
    "structure.too_many_joins",
    dimension=Dimension.CONVENTIONS_STRUCTURE,
    severity=Severity.MEDIUM,
    points=0.8,
    title="{subject} has {joins} joins, over the {limit} join ceiling",
    consequence=(
        "With {joins} joins in one query, a single wrong join condition in {label} "
        "can quietly multiply rows and inflate every figure built on it."
    ),
    plain_heading="How the code is written",
)

CTE_NAME_INVALID = rule(
    "structure.cte_name_invalid",
    dimension=Dimension.CONVENTIONS_STRUCTURE,
    severity=Severity.LOW,
    points=0.3,
    title="{phrase} in {subject} do not match the naming pattern: {names}",
    consequence=(
        "The intermediate steps inside {label} are named inconsistently, which makes "
        "the query harder to follow than it needs to be."
    ),
    plain_heading="How the code is written",
    exposure_weighted=False,
)

#: Jinja is replaced by markers rather than removed, and ``ref`` and ``source``
#: get distinct ones. The difference matters: selecting every column from your
#: own model is ordinary dbt style, while selecting every column from a raw
#: source lets an upstream schema change through untouched.
REF_MARKER = "\x00ref\x00"
SOURCE_MARKER = "\x00source\x00"
JINJA_MARKER = "\x00jinja\x00"

_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_JINJA = re.compile(r"\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\}", re.DOTALL)
_STAR = re.compile(
    r"\bselect\s+(?:distinct\s+)?(?P<form>\*|[A-Za-z_][A-Za-z0-9_]*\.\*)"
    r"(?P<between>(?:\s|\bexcept\s*\([^)]*\)|\breplace\s*\([^)]*\))*)"
    r"from\s+(?P<target>`[^`]+`|\x00\w+\x00|[A-Za-z_][A-Za-z0-9_.]*)",
    re.I,
)

#: SQL where ``from`` is not a FROM clause: ``is distinct from``,
#: ``extract(day from x)``, ``trim(both 'x' from y)``.
_NOT_A_FROM_CLAUSE = frozenset({"distinct", "both", "leading", "trailing"})
_EXTRACTORS = frozenset({"extract", "trim", "substring", "position", "overlay"})
_JOIN = re.compile(r"\bjoin\b", re.I)
_CTE = re.compile(r"(?:\bwith\b|,)\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s+as\s*\(", re.I)
_TABLE_REF = re.compile(
    r"\b(?:from|join)\s+(?P<ref>`[^`]+`|[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)",
    re.I,
)


def strip_noise(sql: str) -> str:
    """Remove comments and blank out Jinja, keeping line numbers intact.

    Line numbers must survive so a finding can point at a line. Each removed
    span is replaced by spaces and newlines rather than deleted.
    """

    def blank(match: re.Match[str]) -> str:
        text = match.group(0)
        return "".join("\n" if char == "\n" else " " for char in text)

    without_comments = _BLOCK_COMMENT.sub(blank, sql)
    without_comments = _LINE_COMMENT.sub(blank, without_comments)

    def marker(match: re.Match[str]) -> str:
        text = match.group(0)
        newlines = text.count("\n")
        lowered = text.lower()
        if "ref(" in lowered:
            token = REF_MARKER
        elif "source(" in lowered:
            token = SOURCE_MARKER
        else:
            token = JINJA_MARKER
        return f" {token} " + ("\n" * newlines)

    return _JINJA.sub(marker, without_comments)


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def cte_names(sql: str) -> list[str]:
    """Names of the intermediate steps in a query."""
    return [match.group("name") for match in _CTE.finditer(sql)]


def _preceding_word(sql: str, index: int) -> str:
    """The word immediately before a position, lowercased."""
    before = sql[:index].rstrip()
    match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)$", before)
    return match.group(1).lower() if match else ""


def _inside_extractor(sql: str, index: int) -> bool:
    """Whether a position sits inside ``extract(...)`` or similar.

    Those take a ``from`` that is not a FROM clause. Only the enclosing 80
    characters are considered, which is ample for one function call.
    """
    window = sql[max(0, index - 80) : index]
    depth = 0
    for position in range(len(window) - 1, -1, -1):
        char = window[position]
        if char == ")":
            depth += 1
        elif char == "(":
            if depth == 0:
                return _preceding_word(window, position) in _EXTRACTORS
            depth -= 1
    return False


def hardcoded_references(sql: str, known_ctes: set[str]) -> list[tuple[str, int]]:
    """Dotted or quoted table names reached without ``ref`` or ``source``.

    A bare name is left alone: it is almost always one of the query's own
    steps. A dotted or backquoted name is a real table somewhere, reached
    outside dbt.

    Two forms of ``from`` are not FROM clauses and are skipped: ``is distinct
    from`` and the ``from`` inside ``extract``, ``trim`` and friends.
    """
    found: list[tuple[str, int]] = []
    for match in _TABLE_REF.finditer(sql):
        keyword_start = match.start()
        if _preceding_word(sql, keyword_start) in _NOT_A_FROM_CLAUSE:
            continue
        if _inside_extractor(sql, keyword_start):
            continue
        reference = match.group("ref").strip()
        bare = reference.strip("`")
        if bare.split(".")[0].lower() in known_ctes:
            continue
        found.append((reference, line_of(sql, match.start("ref"))))
    return found


def run(context: CheckContext) -> Findings:
    """Look at the shape of each model's SQL."""
    findings = Findings()
    spec = context.config.structure

    for model in context.project.sorted_models():
        if not model.is_scoreable or not model.is_sql_model or not model.raw_code:
            continue

        sql = strip_noise(model.raw_code)
        steps = cte_names(sql)
        lowered_steps = {name.lower() for name in steps}

        if spec.forbid_select_star:
            context.examine(SELECT_STAR.id, model.name)
            for match in _STAR.finditer(sql):
                target = match.group("target")
                if target == REF_MARKER or target.lower() in lowered_steps:
                    # Selecting every column from your own model, or from one of
                    # this query's own steps, is ordinary dbt style.
                    continue
                if target == JINJA_MARKER:
                    continue
                described = "a raw source" if target == SOURCE_MARKER else f"{target!r}"
                findings.add(
                    context.finding(
                        SELECT_STAR.id,
                        subject=model.name,
                        file=model.path,
                        line=line_of(sql, match.start()),
                        evidence={
                            "form": match.group("form"),
                            "target": described,
                            "line": line_of(sql, match.start()),
                        },
                    )
                )
                break

        if spec.forbid_hardcoded_refs:
            context.examine(HARDCODED_REFERENCE.id, model.name)
            for reference, line in hardcoded_references(sql, lowered_steps):
                findings.add(
                    context.finding(
                        HARDCODED_REFERENCE.id,
                        subject=model.name,
                        file=model.path,
                        line=line,
                        evidence={"reference": reference, "line": line},
                    )
                )

        context.examine(MODEL_TOO_LONG.id, model.name)
        lines = model.raw_code.count("\n") + 1
        if lines > spec.max_model_lines:
            findings.add(
                context.finding(
                    MODEL_TOO_LONG.id,
                    subject=model.name,
                    file=model.path,
                    evidence={"lines": lines, "limit": spec.max_model_lines},
                )
            )

        context.examine(TOO_MANY_JOINS.id, model.name)
        joins = len(_JOIN.findall(sql))
        if joins > spec.max_joins:
            findings.add(
                context.finding(
                    TOO_MANY_JOINS.id,
                    subject=model.name,
                    file=model.path,
                    evidence={"joins": joins, "limit": spec.max_joins},
                )
            )

        if steps:
            context.examine(CTE_NAME_INVALID.id, model.name)
            pattern = re.compile(spec.cte_name_pattern)
            invalid = [name for name in steps if not pattern.match(name)]
            if invalid:
                findings.add(
                    context.finding(
                        CTE_NAME_INVALID.id,
                        subject=model.name,
                        file=model.path,
                        points_scale=len(invalid) / len(steps),
                        evidence={
                            "count": len(invalid),
                            "phrase": plural(len(invalid), "step name"),
                            "names": ", ".join(sorted(set(invalid))[:8]),
                            "pattern": spec.cte_name_pattern,
                        },
                    )
                )

    return findings
