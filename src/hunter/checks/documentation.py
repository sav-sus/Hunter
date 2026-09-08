"""Is it documented, and is the documentation still true?

FR2.4 and FR2.5. Table-level and column-level documentation are checked
separately, and it matters: the pilot repository describes 1,615 of 1,615
columns on its warehouse models and 0 of 54 tables. Rolled into one figure that
project reads as undocumented, which would be wrong and would cost the tool its
credibility on the first run.
"""

from __future__ import annotations

from hunter.checks.base import (
    REQ_DBML,
    REQ_GIT,
    REQ_MANIFEST,
    CheckContext,
    Findings,
    plural,
    rule,
)
from hunter.enums import Dimension, Severity

MODEL_DESCRIPTION_MISSING = rule(
    "documentation.model_description_missing",
    dimension=Dimension.DOCUMENTATION,
    severity=Severity.MEDIUM,
    points=1.0,
    title="{subject} has no description",
    consequence=(
        "Nobody reading the catalogue can tell what {label} is for or whether it is "
        "the right table to use. {consumers}."
    ),
    plain_heading="What is documented",
)

MODEL_DESCRIPTION_PLACEHOLDER = rule(
    "documentation.model_description_placeholder",
    dimension=Dimension.DOCUMENTATION,
    severity=Severity.MEDIUM,
    points=1.0,
    title="{subject} has a placeholder description: {text!r}",
    consequence=(
        "The description for {label} says {text!r}, which tells a reader nothing. It "
        "counts as documented in the catalogue while explaining nothing."
    ),
    plain_heading="What is documented",
)

COLUMN_DESCRIPTION_MISSING = rule(
    "documentation.column_description_missing",
    dimension=Dimension.DOCUMENTATION,
    severity=Severity.LOW,
    points=0.8,
    title="{count} of {total} columns on {subject} have no description",
    consequence=(
        "{label} has {phrase} with no description, so anyone building a report "
        "from it has to guess the meaning or ask whoever wrote it."
    ),
    plain_heading="What is documented",
)

OWNER_MISSING = rule(
    "documentation.owner_missing",
    dimension=Dimension.DOCUMENTATION,
    severity=Severity.MEDIUM,
    points=0.8,
    title="{subject} names no owner",
    consequence=(
        "There is nobody to ask about {label} and nobody to route a problem with it "
        "to. It is a persistent table, and {consumers}."
    ),
    plain_heading="Who owns what",
)

DESCRIPTION_STALE = rule(
    "documentation.description_stale",
    dimension=Dimension.DOCUMENTATION,
    severity=Severity.LOW,
    points=0.5,
    title="{subject} was changed {days} days after its description was last touched",
    consequence=(
        "The description of {label} may no longer match what the table does. The code "
        "has moved on and the documentation has not."
    ),
    plain_heading="What is documented",
    requires=(REQ_MANIFEST, REQ_GIT),
)

DESIGN_NOTE_MISSING = rule(
    "documentation.design_note_missing",
    dimension=Dimension.DOCUMENTATION,
    severity=Severity.MEDIUM,
    points=1.0,
    title="The design for {subject} has no note",
    consequence=(
        "The design says what columns {label} should have but not what it is for or "
        "what one row represents. That is the part a non-technical reader needs."
    ),
    plain_heading="What is documented",
    requires=(REQ_DBML,),
    exposure_weighted=False,
)

DESIGN_GRAIN_MISSING = rule(
    "documentation.design_grain_missing",
    dimension=Dimension.DOCUMENTATION,
    severity=Severity.MEDIUM,
    points=1.0,
    title="The design for {subject} does not state its grain",
    consequence=(
        "Nothing records what one row of {label} represents, so nobody can tell "
        "whether summing its figures double-counts."
    ),
    plain_heading="What one row means",
    requires=(REQ_DBML,),
    exposure_weighted=False,
)

DESIGN_COLUMN_NOTES_MISSING = rule(
    "documentation.design_column_notes_missing",
    dimension=Dimension.DOCUMENTATION,
    severity=Severity.LOW,
    points=0.8,
    title="{phrase} of {total} designed columns on {subject} have no note",
    consequence=(
        "The design of {label} leaves {phrase} unexplained, so the business "
        "meaning has to be worked out from the name."
    ),
    plain_heading="What is documented",
    requires=(REQ_DBML,),
    exposure_weighted=False,
)


def _is_placeholder(text: str, patterns: list[str], min_words: int) -> bool:
    cleaned = text.strip().strip(".").lower()
    if not cleaned:
        return True
    if cleaned in {pattern.lower() for pattern in patterns}:
        return True
    return len(cleaned.split()) < min_words


def run(context: CheckContext) -> Findings:
    """Report documentation gaps, layer by layer."""
    findings = Findings()
    spec = context.config.documentation

    for model in context.project.sorted_models():
        if (
            not model.is_scoreable
            and not context.config.rule_setting(MODEL_DESCRIPTION_MISSING.id).enabled
        ):
            continue
        layer = context.config.layer(model.layer) if model.layer else None
        if layer is None:
            continue

        consumers = context.consumer_summary(model.name)

        if layer.requires_model_description:
            context.examine(MODEL_DESCRIPTION_MISSING.id, model.name)
            context.examine(MODEL_DESCRIPTION_PLACEHOLDER.id, model.name)
            if not model.has_description:
                findings.add(
                    context.finding(
                        MODEL_DESCRIPTION_MISSING.id,
                        subject=model.name,
                        file=model.path,
                        evidence={"layer": model.layer, "consumers": consumers},
                    )
                )
            elif _is_placeholder(
                model.description or "", spec.placeholder_patterns, spec.min_description_words
            ):
                findings.add(
                    context.finding(
                        MODEL_DESCRIPTION_PLACEHOLDER.id,
                        subject=model.name,
                        file=model.path,
                        evidence={
                            "layer": model.layer,
                            "text": (model.description or "").strip(),
                            "consumers": consumers,
                        },
                    )
                )

        if layer.requires_column_descriptions and model.columns:
            context.examine(COLUMN_DESCRIPTION_MISSING.id, model.name)
            undocumented = [
                column.name
                for column in model.columns
                if not column.has_description
                or _is_placeholder(
                    column.description or "",
                    spec.placeholder_patterns,
                    spec.min_description_words,
                )
            ]
            if undocumented:
                findings.add(
                    context.finding(
                        COLUMN_DESCRIPTION_MISSING.id,
                        subject=model.name,
                        file=model.path,
                        points_scale=len(undocumented) / len(model.columns),
                        evidence={
                            "count": len(undocumented),
                            "phrase": plural(len(undocumented), "column"),
                            "total": len(model.columns),
                            "columns": sorted(undocumented)[:20],
                            "consumers": consumers,
                        },
                    )
                )

        if layer.requires_owner and spec.require_owner_in_meta:
            context.examine(OWNER_MISSING.id, model.name)
        if layer.requires_owner and spec.require_owner_in_meta and not model.owner:
            findings.add(
                context.finding(
                    OWNER_MISSING.id,
                    subject=model.name,
                    file=model.path,
                    evidence={"layer": model.layer, "consumers": consumers},
                )
            )

    findings.extend(_stale_descriptions(context))
    findings.extend(_design_documentation(context))
    return findings


def _stale_descriptions(context: CheckContext) -> Findings:
    """Descriptions the code has moved on from. FR2.5.

    Compares when a model's SQL last changed against when the schema file
    documenting it last changed. A gap wider than the configured window means
    the documentation is describing an older version of the table.

    Only models that are actually documented are considered: an undocumented
    model is already reported by its own rule, and reporting it twice would
    double-count the same gap.
    """
    spec = context.config.documentation
    if not spec.flag_stale_descriptions or not context.has(REQ_GIT):
        return Findings()

    findings = Findings()
    for model in context.project.sorted_models():
        if not model.has_description or not model.is_scoreable:
            continue
        if model.last_modified_at is None or model.docs_modified_at is None:
            continue
        context.examine(DESCRIPTION_STALE.id, model.name)
        gap = (model.last_modified_at - model.docs_modified_at).days
        if gap <= spec.stale_after_days:
            continue
        findings.add(
            context.finding(
                DESCRIPTION_STALE.id,
                subject=model.name,
                file=model.path,
                evidence={
                    "days": gap,
                    "sql_changed": str(model.last_modified_at),
                    "docs_changed": str(model.docs_modified_at),
                    "schema_file": model.schema_file,
                },
            )
        )
    return findings


def _design_documentation(context: CheckContext) -> Findings:
    """Notes and grain on the authored design."""
    if not context.has(REQ_DBML):
        return Findings()

    findings = Findings()
    for entity in context.project.sorted_designed():
        context.examine(DESIGN_NOTE_MISSING.id, entity.name)
        context.examine(DESIGN_GRAIN_MISSING.id, entity.name)
        if entity.columns:
            context.examine(DESIGN_COLUMN_NOTES_MISSING.id, entity.name)
        if not entity.note or not entity.note.strip():
            findings.add(
                context.finding(
                    DESIGN_NOTE_MISSING.id,
                    subject=entity.name,
                    subject_kind="designed_entity",
                    file=entity.source_file,
                )
            )
        elif not entity.grain_note:
            findings.add(
                context.finding(
                    DESIGN_GRAIN_MISSING.id,
                    subject=entity.name,
                    subject_kind="designed_entity",
                    file=entity.source_file,
                )
            )

        if entity.columns:
            unnoted = [column.name for column in entity.columns if not column.has_note]
            if unnoted:
                findings.add(
                    context.finding(
                        DESIGN_COLUMN_NOTES_MISSING.id,
                        subject=entity.name,
                        subject_kind="designed_entity",
                        file=entity.source_file,
                        points_scale=len(unnoted) / len(entity.columns),
                        evidence={
                            "count": len(unnoted),
                            "phrase": plural(len(unnoted), "column"),
                            "total": len(entity.columns),
                            "columns": sorted(unnoted)[:20],
                        },
                    )
                )
    return findings
