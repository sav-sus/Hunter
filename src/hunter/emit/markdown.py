"""The site pages.

F10, plus the data model page carrying all three levels. Pages are generated as
markdown and built by MkDocs Material.

Two rules run through all of it. Every panel carries the timestamp of the data
behind it, per F10. And no page requires reading SQL, YAML or LookML to be
understood at the summary level, per FR14.8: the plain language sits above the
detail on the same page, not in a separate mode nobody finds.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Sequence
from pathlib import Path

from hunter.brand import ASSETS
from hunter.emit import mermaid
from hunter.emit.plain import (
    DIMENSION_EXPLANATIONS,
    DIMENSION_HEADINGS,
    GLOSSARY,
    being_worked_on,
    needs_a_decision,
    score_sentence,
    severity_label,
    state_summary,
    top_fixes,
)
from hunter.enums import Persistence, Presence, Severity
from hunter.model.entities import Model
from hunter.model.findings import Finding
from hunter.run import RunResult

#: Presence values as a reader should see them in the reconciliation table.
PRESENCE_MARK: dict[Presence, str] = {
    Presence.PRESENT: "yes",
    Presence.ABSENT: "no",
    Presence.DISABLED: "switched off",
    Presence.UNKNOWN: "not checked",
}


def table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    """A markdown table. Empty rows give a plain sentence instead of a shell."""
    body = [list(row) for row in rows]
    if not body:
        return "_Nothing to show here._\n"
    lines = [
        "| " + " | ".join(str(item) for item in headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in body:
        cells = [str(cell).replace("|", "\\|").replace("\n", " ") for cell in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def timestamp(result: RunResult, what: str) -> str:
    """The data-freshness line every panel carries. F10."""
    return f"\n_{what} as at {result.as_of.isoformat()}._\n"


def mermaid_block(text: str) -> str:
    return "```mermaid\n" + text.rstrip() + "\n```\n"


def details(summary: str, body: str, *, open_by_default: bool = False) -> str:
    """A collapsed section, for detail that would otherwise bury the summary."""
    marker = " open" if open_by_default else ""
    return (
        f'\n??? note "{summary}"\n\n'
        + "\n".join(f"    {line}" if line.strip() else "" for line in body.splitlines())
        + "\n"
        if False
        else (f"\n<details{marker}>\n<summary>{summary}</summary>\n\n{body}\n</details>\n")
    )


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


def overview_page(result: RunResult) -> str:
    """The non-technical entry point. FR14.1.

    The number is the headline. The interpretation sits beneath it in its own
    panel, never in place of it, per FR7.10.
    """
    score = result.score
    out = [
        "# Repository health",
        "",
        # The dashboard is the front door. These markdown pages are the evidence
        # behind it, so every reader who lands here first gets sent there.
        "[Open the dashboard](dashboard.html){ .hunter-back }",
        "",
        f"# {score.total:g} / 100",
        "",
        f'!!! abstract "{score.interpretation}"',
        f"    Grade {score.grade}."
        + (
            f" Starting point {score.baseline:g}."
            if score.baseline is not None
            else " No starting point recorded yet."
        ),
        "",
        score_sentence(score),
        "",
    ]

    if score.systemic_gaps:
        out += [
            "## Nothing in these areas is done anywhere",
            "",
            "Each of these was checked in every place it applies, and was missing in "
            "every one. That makes each a single decision nobody has taken, rather "
            "than a list of separate faults.",
            "",
            table(
                ["What is missing", "Where", "Why it matters"],
                [
                    [
                        gap.plain_heading or str(gap.dimension),
                        f"{gap.failed} of {gap.checked}",
                        gap.consequence,
                    ]
                    for gap in score.systemic_gaps
                ],
            ),
        ]

    out += ["## What is going well", ""]
    for point in being_worked_on(result):
        out += [f"**{point.figure} — {point.heading}**", "", point.detail, ""]

    out += ["## What needs a decision", ""]
    decisions = needs_a_decision(result)
    if decisions:
        for point in decisions:
            out += [f"**{point.figure} — {point.heading}**", "", point.detail, ""]
    else:
        out += ["Nothing is waiting on a decision.", ""]

    out += [
        "## Where to look next",
        "",
        "- [What was designed against what exists](reconciliation.md) — one table "
        "showing every entity, what was designed, what was built and what is live.",
        "- [The data model](data-model.md) — the business, designed and built views "
        "of the same thing.",
        "- [The score, broken down](scorecard.md) — every number and the rule behind it.",
        "- [Words used on this site](glossary.md) — every term, defined.",
        "",
        timestamp(result, "Repository read"),
    ]
    return "\n".join(out)


def scorecard_page(result: RunResult) -> str:
    """Every number and the rule behind it. F10."""
    score = result.score
    out = [
        "# The score, broken down",
        "",
        f"# {score.total:g} / 100",
        "",
        f'!!! abstract "{score.interpretation}"',
        f"    Grade {score.grade}.",
        "",
    ]

    if score.weights_renormalised:
        skipped = [DIMENSION_HEADINGS[item] for item in score.dimensions_skipped]
        out += [
            '!!! warning "Some areas were not measured"',
            "    " + f"{len(skipped)} of {len(score.dimensions)} areas could not be measured "
            "with the information available. Their weight has been shared across the "
            "rest, so the score is still out of 100. They are not counted as passing.",
            "",
        ]

    out += [
        "## Each area",
        "",
        table(
            ["Area", "Score", "Grade", "Share of the total", "Findings"],
            [
                [
                    DIMENSION_HEADINGS[entry.dimension],
                    f"{entry.score:g}" if entry.scored else "not measured",
                    entry.grade if entry.scored else "-",
                    f"{entry.effective_weight:g}%" if entry.scored else "-",
                    entry.finding_count,
                ]
                for entry in score.dimensions
            ],
        ),
        "",
    ]

    for entry in score.dimensions:
        heading = DIMENSION_HEADINGS[entry.dimension]
        out += [f"### {heading}", "", DIMENSION_EXPLANATIONS[entry.dimension], ""]
        if entry.scored:
            out += [
                f"Scored **{entry.score:g}**, grade {entry.grade}. "
                f"{entry.points_lost:g} of {entry.points_available:g} possible "
                f"points were lost across {entry.finding_count} findings.",
                "",
            ]
        else:
            out += [f"Not measured. {entry.skipped_reason}", ""]

    if score.baseline is not None:
        out += [
            "## Movement since the starting point",
            "",
            table(
                ["Measure", "Value"],
                [
                    ["Starting point", f"{score.baseline:g}"],
                    ["Now", f"{score.total:g}"],
                    ["Change", f"{score.delta:+g}" if score.delta is not None else "-"],
                    [
                        "Of which caused by a Hunter or ruleset upgrade",
                        f"{score.version_attributed_delta:+g}"
                        if score.version_attributed_delta is not None
                        else "-",
                    ],
                    [
                        "Of which real change in the repository",
                        f"{score.real_delta:+g}" if score.real_delta is not None else "-",
                    ],
                ],
            ),
            "",
        ]

    out += [
        "## What to fix first",
        "",
        "Ranked by how much the score would recover, most serious first.",
        "",
        table(
            ["How serious", "Cases", "Points to recover", "What is wrong"],
            [
                [
                    severity_label(Severity(str(row["severity"]))),
                    row["count"],
                    row["points_recoverable"],
                    row["consequence"],
                ]
                for row in top_fixes(result, limit=10)
            ],
        ),
        "",
        "## How much is covered",
        "",
        _coverage_table(result),
        timestamp(result, "Score computed"),
    ]
    return "\n".join(out)


def _coverage_table(result: RunResult) -> str:
    coverage = result.alignment.coverage

    def percent(value: float | None) -> str:
        return "not measured" if value is None else f"{value:g}%"

    return table(
        ["Measure", "Share", "Counts"],
        [
            [
                "How much of the business model is designed",
                percent(coverage.design_coverage),
                f"{coverage.conceptual_designed} of {coverage.conceptual_entities}",
            ],
            [
                "How much of the design is built",
                percent(coverage.delivery_coverage),
                f"{coverage.designed_and_built} of {coverage.designed_entities}",
            ],
            [
                "Tables with a description",
                percent(coverage.documentation_coverage),
                f"{coverage.documented_entities} of {coverage.built_entities}",
            ],
            [
                "Tables with every column described",
                percent(coverage.column_documentation_coverage),
                f"{coverage.column_documented_entities} of {coverage.built_entities}",
            ],
            [
                "Tables with their key checked",
                percent(coverage.test_coverage),
                f"{coverage.tested_entities} of {coverage.built_entities}",
            ],
        ],
    )


def conceptual_page(result: RunResult) -> str:
    """The designated non-technical entry point. FR14.6."""
    out = [
        "# The business model",
        "",
        "What the business needs the warehouse to hold, in business language. "
        "No table names, no code.",
        "",
        "The colours show what is actually true today, worked out from the "
        "repository rather than taken from the diagram. Where the authored "
        "diagram disagrees, that is listed at the bottom of this page.",
        "",
        mermaid_block(mermaid.conceptual_diagram(result.alignment)),
        "",
        "## Every business entity",
        "",
        table(
            ["Business name", "Area", "State", "What that means", "Table behind it"],
            [
                [
                    row.label,
                    row.domain or "-",
                    row.state_label,
                    row.state_meaning,
                    row.technical_name or "not built",
                ]
                for row in result.alignment.rows
                if row.conceptual is Presence.PRESENT
            ],
        ),
        "",
    ]

    stale = result.alignment.stale_claims()
    if stale:
        out += [
            "## Where the authored diagram is out of date",
            "",
            "The diagram in the repository shows these in a state they are not in. "
            "Anyone reading it is being told something untrue.",
            "",
            table(
                ["Business name", "The diagram says", "Actually"],
                [[row.label, row.claimed_status or "-", row.state_label] for row in stale],
            ),
            "",
        ]

    out.append(timestamp(result, "Business model read"))
    return "\n".join(out)


def data_model_page(result: RunResult) -> str:
    """All three levels of the same model, side by side."""
    domains = sorted({row.domain for row in result.alignment.rows if row.domain})
    out = [
        "# The data model, at three levels",
        "",
        "The same model described three ways. Each answers a different question, "
        "and comparing them is how a gap becomes visible.",
        "",
        table(
            ["Level", "What it shows", "Who it is for"],
            [
                [
                    "Business",
                    "The things the business needs held, in business language. No columns.",
                    "Anyone",
                ],
                [
                    "Designed",
                    "The specification: columns grouped by what they are for, keys, "
                    "relationships and what one row means. No warehouse detail.",
                    "Analysts and engineers",
                ],
                [
                    "Built",
                    "What actually exists: the tables, their real columns and how they are built.",
                    "Engineers",
                ],
            ],
        ),
        "",
    ]

    for domain in domains:
        rows = [row for row in result.alignment.rows if row.domain == domain]
        out += [f"## {domain.replace('_', ' ').title()}", ""]

        out += [
            "### Business view",
            "",
            mermaid_block(
                mermaid.conceptual_diagram(result.alignment, domain=domain, include_legend=False)
            ),
        ]

        designed = mermaid.logical_diagram(result.project, result.alignment, domain=domain)
        if designed.strip() != "erDiagram":
            out += ["### Designed view", "", mermaid_block(designed)]
        else:
            out += ["### Designed view", "", "_Nothing in this area is designed yet._", ""]

        built = mermaid.physical_diagram(result.project, result.alignment, domain=domain)
        if built.strip() != "erDiagram":
            out += ["### Built view", "", mermaid_block(built)]
        else:
            out += ["### Built view", "", "_Nothing in this area is built yet._", ""]

        out += [
            "### Where the three disagree",
            "",
            table(
                ["Entity", "Business", "Designed", "Built", "State"],
                [
                    [
                        row.label,
                        PRESENCE_MARK[row.conceptual],
                        PRESENCE_MARK[row.designed],
                        PRESENCE_MARK[row.repo],
                        row.state_label,
                    ]
                    for row in rows
                ],
            ),
            "",
        ]

    out.append(timestamp(result, "Model read"))
    return "\n".join(out)


def reconciliation_page(result: RunResult) -> str:
    """The primary non-technical view. FR17.5."""
    out = [
        "# What was designed against what exists",
        "",
        "One row per entity. Read across to see whether the business asked for it, "
        "whether it was designed, whether it was built and whether it is live.",
        "",
        "## The counts",
        "",
        table(
            ["State", "Entities", "What it means"],
            [[label, count, meaning] for label, count, meaning in state_summary(result)],
        ),
        "",
    ]

    if not result.project.has_warehouse:
        out += [
            '!!! info "Production was not checked"',
            "    Hunter had no read access to the warehouse on this run, so the last "
            'column says "not checked" rather than guessing. Nothing here means a '
            "table is missing from production; it means nobody looked.",
            "",
        ]

    out += ["## Every entity", ""]
    for domain, rows in result.alignment.by_domain().items():
        out += [
            f"### {domain.replace('_', ' ').title()}",
            "",
            table(
                [
                    "Business name",
                    "Business model",
                    "Designed",
                    "Built",
                    "In production",
                    "State",
                    "One row means",
                    "Owner",
                ],
                [
                    [
                        row.label,
                        PRESENCE_MARK[row.conceptual],
                        PRESENCE_MARK[row.designed],
                        PRESENCE_MARK[row.repo],
                        PRESENCE_MARK[row.warehouse],
                        row.state_label,
                        row.grain or "not stated",
                        row.owner or "nobody named",
                    ]
                    for row in rows
                ],
            ),
            "",
        ]

    out.append(timestamp(result, "Reconciliation built"))
    return "\n".join(out)


def roadmap_page(result: RunResult) -> str:
    """Where every table is on its way from an idea to retirement. One lane each."""
    from hunter.emit.dashboard import roadmap_lanes

    lanes = roadmap_lanes(result)
    built = [item for lane in lanes for item in lane.items if item.status]
    counts = {
        word: sum(1 for item in built if item.status == word)
        for word in ("verified", "permanent", "temporary", "not determined")
    }
    out = [
        "# The roadmap",
        "",
        "Every table Hunter tracks, placed in one lane: planned, being built, live, "
        "temporary by design, being phased out, or retired. The register decides first, "
        "because a person saying a table is deprecated outranks the code saying it is "
        "live. Everything else is placed by where it sits between the design and the "
        "build.",
        "",
        "## Status at a glance",
        "",
        "Each built table carries one of three words. The fourth row is what Hunter "
        "says when it had no signal to go on.",
        "",
        table(
            ["Status", "Tables", "What it means"],
            [
                [
                    "Verified",
                    counts["verified"],
                    "meant to stay, and a named person has confirmed it",
                ],
                ["Permanent", counts["permanent"], "meant to stay, worked out from the layer"],
                [
                    "Temporary",
                    counts["temporary"],
                    "a working step, or only ever meant to run once",
                ],
                ["Not determined", counts["not determined"], "no signal to go on"],
            ],
        ),
        "",
        "## The lanes",
        "",
        table(
            ["Lane", "Tables", "What it means"],
            [[lane.title, len(lane.items), lane.meaning] for lane in lanes],
        ),
        "",
    ]
    for lane in lanes:
        out += [f"## {lane.title}", "", lane.meaning, ""]
        if not lane.items:
            out += ["Nothing here.", ""]
            continue
        out += [
            table(
                ["Entity", "Table", "Area", "Owner", "Status", "What happens next"],
                [
                    [
                        item.label,
                        f"`{item.technical_name}`" if item.technical_name else "-",
                        item.domain.replace("_", " ") or "-",
                        item.owner or "nobody named",
                        item.status or "-",
                        item.next_step,
                    ]
                    for item in lane.items
                ],
            ),
            "",
        ]
    out += [
        "## Changing where a table sits",
        "",
        "All of this is read from the register, `.hunter/register.yml`. Lifecycle status "
        "is plain information and needs no reason:",
        "",
        "```yaml",
        "models:",
        "  wh_commerce__legacy_fact:",
        "    status: deprecated          # planned, building, live, deprecated, retired",
        "    review_by: 2027-03-31       # the date it should be gone by",
        "```",
        "",
        "Marking a table verified is a confirmation, so it names the person:",
        "",
        "```yaml",
        "  wh_commerce__order_fact:",
        "    persistence: verified",
        "    verified_by: sav",
        "    reason: signed off at the design review as the order fact of record",
        "```",
        "",
        timestamp(result, "Repository read"),
    ]
    return "\n".join(out)


def physical_page(result: RunResult) -> str:
    """The model catalogue. F10."""
    models = [model for model in result.project.sorted_models() if not model.vendored]
    out = [
        "# What is built",
        "",
        f"{len(models)} tables and views are built by this project. A further "
        f"{sum(1 for m in result.project.models.values() if m.vendored)} come from "
        "installed packages and are listed but not assessed: they are not this "
        "team's code to change.",
        "",
        "## Temporary against permanent",
        "",
        "A temporary model is a working step, not something to report from. A verified",
        "model is a permanent one that a named person has confirmed should stay.",
        "",
        table(
            ["Kind", "Count", "Meaning"],
            [
                [
                    "Verified",
                    sum(1 for model in models if model.persistence is Persistence.VERIFIED),
                    "meant to stay, and somebody has checked that it should",
                ],
                [
                    "Permanent",
                    sum(1 for model in models if model.persistence is Persistence.PERSISTENT),
                    "meant to stay",
                ],
                [
                    "Temporary",
                    sum(1 for model in models if model.persistence is Persistence.TEMPORARY),
                    "a working step, or only ever meant to run once",
                ],
                [
                    "Not determined",
                    sum(1 for model in models if model.persistence is Persistence.UNKNOWN),
                    "Hunter had no signal to go on",
                ],
            ],
        ),
        "",
        "## Every table",
        "",
        table(
            [
                "Name",
                "Layer",
                "Area",
                "Built as",
                "Kind",
                "Why",
                "Columns",
                "Read by",
                "Owner",
            ],
            [
                [
                    f"[{model.name}](models/{model.name}.md)",
                    model.layer or "-",
                    model.domain or "-",
                    model.materialisation,
                    model.persistence.label,
                    str(model.persistence_signal).replace("_", " "),
                    len(model.columns),
                    len(model.downstream_models),
                    model.owner or "nobody named",
                ]
                for model in models
            ],
        ),
        timestamp(result, "Catalogue built"),
    ]
    return "\n".join(out)


def model_page(result: RunResult, model_name: str) -> str:
    """Everything known about one model. Backs ``hunter explain``."""
    model = result.project.any_model(model_name)
    if model is None:
        return f"# {model_name}\n\nThis model was not found.\n"

    row = next((item for item in result.alignment.rows if item.model_name == model_name), None)
    findings = [item for item in result.findings if item.subject == model_name]
    views = result.project.views_for_model(model_name)

    out = [
        f"# {row.label if row else model_name}",
        "",
        f"`{model_name}`",
        "",
        model.description or "_No description has been written for this table._",
        "",
        table(
            ["", ""],
            [
                ["Layer", model.layer or "not placed in a layer"],
                ["Area", model.domain or "-"],
                ["Built as", model.materialisation],
                ["Enabled", "yes" if model.enabled else "no, switched off"],
                ["Temporary, verified or permanent", model.persistence.label],
                ["Decided by", str(model.persistence_signal).replace("_", " ")],
                ["One row means", (row.grain if row and row.grain else "not stated")],
                ["Owner", model.owner or "nobody named"],
                ["Named as", str(model.entity_kind_declared)],
                [
                    "Behaves like",
                    _behaves_like(result, model),
                ],
                ["State", row.state_label if row else "-"],
                ["First written by", model.created_by or "unknown"],
                ["First written", model.created_at.isoformat() if model.created_at else "-"],
                [
                    "Last changed",
                    (model.last_modified_at.isoformat() if model.last_modified_at else "-"),
                ],
                ["File", f"`{model.path}`"],
            ],
        ),
        "",
        "## Columns",
        "",
        table(
            ["Column", "Type", "Description", "Tests"],
            [
                [
                    column.name,
                    column.data_type or "not recorded",
                    column.description or "_none_",
                    ", ".join(
                        sorted(
                            {
                                test.kind
                                for test in result.project.tests_for_column(model_name, column.name)
                            }
                        )
                    )
                    or "none",
                ]
                for column in model.columns
            ],
        ),
        "",
        "## What depends on this",
        "",
        table(
            ["What", "Count", "Names"],
            [
                [
                    "Other tables",
                    len(model.downstream_models),
                    ", ".join(model.downstream_models[:8]) or "-",
                ],
                [
                    "Report views",
                    len(views),
                    ", ".join(view.name for view in views[:8]) or "-",
                ],
            ],
        ),
        "",
        mermaid_block(mermaid.blast_radius(model_name, result.project, result.graph)),
        "",
        "## Findings",
        "",
        _findings_table(findings),
        timestamp(result, "Table read"),
    ]
    return "\n".join(out)


def _behaves_like(result: RunResult, model: Model) -> str:
    """How the columns say the table behaves, and how sure Hunter is.

    Below the confidence floor Hunter says it could not tell, rather than
    naming a type it would not score. Stating "behaves like a fact" at 0.3
    confidence reads as a finding when it is a shrug.
    """
    kind = model.entity_kind_inferred
    if kind.value == "unknown":
        return "not determined"
    floor = result.config.entity_inference.min_confidence_to_score
    if model.inference_confidence < floor:
        return (
            "not clear from its columns (closest guess "
            f"{kind}, confidence {model.inference_confidence:g}, below the "
            f"{floor:g} needed to say)"
        )
    return f"{kind} (confidence {model.inference_confidence:g})"


def _findings_table(findings: Iterable[Finding]) -> str:
    return table(
        ["How serious", "What is wrong", "Why it matters", "Where"],
        [
            [
                severity_label(finding.severity)
                + (" (silenced)" if finding.suppressed else "")
                + (" (suggestion)" if not finding.scored and not finding.suppressed else ""),
                finding.summary,
                finding.consequence,
                finding.location,
            ]
            for finding in findings
        ],
    )


def lineage_page(result: RunResult) -> str:
    """The graph, collapsed first and per-domain underneath. F5."""
    out = [
        "# How the tables fit together",
        "",
        "One box per area, with the number of tables in it. Arrows show which "
        "areas feed which, and the number on an arrow is how many dependencies "
        "it stands for.",
        "",
        mermaid_block(mermaid.collapsed_graph(result.project, result.graph)),
        "",
        "## By area",
        "",
        "Rounded boxes are working steps rather than finished tables. Grey boxes "
        "sit outside the area and are shown for context.",
        "",
    ]
    domains = sorted(
        {
            model.domain
            for model in result.project.models.values()
            if model.domain and not model.vendored
        }
    )
    for domain in domains:
        out += [
            f"### {domain.replace('_', ' ').title()}",
            "",
            mermaid_block(mermaid.domain_graph(result.project, result.graph, domain)),
            "",
        ]
    out.append(timestamp(result, "Lineage built"))
    return "\n".join(out)


def debt_page(result: RunResult) -> str:
    """Every open finding, grouped so it can be acted on. F8."""
    open_findings = result.open_findings
    out = [
        "# Everything that needs doing",
        "",
        f"{len(open_findings)} open findings, "
        f"{len(result.suggestions)} suggestions Hunter is not confident enough to "
        f"count, and {len(result.suppressed_findings)} silenced with a recorded "
        "reason.",
        "",
        "## By how serious it is",
        "",
        table(
            ["How serious", "Count"],
            [
                [
                    severity_label(severity),
                    sum(1 for item in open_findings if item.severity is severity),
                ]
                for severity in Severity
            ],
        ),
        "",
        "## By area of concern",
        "",
    ]

    by_heading: dict[str, list[Finding]] = {}
    from hunter.checks.base import REGISTRY

    for finding in open_findings:
        try:
            heading = REGISTRY.get(finding.rule).plain_heading
        except KeyError:
            heading = "Other"
        by_heading.setdefault(heading or "Other", []).append(finding)

    for heading, findings in sorted(by_heading.items()):
        out += [
            f"### {heading}",
            "",
            _findings_table(sorted(findings, key=lambda item: item.sort_key())),
            "",
        ]

    if result.suggestions:
        out += [
            "## Suggestions, not counted",
            "",
            "Hunter is not confident enough about these to let them affect the "
            "score. They are worth a human look rather than a change.",
            "",
            _findings_table(result.suggestions),
            "",
        ]

    if result.suppressed_findings:
        out += [
            "## Silenced, with a reason",
            "",
            "These are real findings that somebody has agreed to leave for now. "
            "They come back automatically on their expiry date.",
            "",
            table(
                ["What is wrong", "Where", "Reason recorded", "Comes back on"],
                [
                    [
                        finding.summary,
                        finding.subject,
                        finding.suppression_reason or "-",
                        finding.suppression_expires.isoformat()
                        if finding.suppression_expires
                        else "-",
                    ]
                    for finding in result.suppressed_findings
                ],
            ),
            "",
        ]

    out.append(timestamp(result, "Findings computed"))
    return "\n".join(out)


def sync_page(result: RunResult) -> str:
    """Are the layers in sync? F10."""
    cross = [
        finding
        for finding in result.findings
        if finding.rule.startswith(("crosslayer.", "droughty."))
    ]
    out = [
        "# Do the layers still agree",
        "",
        "Three comparisons: the reporting layer against the tables underneath it, "
        "the generated schema against the project, and the designed model against "
        "what was built.",
        "",
        "## Reporting layer against the data",
        "",
        table(
            ["Measure", "Count"],
            [
                ["Report views read", len(result.project.lookml_views)],
                ["Explores read", len(result.project.explores)],
                [
                    "Views matched to a table",
                    sum(1 for view in result.project.lookml_views.values() if view.model_name),
                ],
                [
                    "Views Hunter could not match",
                    sum(
                        1
                        for view in result.project.lookml_views.values()
                        if not view.model_name and not view.is_derived_table
                    ),
                ],
                [
                    "Views built on their own query, not checked",
                    sum(
                        1 for view in result.project.lookml_views.values() if view.is_derived_table
                    ),
                ],
            ],
        ),
        "",
    ]

    droughty = result.project.droughty
    if droughty is not None:
        out += [
            "## Generated schema against the project",
            "",
            table(
                ["Measure", "Count"],
                [
                    ["Tests the generated schema declares", len(droughty.generated_tests)],
                    ["Tables it covers", len(droughty.covered_models)],
                    ["Hand-written overrides in the config", len(droughty.test_overrides)],
                    ["Tables deliberately excluded", len(droughty.test_ignore_models)],
                    ["Descriptions defined", len(droughty.doc_blocks_defined)],
                    ["Descriptions referenced", len(droughty.doc_refs)],
                    [
                        "Last generated",
                        droughty.schema_modified_at.isoformat()
                        if droughty.schema_modified_at
                        else "not known",
                    ],
                ],
            ),
            "",
        ]
    else:
        out += [
            "## Generated schema against the project",
            "",
            "_No generated schema was found, so this comparison did not run._",
            "",
        ]

    out += ["## Findings", "", _findings_table(cross), timestamp(result, "Layers compared")]
    return "\n".join(out)


def conventions_page(result: RunResult) -> str:
    """The active ruleset, so the score is auditable. F10, FR7d."""
    from hunter.checks.base import REGISTRY

    config = result.config
    out = [
        "# The rules this was measured against",
        "",
        f"Measured against **{config.extends}**, house ruleset version "
        f"{config.house_version}. Every rule and every weight is listed here, so "
        "any number on this site can be traced back to the rule that produced it.",
        "",
        "## How the areas are weighted",
        "",
        table(
            ["Area", "Weight", "Used this run", "Why"],
            [
                [
                    DIMENSION_HEADINGS[entry.dimension],
                    f"{entry.weight:g}",
                    f"{entry.effective_weight:g}" if entry.scored else "not measured",
                    entry.skipped_reason or "-",
                ]
                for entry in result.score.dimensions
            ],
        ),
        "",
        "## The layers",
        "",
        "A layer marked *found* was discovered in the models directory and is not in the",
        "ruleset. Its models are grouped and reported, and held to no layer rules until",
        "the layer is declared.",
        "",
        table(
            [
                "Layer",
                "Declared",
                "Prefix",
                "Stage",
                "Temporary or permanent",
                "May read",
                "Holds entities",
            ],
            [
                [
                    layer.name,
                    "found, not declared" if layer.discovered else "yes",
                    layer.prefix or "-",
                    layer.pipeline_stage or "outside the flow",
                    layer.persistence.label,
                    ", ".join(layer.may_reference) or "anything",
                    "yes" if layer.in_alignment else "no",
                ]
                for layer in config.layers
            ],
        ),
        "",
        "## Entity naming",
        "",
        table(
            ["Kind", "Name ends with", "Needs a key", "Needs a uniqueness check"],
            [
                [
                    str(spec.kind),
                    spec.suffix,
                    "yes" if spec.requires_surrogate_key else "no",
                    "yes" if spec.requires_unique_test else "no",
                ]
                for spec in config.entities
            ],
        ),
        "",
    ]

    if result.resolved.divergences:
        out += [
            "## Where this project departs from the house standard",
            "",
            "FR7d makes this a first-class output: on a client engagement it shows "
            "how far the repository sits from the standard, which is itself a "
            "finding.",
            "",
            table(
                ["Setting", "Change", "House says", "This project says", "Reason given"],
                [
                    [
                        item.path,
                        item.kind,
                        repr(item.house_value),
                        repr(item.project_value),
                        item.reason or "none recorded",
                    ]
                    for item in sorted(result.resolved.divergences, key=lambda item: item.path)
                ],
            ),
            "",
        ]
    else:
        out += [
            "## Where this project departs from the house standard",
            "",
            "It does not. Every rule and weight is the house standard.",
            "",
        ]

    out += [
        "## Every rule",
        "",
        table(
            ["Rule", "Area", "How serious", "Points", "Ran this time", "Needs"],
            [
                [
                    f"`{spec.id}`",
                    DIMENSION_HEADINGS[spec.dimension],
                    severity_label(config.rule_setting(spec.id).severity or spec.severity),
                    f"{spec.points:g}",
                    "yes" if spec.id in result.examined else "no",
                    ", ".join(spec.requires) or "nothing",
                ]
                for spec in REGISTRY.all()
                if config.is_rule_enabled(spec.id)
            ],
        ),
        "",
    ]

    disabled = [spec for spec in REGISTRY.all() if not config.is_rule_enabled(spec.id)]
    if disabled:
        out += [
            "## Rules switched off for this project",
            "",
            table(
                ["Rule", "Reason given"],
                [
                    [f"`{spec.id}`", config.rule_setting(spec.id).reason or "none recorded"]
                    for spec in disabled
                ],
            ),
            "",
        ]

    out.append(timestamp(result, "Ruleset resolved"))
    return "\n".join(out)


def glossary_page() -> str:
    """FR14.4. Every term the site uses, defined."""
    return "\n".join(
        [
            "# Words used on this site",
            "",
            "Plain definitions for every term that appears elsewhere.",
            "",
            *[f"**{term}**\n\n{definition}\n" for term, definition in sorted(GLOSSARY.items())],
        ]
    )


#: Every source Hunter can read, and what its absence costs. Shared with the
#: dashboard so both say the same thing about the same gap.
UNAVAILABLE_REASONS: dict[str, str] = {
    "warehouse": (
        "No read access to the warehouse, so nothing here reflects what is "
        "actually deployed, what it costs or whether row counts match the "
        "design."
    ),
    "dbml": "No design files were found, so nothing was compared against a design.",
    "conceptual": (
        "No business model diagram was found, so there is nothing to compare the design against."
    ),
    "lookml": ("No reporting layer files were found, so nothing was checked against the reports."),
    "droughty": (
        "No generated schema was found, so the generated tests and descriptions were not compared."
    ),
    "git": (
        "No usable history, so nothing is attributed to whoever wrote it and no "
        "window can be reported."
    ),
}


def not_checked_page(result: RunResult) -> str:
    """What Hunter did not look at, and why. Honest about its own limits."""
    missing = sorted(set(UNAVAILABLE_REASONS) - result.available)
    reasons = UNAVAILABLE_REASONS
    out = [
        "# What was not checked",
        "",
        "A score is only as good as what went into it. This page says what did not.",
        "",
    ]
    if missing:
        out += [
            table(
                ["Not available", "What that means"],
                [[item, reasons.get(item, "-")] for item in missing],
            ),
            "",
        ]
    else:
        out += ["Every source Hunter can read was available on this run.", ""]

    unchecked = [
        finding
        for finding in result.findings
        if finding.rule
        in {
            "conformance.types_unavailable",
            "crosslayer.view_table_unresolvable",
            "alignment.ambiguous_match",
        }
    ]
    if unchecked:
        out += ["## Specific things Hunter could not resolve", "", _findings_table(unchecked), ""]

    if result.project.parse_issues:
        out += [
            "## Files Hunter could not fully read",
            "",
            table(
                ["File", "What", "Detail"],
                [
                    [issue.source, issue.subject or "-", issue.message]
                    for issue in result.project.parse_issues
                ],
            ),
            "",
        ]

    out.append(timestamp(result, "Run completed"))
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Writing the site
# ---------------------------------------------------------------------------

#: Page file names, in navigation order.
PAGES: tuple[tuple[str, str], ...] = (
    ("index.md", "Overview"),
    ("reconciliation.md", "Designed against built"),
    ("roadmap.md", "The roadmap"),
    ("conceptual-model.md", "The business model"),
    ("data-model.md", "The data model"),
    ("scorecard.md", "The score"),
    ("physical-model.md", "What is built"),
    ("lineage.md", "How it fits together"),
    ("debt.md", "What needs doing"),
    ("sync.md", "Do the layers agree"),
    ("conventions.md", "The rules"),
    ("not-checked.md", "What was not checked"),
    ("glossary.md", "Words used here"),
)


def write_site(
    result: RunResult,
    out_dir: Path,
    *,
    per_model_pages: bool = True,
    generated_at: dt.datetime | None = None,
) -> list[Path]:
    """Write every page. Returns the files written, sorted."""
    docs = out_dir / "docs"
    docs.mkdir(parents=True, exist_ok=True)

    attribution = result.config.branding.attribution
    footer = f"\n\n---\n\n_{attribution}._\n"

    pages = {
        "index.md": overview_page(result),
        "reconciliation.md": reconciliation_page(result),
        "roadmap.md": roadmap_page(result),
        "conceptual-model.md": conceptual_page(result),
        "data-model.md": data_model_page(result),
        "scorecard.md": scorecard_page(result),
        "physical-model.md": physical_page(result),
        "lineage.md": lineage_page(result),
        "debt.md": debt_page(result),
        "sync.md": sync_page(result),
        "conventions.md": conventions_page(result),
        "not-checked.md": not_checked_page(result),
        "glossary.md": glossary_page(),
    }

    written: list[Path] = []
    for name, body in pages.items():
        path = docs / name
        path.write_text(body + footer, encoding="utf-8")
        written.append(path)

    if per_model_pages:
        model_dir = docs / "models"
        model_dir.mkdir(exist_ok=True)
        for model in result.project.sorted_models():
            if model.vendored:
                continue
            path = model_dir / f"{model.name}.md"
            path.write_text(model_page(result, model.name) + footer, encoding="utf-8")
            written.append(path)

    # The dashboard is the front page of the report. It is written into the
    # MkDocs tree so the built site serves it, and it is also standalone: every
    # style, chart and image is inlined, so this one file can be sent on its own.
    from hunter.emit.dashboard import dashboard_html
    from hunter.emit.theme import BRAND_CSS

    dashboard = docs / "dashboard.html"
    dashboard.write_text(dashboard_html(result, generated_at=generated_at), encoding="utf-8")
    written.append(dashboard)

    overrides = docs / "assets"
    overrides.mkdir(exist_ok=True)
    css_path = overrides / "rittman.css"
    css_path.write_text(BRAND_CSS, encoding="utf-8")
    written.append(css_path)

    logo_path = overrides / "rittman-analytics.png"
    logo_path.write_bytes((ASSETS / "rittman-analytics.png").read_bytes())
    written.append(logo_path)

    favicon_path = overrides / "favicon.ico"
    favicon_path.write_bytes((ASSETS / "favicon.ico").read_bytes())
    written.append(favicon_path)

    config_path = out_dir / "mkdocs.yml"
    config_path.write_text(mkdocs_config(result), encoding="utf-8")
    written.append(config_path)

    return sorted(written)


def mkdocs_config(result: RunResult) -> str:
    """The MkDocs configuration, with the nav in reading order."""
    branding = result.config.branding
    name = branding.site_name
    if branding.client_name:
        name = f"{branding.client_name}: {name}"

    nav = "\n".join(f"  - {title}: {file}" for file, title in PAGES)
    return f"""# Generated by Rittman Hunter. Edits here are overwritten on the next run.
site_name: {name!r}
site_description: 'Repository health, generated from the repository itself'
use_directory_urls: true

theme:
  name: material
  logo: assets/rittman-analytics.png
  favicon: assets/favicon.ico
  font:
    text: Inter
    code: Roboto Mono
  palette:
    - media: '(prefers-color-scheme: light)'
      scheme: default
      primary: custom
      accent: custom
      toggle:
        icon: material/weather-night
        name: Switch to dark
    - media: '(prefers-color-scheme: dark)'
      scheme: slate
      primary: custom
      accent: custom
      toggle:
        icon: material/weather-sunny
        name: Switch to light
  features:
    - navigation.top
    - navigation.tracking
    - navigation.instant
    - content.code.copy
    - search.highlight
    - toc.follow

extra_css:
  - assets/rittman.css

markdown_extensions:
  - admonition
  - attr_list
  - md_in_html
  - tables
  - toc:
      permalink: true
  - pymdownx.details
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format

plugins:
  - search

copyright: {branding.attribution!r}

nav:
{nav}
"""
