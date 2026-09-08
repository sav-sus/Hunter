"""Do the model levels agree with each other?

F17, plus the register's own validity. The alignment chain in
``model/align.py`` works out the state of every entity; this module turns the
states that need action into findings, and leaves the ones that are merely
information as information.

The distinction matters for noise. 71 business entities on the pilot's
conceptual model have no design yet. That is a design backlog, not 71 defects,
so it is reported once as a count rather than 71 times as a failure.

The register is checked against reality here too. A register nobody prunes stops
being a record of decisions and becomes a place debt hides, so a stale entry, an
expired silence and an overdue approval are all findings.
"""

from __future__ import annotations

from hunter.checks.base import (
    REGISTRY,
    REQ_CONCEPTUAL,
    REQ_DBML,
    REQ_MANIFEST,
    CheckContext,
    Findings,
    plural,
    rule,
)
from hunter.config.register import validate_register
from hunter.enums import AlignmentState, Dimension, Severity

BUILT_OFF_PLAN = rule(
    "alignment.built_off_plan",
    dimension=Dimension.MODEL_CONFORMANCE,
    severity=Severity.MEDIUM,
    points=1.2,
    title="{subject} is built but was never designed",
    consequence=(
        "{label} exists in production and appears on no design, so nothing records "
        "what it is for, what one row means or who owns it. If it should be there, "
        "add it to the design or record an approval in the register."
    ),
    plain_heading="What was designed against what exists",
    requires=(REQ_MANIFEST, REQ_DBML),
    exposure_weighted=False,
)

BUILT_DISABLED = rule(
    "alignment.built_disabled",
    dimension=Dimension.MODEL_CONFORMANCE,
    severity=Severity.LOW,
    points=0.5,
    title="{subject} is built but switched off",
    consequence=(
        "The code for {label} exists and is not running, so nothing is being "
        "produced from it. Either it is waiting to be turned on, or it was left "
        "behind and should be removed."
    ),
    plain_heading="What was designed against what exists",
    exposure_weighted=False,
)

DESIGN_WITHOUT_BUSINESS_ENTITY = rule(
    "alignment.design_without_business_entity",
    dimension=Dimension.MODEL_CONFORMANCE,
    severity=Severity.LOW,
    points=0.4,
    title="{subject} is designed but appears on no business model",
    consequence=(
        "{label} was designed without a matching entity on the conceptual model, so "
        "there is no record of which part of the business asked for it."
    ),
    plain_heading="What was designed against what exists",
    requires=(REQ_DBML, REQ_CONCEPTUAL),
    exposure_weighted=False,
)

DESIGN_BACKLOG = rule(
    "alignment.design_backlog",
    dimension=Dimension.MODEL_CONFORMANCE,
    severity=Severity.INFO,
    points=0.0,
    title="{phrase} on the business model have not been designed yet",
    consequence=(
        "These are agreed with the business as things the warehouse should hold, and "
        "no design exists for them yet. This is the design backlog, not a list of "
        "faults. Examples: {examples}."
    ),
    plain_heading="What is still to come",
    requires=(REQ_CONCEPTUAL,),
    exposure_weighted=False,
)

DIAGRAM_CLAIM_STALE = rule(
    "alignment.diagram_claim_stale",
    dimension=Dimension.MODEL_CONFORMANCE,
    severity=Severity.MEDIUM,
    points=0.6,
    title="The business model shows {subject} as {claimed}, but it is {actual}",
    consequence=(
        "The published picture of the data model is out of date for {label}. Anyone "
        "reading it is being told something that is not true, which is worse than "
        "not having the picture."
    ),
    plain_heading="Is the published picture still true",
    requires=(REQ_CONCEPTUAL,),
    exposure_weighted=False,
)

AMBIGUOUS_MATCH = rule(
    "alignment.ambiguous_match",
    dimension=Dimension.MODEL_CONFORMANCE,
    severity=Severity.MEDIUM,
    points=0.8,
    title="{subject} could be either of {phrase}, so Hunter did not choose: {candidates}",
    consequence=(
        "Hunter cannot tell which designed table {label} corresponds to, so its row "
        "in the reconciliation is incomplete. Adding an implements entry to the "
        "register settles it. Guessing would have produced a wrong row that reads "
        "as fact."
    ),
    plain_heading="What was not checked",
    requires=(REQ_DBML,),
    exposure_weighted=False,
)

APPROVED_OFF_PLAN = rule(
    "alignment.approved_off_plan",
    dimension=Dimension.MODEL_CONFORMANCE,
    severity=Severity.INFO,
    points=0.0,
    title="{subject} is built ahead of the design, with that approved",
    consequence=(
        "{label} was accepted as an exception rather than added to the design. "
        "Recorded reason: {reason}"
    ),
    plain_heading="Agreed exceptions",
    exposure_weighted=False,
)

UNMANAGED_PRODUCTION = rule(
    "alignment.unmanaged_production_object",
    dimension=Dimension.MODEL_CONFORMANCE,
    severity=Severity.HIGH,
    points=1.5,
    title="{subject} is in production and nothing here produces it",
    consequence=(
        "Something outside this project is writing {label}. Nobody here manages it, "
        "nothing tests it, and a change to it would not be noticed."
    ),
    plain_heading="What was designed against what exists",
    exposure_weighted=False,
)

# ---- register validity ----

REGISTER_RULES = {
    "register.entry_matches_no_model": (Dimension.MODEL_CONFORMANCE, 0.3),
    "register.approval_matches_no_model": (Dimension.MODEL_CONFORMANCE, 0.3),
    "register.review_overdue": (Dimension.MODEL_CONFORMANCE, 0.6),
    "register.approval_review_overdue": (Dimension.MODEL_CONFORMANCE, 0.6),
    "register.ignore_expired": (Dimension.CONVENTIONS_STRUCTURE, 0.6),
    "register.ignore_names_unknown_rule": (Dimension.CONVENTIONS_STRUCTURE, 0.3),
}

for _rule_id, (_dimension, _points) in REGISTER_RULES.items():
    rule(
        _rule_id,
        dimension=_dimension,
        severity=Severity.MEDIUM,
        points=_points,
        title="{summary}",
        consequence="{consequence}",
        plain_heading="Agreed exceptions",
        requires=(),
        exposure_weighted=False,
    )


#: States that need someone to do something.
ACTIONABLE: dict[AlignmentState, str] = {
    AlignmentState.BUILT_OFF_PLAN: BUILT_OFF_PLAN.id,
    AlignmentState.BUILT_DISABLED: BUILT_DISABLED.id,
    AlignmentState.UNTRACKED_TABLE: UNMANAGED_PRODUCTION.id,
    AlignmentState.LIVE_WITHOUT_CODE: UNMANAGED_PRODUCTION.id,
    AlignmentState.APPROVED_OFF_PLAN: APPROVED_OFF_PLAN.id,
}


def run(context: CheckContext) -> Findings:
    """Report where the model levels disagree, and where the register has gone stale."""
    findings = Findings()
    alignment = context.alignment

    for row in alignment.rows:
        subject = row.model_name or row.designed_name or row.key

        # Examine every candidate, not only the ones that fail. Counting only
        # failures makes the denominator equal the numerator, and the dimension
        # then scores zero whenever a single entity is off-plan.
        if row.is_built or row.repo.value == "disabled":
            context.examine(BUILT_OFF_PLAN.id, subject)
            context.examine(BUILT_DISABLED.id, subject)
            context.examine(UNMANAGED_PRODUCTION.id, subject)
            context.examine(APPROVED_OFF_PLAN.id, subject)
        if row.designed.value == "present" and context.has(REQ_CONCEPTUAL):
            context.examine(DESIGN_WITHOUT_BUSINESS_ENTITY.id, row.designed_name or row.key)
        if row.claimed_status:
            context.examine(DIAGRAM_CLAIM_STALE.id, row.conceptual_name or row.key)
        if row.designed.value == "present" or row.is_built:
            context.examine(AMBIGUOUS_MATCH.id, subject)

        rule_id = ACTIONABLE.get(row.state)
        if rule_id is not None:
            findings.add(
                context.finding(
                    rule_id,
                    subject=subject,
                    subject_kind="entity",
                    file=row.design_file,
                    evidence={
                        "state": row.state.value,
                        "reason": row.approval_reason or "none recorded",
                        "domain": row.domain,
                    },
                )
            )

        if (
            row.designed is not None
            and row.designed.value == "present"
            and row.conceptual.value == "absent"
            and context.has(REQ_CONCEPTUAL)
        ):
            findings.add(
                context.finding(
                    DESIGN_WITHOUT_BUSINESS_ENTITY.id,
                    subject=row.designed_name or row.key,
                    subject_kind="designed_entity",
                    file=row.design_file,
                )
            )

        if row.claim_matches_reality is False:
            findings.add(
                context.finding(
                    DIAGRAM_CLAIM_STALE.id,
                    subject=row.conceptual_name or row.key,
                    subject_kind="conceptual_entity",
                    evidence={
                        "claimed": row.claimed_status or "unstated",
                        "actual": row.state_label.lower(),
                    },
                )
            )

        if row.match_method == "ambiguous" and row.match_candidates:
            findings.add(
                context.finding(
                    AMBIGUOUS_MATCH.id,
                    subject=subject,
                    subject_kind="entity",
                    evidence={
                        "phrase": plural(len(row.match_candidates), "designed table"),
                        "candidates": ", ".join(row.match_candidates[:4]),
                    },
                )
            )

    findings.extend_from(_design_backlog(context))
    findings.extend_from(_register(context))
    return findings


def _design_backlog(context: CheckContext) -> Findings:
    """One informational count, not one failure per unbuilt idea."""
    findings = Findings()
    if not context.has(REQ_CONCEPTUAL):
        return findings

    backlog = [row for row in context.alignment.rows if row.state is AlignmentState.CONCEPTUAL_ONLY]
    if not backlog:
        return findings

    findings.add(
        context.finding(
            DESIGN_BACKLOG.id,
            subject="conceptual model",
            subject_kind="project",
            evidence={
                "count": len(backlog),
                "phrase": plural(len(backlog), "business entity", "business entities"),
                "examples": ", ".join(sorted(row.label for row in backlog)[:6]),
            },
        )
    )
    return findings


def _register(context: CheckContext) -> Findings:
    """The register checked against the repository it describes."""
    findings = Findings()
    issues = validate_register(
        context.register,
        known_models=context.project.model_names(),
        known_rules=REGISTRY.ids(),
        as_of=context.as_of,
    )
    for issue in issues:
        context.examine(issue.rule, issue.subject)
        findings.add(
            context.finding(
                issue.rule,
                subject=issue.subject,
                subject_kind="register",
                evidence={
                    "summary": issue.summary,
                    "consequence": issue.consequence,
                    **issue.evidence,
                },
            )
        )
    return findings
