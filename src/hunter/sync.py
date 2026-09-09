"""The three sync checks, as one thing the whole product agrees on.

Hunter's score answers "how healthy is this repository". These answer a
narrower question a team can put on a pull request and act on the same day:
**has one layer drifted away from another?**

    LookML sync      does the reporting layer still match the tables
    Droughty sync    has the generated schema been applied, and is it current
    Modelling sync   does what exists match what was designed and asked for

Each is a slice of the rules the score already runs, plus the dashboard's own
checklist section for that layer. Nothing here computes a second opinion, so a
sync check that passes and a score that drops cannot contradict each other:
they are reading the same findings.

Three reasons these are separate gates rather than one:

1. They fail for different reasons and different people fix them. A renamed
   column is an analytics engineer's morning. An undesigned table is a
   conversation with whoever owns the design.
2. They become available at different times. A repository with no DBML can run
   LookML sync on its first day; modelling sync has nothing to read yet.
3. A team will make one of them a required check long before it accepts the
   whole score as one. Three small gates get adopted; one large one gets an
   exemption.

A check whose sources are missing reports **skipped**, never **passed**. That
distinction is the point of the whole module: a green tick nobody earned is
worse than no tick.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hunter.checks.base import (
    REGISTRY,
    REQ_CONCEPTUAL,
    REQ_DBML,
    REQ_DROUGHTY,
    REQ_LOOKML,
    REQ_MANIFEST,
)
from hunter.enums import SEVERITY_ORDER, Severity
from hunter.model.findings import Finding
from hunter.run import RunResult


@dataclass(frozen=True)
class SyncCheck:
    """One drift check: which rules it runs, and what it needs to run them."""

    key: str
    title: str
    #: The question in the words a reader would ask it.
    question: str
    #: What goes wrong when this drifts, in one sentence.
    consequence: str
    #: Rule id prefixes. A slice of the registry, never a separate rule set.
    prefixes: tuple[str, ...]
    #: Every source that must be present. Missing any means skipped, not passed.
    requires: tuple[str, ...]
    #: Checklist sections this check owns, so the dashboard and the CI check
    #: group the same facts under the same headings.
    sections: tuple[str, ...] = ()
    #: Sources that are optional but sharpen it. Named on a pass, so a green
    #: check still says what it could not see.
    sharpened_by: tuple[str, ...] = ()

    def owns(self, rule_id: str) -> bool:
        return rule_id.startswith(self.prefixes)


LOOKML_SYNC = SyncCheck(
    key="lookml",
    title="LookML sync",
    question="Does the reporting layer still match the tables?",
    consequence=(
        "A field reading a column that no longer exists breaks in a client's "
        "dashboard, not in the pull request that removed it."
    ),
    prefixes=("crosslayer.",),
    requires=(REQ_MANIFEST, REQ_LOOKML),
    sections=("Warehouse to Looker",),
)

DROUGHTY_SYNC = SyncCheck(
    key="droughty",
    title="Droughty sync",
    question="Has the generated schema been applied, and is it current?",
    consequence=(
        "A generated test that never reached dbt is a test everyone believes "
        "is running. Nothing is checking what they think is checked."
    ),
    prefixes=("droughty.",),
    requires=(REQ_MANIFEST, REQ_DROUGHTY),
    sections=("Droughty",),
)

MODELLING_SYNC = SyncCheck(
    key="modelling",
    title="Modelling sync",
    question="Does what exists match what was designed and asked for?",
    consequence=(
        "A table built with no design has no agreed grain and no owner, and a "
        "design nobody built is a promise the business is still waiting on."
    ),
    prefixes=("alignment.", "conformance."),
    requires=(REQ_MANIFEST, REQ_DBML),
    sections=("Design to build",),
    sharpened_by=(REQ_CONCEPTUAL,),
)

#: In reading order: nearest the reports first, because that is the drift a
#: client notices.
SYNC_CHECKS: tuple[SyncCheck, ...] = (LOOKML_SYNC, DROUGHTY_SYNC, MODELLING_SYNC)

BY_KEY: dict[str, SyncCheck] = {check.key: check for check in SYNC_CHECKS}

#: What a missing source means, in the words the CI summary uses.
SOURCE_NAMES: dict[str, str] = {
    REQ_MANIFEST: "dbt manifest",
    REQ_DBML: "DBML design files",
    REQ_LOOKML: "LookML files",
    REQ_DROUGHTY: "committed Droughty output",
    REQ_CONCEPTUAL: "business model diagram",
}


def source_name(source: str) -> str:
    return SOURCE_NAMES.get(source, source)


@dataclass
class SyncResult:
    """What one sync check found."""

    check: SyncCheck
    #: False when a source it needs was not read. Nothing below is then meaningful.
    ran: bool
    missing_sources: tuple[str, ...] = ()
    absent_but_useful: tuple[str, ...] = ()
    checked: int = 0
    failed: int = 0
    findings: list[Finding] = field(default_factory=list)
    #: (statement, held, of, names that let it down)
    statements: list[tuple[str, int, int, tuple[str, ...]]] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return max(0, self.checked - self.failed)

    @property
    def share(self) -> float | None:
        """Share of what it looked at that was in sync, 0 to 100."""
        if not self.ran or self.checked == 0:
            return None
        return round(100.0 * self.passed / self.checked, 1)

    def by_severity(self) -> dict[Severity, int]:
        counts: dict[Severity, int] = {}
        for item in self.findings:
            counts[item.severity] = counts.get(item.severity, 0) + 1
        return dict(sorted(counts.items(), key=lambda pair: SEVERITY_ORDER[pair[0]]))

    @property
    def verdict(self) -> str:
        """One word, for a check name in a pull request."""
        if not self.ran:
            return "skipped"
        if self.checked == 0:
            return "nothing to compare"
        return "in sync" if self.failed == 0 else "drifted"

    @property
    def headline(self) -> str:
        """The answer in a sentence, for the top of a CI summary."""
        if not self.ran:
            names = ", ".join(source_name(item) for item in self.missing_sources)
            return f"Not checked. Hunter found no {names} to compare against."
        if self.checked == 0:
            return "Nothing to compare. The sources are there but hold nothing in common."
        if self.failed == 0:
            return f"In sync. All {self.checked} checks passed."
        return f"Drifted. {self.failed} of {self.checked} checks failed."

    def fails_build(self, threshold: str) -> bool:
        """Whether this result should fail a build.

        A skipped check never fails. There is nothing to be wrong about, and
        failing on a missing source would make adding a design file a breaking
        change.
        """
        if not self.ran or threshold == "never":
            return False
        if threshold == "any":
            return self.failed > 0
        if threshold == "high":
            return any(item.severity is Severity.HIGH for item in self.findings)
        raise ValueError(f"unknown threshold: {threshold!r}, expected never, high or any")


def evaluate(result: RunResult, check: SyncCheck) -> SyncResult:
    """Run one sync check over a completed run.

    Reads the findings and denominators the pipeline already produced. Nothing
    is re-checked, so this cannot disagree with the score.
    """
    missing = tuple(source for source in check.requires if source not in result.available)
    if missing:
        return SyncResult(check=check, ran=False, missing_sources=missing)

    findings = [
        item
        for item in result.open_findings
        if check.owns(item.rule) and not _is_about_coverage(item.rule)
    ]
    checked = sum(
        denominator.checked
        for rule_id, denominator in result.examined.items()
        if check.owns(rule_id) and not _is_about_coverage(rule_id)
    )

    return SyncResult(
        check=check,
        ran=True,
        absent_but_useful=tuple(
            source for source in check.sharpened_by if source not in result.available
        ),
        checked=checked,
        failed=len(findings),
        findings=sorted(
            findings, key=lambda item: (SEVERITY_ORDER[item.severity], item.rule, item.subject)
        ),
        statements=_statements_for(result, check),
    )


def evaluate_all(result: RunResult) -> list[SyncResult]:
    return [evaluate(result, check) for check in SYNC_CHECKS]


def _is_about_coverage(rule_id: str) -> bool:
    """Rules reporting what Hunter could not check are not drift.

    "Hunter could not resolve this table name" is not a layer having moved, so
    counting it as drift would fail a build for Hunter's own blind spot.
    """
    try:
        return REGISTRY.get(rule_id).about_coverage
    except KeyError:
        return False


def _statements_for(
    result: RunResult, check: SyncCheck
) -> list[tuple[str, int, int, tuple[str, ...]]]:
    """The dashboard's checklist statements for this check's sections."""
    from hunter.emit.dashboard import checklist

    return [
        (item.statement, item.done, item.total, item.missing)
        for section in checklist(result)
        if section.title in check.sections
        for item in section.checks
    ]


# ------------------------------------------------------------------- emitters


def as_payload(results: list[SyncResult], result: RunResult) -> dict[str, object]:
    """Machine-readable, for a CI step or a later comparison.

    Carries the version stamp for the same reason every report does: a result
    compared against one from a different Hunter is not a comparison.
    """
    return {
        "meta": dict(result.meta),
        "checks": [
            {
                "key": item.check.key,
                "title": item.check.title,
                "question": item.check.question,
                "verdict": item.verdict,
                "headline": item.headline,
                "ran": item.ran,
                "missing_sources": list(item.missing_sources),
                "narrowed_by_missing": list(item.absent_but_useful),
                "checked": item.checked,
                "passed": item.passed,
                "failed": item.failed,
                "in_sync_percent": item.share,
                "by_severity": {str(k): v for k, v in item.by_severity().items()},
                "statements": [
                    {
                        "statement": statement,
                        "held": held,
                        "of": total,
                        "let_down_by": list(missing),
                    }
                    for statement, held, total, missing in item.statements
                ],
                "findings": [
                    {
                        "rule": finding.rule,
                        "severity": str(finding.severity),
                        "object": finding.subject,
                        "summary": finding.summary,
                        "consequence": finding.consequence,
                        "file": finding.file,
                        "line": finding.line,
                    }
                    for finding in item.findings
                ],
            }
            for item in results
        ],
    }


_VERDICT_MARK = {
    "in sync": "&#10003;",
    "drifted": "&#10007;",
    "skipped": "&#8211;",
    "nothing to compare": "&#8211;",
}


def as_markdown(results: list[SyncResult], *, logo_url: str | None = None) -> str:
    """A CI step summary.

    Written so the table alone is enough to decide whether to look further,
    and the detail below it is enough to act without opening the repository.
    """
    from hunter.emit.pr_comment import header

    lines: list[str] = header("Rittman Hunter: layer sync", logo_url)
    lines += ["| | Check | Result | Detail |", "|---|---|---|---|"]
    for item in results:
        mark = _VERDICT_MARK[item.verdict]
        lines.append(f"| {mark} | {item.check.title} | {item.verdict} | {item.headline} |")
    lines.append("")

    for item in results:
        if not item.ran:
            names = ", ".join(source_name(source) for source in item.missing_sources)
            lines += [
                f"### {item.check.title}: skipped",
                "",
                f"Nothing to compare against. Hunter read no {names}.",
                "",
                "This is not a pass. Adding that source turns this check on.",
                "",
            ]
            continue

        lines += [f"### {item.check.title}", "", f"_{item.check.question}_", ""]
        if item.statements:
            lines += ["| Holds | Statement | Where it does not |", "|---|---|---|"]
            for statement, held, total, missing in item.statements:
                shown = ", ".join(f"`{name}`" for name in missing[:4])
                if len(missing) > 4:
                    shown += f" and {len(missing) - 4} more"
                lines.append(f"| {held} of {total} | {statement} | {shown or '-'} |")
            lines.append("")

        if item.findings:
            lines += [
                "<details><summary>"
                f"{item.failed} finding{'' if item.failed == 1 else 's'}</summary>",
                "",
                "| Severity | What is wrong | What breaks if it is left |",
                "|---|---|---|",
            ]
            for finding in item.findings[:25]:
                lines.append(f"| {finding.severity} | {finding.summary} | {finding.consequence} |")
            if len(item.findings) > 25:
                lines.append(f"| | and {len(item.findings) - 25} more | |")
            lines += ["", "</details>", ""]
        else:
            lines += [item.check.consequence, ""]

        if item.absent_but_useful:
            names = ", ".join(source_name(source) for source in item.absent_but_useful)
            lines += [
                f"Narrower than it could be: Hunter read no {names}.",
                "",
            ]

    lines += [
        "---",
        "",
        "_Generated by Rittman Hunter, from Rittman Analytics. Nothing was written "
        "back to this repository._",
        "",
    ]
    return "\n".join(lines)
