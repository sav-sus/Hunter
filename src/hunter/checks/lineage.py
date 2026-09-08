"""Lineage shapes that cause wrong numbers.

FR5.3. Four patterns, each with a specific failure mode rather than a general
sense of untidiness:

* **Fanout.** One model read directly by many others. A change to it is a change
  to all of them, so nobody can safely touch it.
* **Rejoins.** A model reading the same upstream table by two different paths.
  This is the shape that produces double counting.
* **Dead models.** Built, costed and never read. Spend with no consumer.
* **Staging bypass.** A finished table reading a working step from two layers
  up, so the intermediate checks never run.
"""

from __future__ import annotations

from hunter.checks.base import CheckContext, Findings, plural, rule
from hunter.enums import Dimension, Persistence, Severity
from hunter.model.entities import Model

HIGH_FANOUT = rule(
    "lineage.high_fanout",
    dimension=Dimension.LINEAGE_HEALTH,
    severity=Severity.MEDIUM,
    points=1.0,
    title="{phrase} read directly from {subject}, over the limit of {limit}",
    consequence=(
        "Any change to {label} is a change to {count} other models at once, so in "
        "practice nobody can safely alter it."
    ),
    plain_heading="How the tables fit together",
)

MODEL_REJOIN = rule(
    "lineage.model_rejoin",
    dimension=Dimension.LINEAGE_HEALTH,
    severity=Severity.HIGH,
    points=1.5,
    title="{subject} reads {rejoined} by more than one path",
    consequence=(
        "{label} brings in the same upstream data twice through different routes. "
        "If either path returns more than one row per key, figures double-count "
        "with nothing to signal it."
    ),
    plain_heading="How the tables fit together",
)

DEAD_MODEL = rule(
    "lineage.dead_model",
    dimension=Dimension.LINEAGE_HEALTH,
    severity=Severity.MEDIUM,
    points=1.0,
    title="{subject} is built and stored but nothing reads it",
    consequence=(
        "{label} is rebuilt on every run and no model, report or dashboard uses the "
        "result. It costs money and delivers nothing until something consumes it."
    ),
    plain_heading="What is not used",
    exposure_weighted=False,
)

TEMPORARY_MODEL_EXPOSED = rule(
    "lineage.temporary_model_exposed",
    dimension=Dimension.LINEAGE_HEALTH,
    severity=Severity.HIGH,
    points=1.5,
    title="{subject} is a working step but {consumer_kind} reads it directly",
    consequence=(
        "{label} was built as a temporary step and was never meant to be relied on. "
        "Something outside the modelling layer now depends on it, so it cannot be "
        "changed or removed without breaking that. {detail}"
    ),
    plain_heading="Temporary against permanent",
)

STAGING_BYPASSED = rule(
    "lineage.staging_bypassed",
    dimension=Dimension.LINEAGE_HEALTH,
    severity=Severity.MEDIUM,
    points=1.0,
    title="{subject} skips the {skipped} layer to read {referenced}",
    consequence=(
        "{label} reaches back past the layer that normally cleans and checks this "
        "data, so those checks do not apply to what it reads."
    ),
    plain_heading="How the layers fit together",
)

DEPENDENCY_CYCLE = rule(
    "lineage.dependency_cycle",
    dimension=Dimension.LINEAGE_HEALTH,
    severity=Severity.HIGH,
    points=4.0,
    title="{subject} is part of a dependency loop: {cycle}",
    consequence=(
        "These models depend on each other in a circle, so there is no order in "
        "which they can be built. The project as described cannot run."
    ),
    plain_heading="How the tables fit together",
    exposure_weighted=False,
)


def run(context: CheckContext) -> Findings:
    """Look for lineage shapes that produce wrong or wasted work."""
    findings = Findings()
    spec = context.config.lineage
    graph = context.graph
    project = context.project

    for cycle in graph.cycles():
        subject = cycle[0]
        findings.add(
            context.finding(
                DEPENDENCY_CYCLE.id,
                subject=subject,
                evidence={"cycle": " -> ".join(cycle)},
            )
        )

    for model in project.sorted_models():
        if not model.is_scoreable:
            continue

        context.examine(HIGH_FANOUT.id, model.name)
        fanout = graph.fanout(model.name)
        if fanout > spec.max_fanout:
            findings.add(
                context.finding(
                    HIGH_FANOUT.id,
                    subject=model.name,
                    file=model.path,
                    evidence={
                        "count": fanout,
                        "phrase": plural(fanout, "model"),
                        "limit": spec.max_fanout,
                    },
                )
            )

        if spec.flag_model_rejoins:
            context.examine(MODEL_REJOIN.id, model.name)
            rejoined = graph.rejoin_paths(model.name)
            if rejoined:
                findings.add(
                    context.finding(
                        MODEL_REJOIN.id,
                        subject=model.name,
                        file=model.path,
                        evidence={
                            "rejoined": ", ".join(rejoined[:4]),
                            "count": len(rejoined),
                        },
                    )
                )

        if spec.flag_dead_models:
            findings.extend(_dead_model(context, model))

        findings.extend(_exposed_temporary(context, model))

        if spec.flag_staging_bypass:
            findings.extend(_staging_bypass(context, model))

    return findings


def _dead_model(context: CheckContext, model: Model) -> Findings:
    """Persistent, built, and read by nothing at all."""
    if model.persistence is not Persistence.PERSISTENT or model.is_ephemeral:
        return Findings()
    if model.materialisation not in {"table", "incremental"}:
        return Findings()

    context.examine(DEAD_MODEL.id, model.name)
    if model.downstream_models:
        return Findings()
    if context.project.views_for_model(model.name):
        return Findings()
    if any(model.name in exposure.depends_on_models for exposure in context.project.exposures):
        return Findings()
    # A reverse-ETL model's whole purpose is to be read by something outside
    # this project, so nothing downstream is expected.
    layer = context.config.layer(model.layer) if model.layer else None
    if layer is not None and not layer.may_reference_sources and layer.name == "reverse_etl":
        return Findings()

    finding = context.finding(DEAD_MODEL.id, subject=model.name, file=model.path)
    out = Findings()
    out.add(finding)
    return out


def _exposed_temporary(context: CheckContext, model: Model) -> Findings:
    """A working step relied on by the semantic layer or an exposure. FR1.4."""
    if model.persistence is not Persistence.TEMPORARY:
        return Findings()

    context.examine(TEMPORARY_MODEL_EXPOSED.id, model.name)
    views = context.project.views_for_model(model.name)
    exposures = [
        exposure.name
        for exposure in context.project.exposures
        if model.name in exposure.depends_on_models
    ]
    if not views and not exposures:
        return Findings()

    if views:
        consumer_kind = plural(len(views), "report view")
        detail = "Views: " + ", ".join(sorted(view.name for view in views)[:4]) + "."
    else:
        consumer_kind = plural(len(exposures), "declared consumer")
        detail = "Consumers: " + ", ".join(sorted(exposures)[:4]) + "."

    finding = context.finding(
        TEMPORARY_MODEL_EXPOSED.id,
        subject=model.name,
        file=model.path,
        evidence={
            "consumer_kind": consumer_kind,
            "detail": detail,
            "signal": str(model.persistence_signal),
        },
    )
    out = Findings()
    out.add(finding)
    return out


def _staging_bypass(context: CheckContext, model: Model) -> Findings:
    """A model reading two or more pipeline stages below itself.

    Uses the declared ``pipeline_stage``, not the order layers happen to appear
    in the config. A layer at stage 0 sits outside the flow (seeds, for
    instance) and can be read from anywhere without bypassing anything.
    """
    layer = context.config.layer(model.layer) if model.layer else None
    if layer is None or layer.pipeline_stage <= 0:
        return Findings()

    stages = {
        item.name: item.pipeline_stage for item in context.config.layers if item.pipeline_stage > 0
    }
    by_stage: dict[int, list[str]] = {}
    for name, stage in stages.items():
        by_stage.setdefault(stage, []).append(name)

    context.examine(STAGING_BYPASSED.id, model.name)
    findings = Findings()
    for referenced in sorted(model.depends_on_models):
        other = context.project.any_model(referenced)
        if other is None or other.layer is None:
            continue
        other_stage = stages.get(other.layer)
        if other_stage is None or other_stage >= layer.pipeline_stage - 1:
            continue
        skipped_stage = other_stage + 1
        skipped = ", ".join(sorted(by_stage.get(skipped_stage, []))) or "an intermediate"
        findings.add(
            context.finding(
                STAGING_BYPASSED.id,
                subject=model.name,
                file=model.path,
                evidence={"skipped": skipped, "referenced": referenced},
            )
        )
    return findings
