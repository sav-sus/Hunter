"""The plain-language layer.

F14. Two audiences read the same pages, so every page carries plain language
above the technical detail rather than in a separate mode a non-technical reader
will never find.

Everything here is a template filled from a computed finding. Nothing is
generated. FR14.2 requires every consequence line to trace back to a
deterministic finding, and the way to guarantee that is to have no path by which
prose could appear without one.
"""

from __future__ import annotations

from dataclasses import dataclass

from hunter.enums import ALIGNMENT_STATE_LABELS, AlignmentState, Dimension, Severity
from hunter.model.findings import ScoreResult
from hunter.run import RunResult

#: What each dimension is called on the site, in plain words. FR14.5.
DIMENSION_HEADINGS: dict[Dimension, str] = {
    Dimension.TESTING: "What is checked automatically",
    Dimension.MODEL_CONFORMANCE: "Does what was built match the design",
    Dimension.LINEAGE_HEALTH: "How the tables fit together",
    Dimension.DOCUMENTATION: "What is written down",
    Dimension.CROSS_LAYER_SYNC: "Do the reports still match the data",
    Dimension.CONVENTIONS_STRUCTURE: "Are the house rules followed",
    Dimension.ENTITY_MODELLING: "Are the tables the shape they claim",
    Dimension.PERFORMANCE_COST: "What it costs to run",
}

#: One sentence on what each dimension measures.
DIMENSION_EXPLANATIONS: dict[Dimension, str] = {
    Dimension.TESTING: (
        "Whether anything would notice if the data went wrong. A test that only "
        "checks a column is not empty does not count as checking a key."
    ),
    Dimension.MODEL_CONFORMANCE: (
        "Whether the tables that exist are the tables that were designed, with the "
        "columns, keys and relationships the design specifies."
    ),
    Dimension.LINEAGE_HEALTH: (
        "Whether the tables depend on each other in ways that are safe to change, "
        "and whether anything is being built that nobody reads."
    ),
    Dimension.DOCUMENTATION: (
        "Whether someone new could tell what each table is for, what one row of it "
        "means, and who to ask about it."
    ),
    Dimension.CROSS_LAYER_SYNC: (
        "Whether the reporting layer still matches the data underneath it. This is "
        "what catches a renamed column before it breaks a dashboard."
    ),
    Dimension.CONVENTIONS_STRUCTURE: (
        "Whether the naming and the layering follow the agreed house rules, so "
        "anyone reading a query can tell what they are looking at."
    ),
    Dimension.ENTITY_MODELLING: (
        "Whether a table named as something you count behaves like something you "
        "count. Getting this wrong is how figures get double counted."
    ),
    Dimension.PERFORMANCE_COST: (
        "What the warehouse spends running this, and whether any of that spend "
        "produces something nobody uses."
    ),
}

#: FR14.4. Every term the site uses, defined. Linked from first use on a page.
GLOSSARY: dict[str, str] = {
    "aggregate table": (
        "A table holding figures already added up to a chosen level, such as one "
        "row per store per day. Faster to report from than working it out each time."
    ),
    "business model": (
        "The list of things the business needs the warehouse to hold, in business "
        "language and before anyone decides how to build them. Also called the "
        "conceptual model."
    ),
    "column": "One field in a table, such as the order date or the amount.",
    "design": (
        "The written specification of a table: its columns, its keys, what one row "
        "means and how it links to other tables. Held in files the team edits."
    ),
    "dimension": (
        "A table that describes things rather than counts them: stores, products, "
        "customers. You join to it to put labels on figures."
    ),
    "exposure": (
        "A note in the project recording that something outside it, usually a "
        "dashboard, depends on a particular table. Without it, nobody changing the "
        "table can see what they would break."
    ),
    "fact table": (
        "A table holding things that happened, one row per event or transaction, "
        "with figures you would add up."
    ),
    "foreign key": (
        "A column that points at a row in another table, such as the store a sale happened in."
    ),
    "grain": (
        "What one row of a table represents, for example one row per order, or one "
        "row per store per day. Getting this wrong is the usual cause of figures "
        "being counted twice."
    ),
    "layer": (
        "A stage in the pipeline. Data usually moves through staging (raw, tidied "
        "up), integration (combined) and warehouse (finished and ready to report "
        "from)."
    ),
    "lineage": (
        "Which tables feed which. Knowing it is what makes it possible to say what "
        "a change would affect before making it."
    ),
    "model": (
        "One table or view built by the project, defined by a file of SQL. The dbt "
        "word for it, used throughout."
    ),
    "primary key": (
        "The column that identifies a row uniquely. If it repeats, the table holds "
        "duplicates and figures built on it come out too high."
    ),
    "relationship test": (
        "A check that every reference from one table to another points at a row "
        "that exists. Where it does not, rows quietly disappear from joins."
    ),
    "semantic layer": (
        "The layer that turns warehouse tables into things a report can use: named "
        "measures, dimensions and explores. LookML here."
    ),
    "source": (
        "A table Hunter's project reads but does not build, arriving from a system outside it."
    ),
    "temporary model": (
        "A table or view built as a working step on the way to something else, and "
        "not meant to be relied on or reported from directly."
    ),
    "test": (
        "An automatic check that runs with the build and fails it when the data "
        "does not hold, such as a key repeating or a reference not resolving."
    ),
    "view": (
        "A saved query that runs each time it is read, rather than a stored table. "
        "Cheaper to store and slower to read."
    ),
}


@dataclass(frozen=True)
class OverviewPoint:
    """One line on the overview page, with the number behind it."""

    heading: str
    detail: str
    figure: str | None = None


def score_sentence(score: ScoreResult) -> str:
    """The three sentences of context under the headline number. FR14.1."""
    scored = len(score.dimensions_scored)
    total = scored + len(score.dimensions_skipped)
    parts = [f"This repository scores {score.total:g} out of 100. {score.interpretation}."]
    if score.weights_renormalised:
        parts.append(
            f"The score covers {scored} of {total} areas: the rest could not be "
            "measured with the information available, and are listed as not checked "
            "rather than counted as passing."
        )
    else:
        parts.append(f"All {total} areas were measured.")

    if score.baseline is not None and score.real_delta is not None:
        if score.real_delta > 0:
            parts.append(
                f"It has risen {score.real_delta:g} points since the agreed starting point."
            )
        elif score.real_delta < 0:
            parts.append(
                f"It has fallen {abs(score.real_delta):g} points since the agreed starting point."
            )
        else:
            parts.append("It has not moved since the agreed starting point.")
    else:
        parts.append(
            "There is no agreed starting point recorded yet, so there is nothing to "
            "compare this against."
        )
    return " ".join(parts)


def being_worked_on(result: RunResult, limit: int = 3) -> list[OverviewPoint]:
    """Three things going well, so the page is not only a list of faults. FR14.1."""
    points: list[OverviewPoint] = []
    coverage = result.alignment.coverage

    if coverage.delivery_coverage is not None:
        points.append(
            OverviewPoint(
                heading="How much of the design is built",
                detail=(
                    f"{coverage.designed_and_built} of {coverage.designed_entities} "
                    "designed tables exist."
                ),
                figure=f"{coverage.delivery_coverage:g}%",
            )
        )
    if coverage.column_documentation_coverage is not None:
        points.append(
            OverviewPoint(
                heading="How much is explained column by column",
                detail=(
                    f"{coverage.column_documented_entities} of "
                    f"{coverage.built_entities} tables have every column described."
                ),
                figure=f"{coverage.column_documentation_coverage:g}%",
            )
        )
    if coverage.test_coverage is not None:
        points.append(
            OverviewPoint(
                heading="How much is checked automatically",
                detail=(
                    f"{coverage.tested_entities} of {coverage.built_entities} tables "
                    "have their key checked."
                ),
                figure=f"{coverage.test_coverage:g}%",
            )
        )

    best = sorted(
        (entry for entry in result.score.dimensions if entry.scored),
        key=lambda entry: -entry.score,
    )
    for entry in best[:limit]:
        if entry.score < 90:
            break
        points.append(
            OverviewPoint(
                heading=DIMENSION_HEADINGS[entry.dimension],
                detail=DIMENSION_EXPLANATIONS[entry.dimension],
                figure=f"{entry.score:g}",
            )
        )
    return points[:limit]


def needs_a_decision(result: RunResult, limit: int = 3) -> list[OverviewPoint]:
    """Three things needing someone to decide, not just to fix. FR14.1.

    Drawn from the systemic gaps and the alignment states, because those are the
    ones where the answer is a decision rather than a task: nobody has agreed
    who owns the warehouse tables, or whether the off-plan tables should be in
    the design.
    """
    points: list[OverviewPoint] = []

    # Only gaps that are somebody's decision. A low-severity gap is a tidy-up
    # task, and an informational rule such as "Hunter could not check this" is
    # neither a gap nor a decision.
    decidable = [
        gap
        for gap in result.score.systemic_gaps
        if gap.severity in {Severity.HIGH, Severity.MEDIUM}
    ]
    for gap in decidable[:limit]:
        points.append(
            OverviewPoint(
                heading=gap.plain_heading or DIMENSION_HEADINGS[gap.dimension],
                detail=(
                    f"Missing everywhere Hunter looked, in all {gap.checked} cases. "
                    f"{gap.consequence}"
                ),
                figure=f"0 of {gap.checked}",
            )
        )

    off_plan = result.alignment.by_state(AlignmentState.BUILT_OFF_PLAN)
    if off_plan and len(points) < limit:
        names = ", ".join(sorted(row.label for row in off_plan)[:3])
        points.append(
            OverviewPoint(
                heading="Tables built without a design",
                detail=(
                    f"These exist in production and appear on no design: {names}"
                    f"{' and others' if len(off_plan) > 3 else ''}. Either they belong "
                    "in the design or they should be retired."
                ),
                figure=str(len(off_plan)),
            )
        )

    stale = result.alignment.stale_claims()
    if stale and len(points) < limit:
        points.append(
            OverviewPoint(
                heading="The published picture is out of date",
                detail=(
                    f"{len(stale)} entities on the business model diagram are shown "
                    "in a state they are not in. Anyone reading it is being told "
                    "something untrue."
                ),
                figure=str(len(stale)),
            )
        )

    return points[:limit]


def top_fixes(result: RunResult, limit: int = 10) -> list[dict[str, object]]:
    """The findings worth doing first. FR8.2.

    Ranked by points recoverable per finding, high severity first, so the list
    is ordered by what it buys rather than by what is easiest to type.
    """
    from hunter.enums import SEVERITY_ORDER

    grouped: dict[str, list] = {}
    for finding in result.open_findings:
        if finding.points <= 0:
            continue
        grouped.setdefault(finding.rule, []).append(finding)

    rows: list[dict[str, object]] = []
    for rule_id, findings in grouped.items():
        recoverable = sum(item.effective_points for item in findings)
        example = findings[0]
        rows.append(
            {
                "rule": rule_id,
                "severity": str(example.severity),
                "count": len(findings),
                "points_recoverable": round(recoverable, 1),
                "heading": example.summary,
                "consequence": example.consequence,
                "objects": sorted({item.subject for item in findings})[:5],
                "_order": (
                    SEVERITY_ORDER[example.severity],
                    -recoverable,
                    rule_id,
                ),
            }
        )

    rows.sort(key=lambda row: row["_order"])  # type: ignore[arg-type,return-value]
    for row in rows:
        del row["_order"]
    return rows[:limit]


def severity_label(severity: Severity) -> str:
    """Severity in words rather than a level. FR14.5."""
    return {
        Severity.HIGH: "Needs attention",
        Severity.MEDIUM: "Worth fixing",
        Severity.LOW: "Tidy up",
        Severity.INFO: "For information",
    }[severity]


def state_summary(result: RunResult) -> list[tuple[str, int, str]]:
    """The reconciliation counts, in reading order. FR17.5."""
    from hunter.enums import ALIGNMENT_STATE_MEANINGS

    order = [
        AlignmentState.DESIGNED_AND_DELIVERED,
        AlignmentState.BUILT_NOT_DEPLOYED,
        AlignmentState.BUILT_DISABLED,
        AlignmentState.APPROVED_OFF_PLAN,
        AlignmentState.BUILT_OFF_PLAN,
        AlignmentState.OFF_PLAN_NOT_DEPLOYED,
        AlignmentState.DESIGNED_NOT_STARTED,
        AlignmentState.CONCEPTUAL_ONLY,
        AlignmentState.LOGICAL_ONLY,
        AlignmentState.LIVE_WITHOUT_CODE,
        AlignmentState.UNTRACKED_TABLE,
        AlignmentState.NOT_PRESENT,
    ]
    counts = result.alignment.state_counts()
    return [
        (ALIGNMENT_STATE_LABELS[state], counts[state], ALIGNMENT_STATE_MEANINGS[state])
        for state in order
        if counts.get(state)
    ]


def glossary_terms(text: str) -> list[str]:
    """Glossary terms appearing in a piece of text, for linking on first use."""
    lowered = text.lower()
    return sorted(term for term in GLOSSARY if term in lowered)
