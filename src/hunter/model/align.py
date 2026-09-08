"""The alignment chain: one row per entity, across every level.

Section 17 of the requirements document defines a three-way reconciliation
between the design, the repository and the warehouse. This extends it to five
points, so a gap is attributable to a specific step rather than to "somewhere":

    conceptual -> logical -> physical design -> repository -> warehouse

Each link reports separately. Without warehouse access the last column reports
``unknown`` rather than ``absent``, per FR17.7: assuming a table is missing
because Hunter could not look is worse than saying it did not look.

Two states are additions to the seven in the requirements document, both forced
by real data:

* ``built_disabled``. Six pilot models are built but switched off by a dbt
  variable. Calling those "designed, not started" would be wrong.
* ``approved_off_plan``. The register lets a team accept an off-plan build with
  a reason and a review date. It still appears here, so the approval is visible
  rather than invisible.

The conceptual diagram's own colour coding is treated as a claim. Hunter
computes the real state and reports where the two disagree, which is the
"is the picture still true" question.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hunter.config.register import Register
from hunter.config.schema import HunterConfig
from hunter.enums import (
    ALIGNMENT_STATE_LABELS,
    ALIGNMENT_STATE_MEANINGS,
    AlignmentState,
    Presence,
)
from hunter.ingest.diagrams import LogicalData
from hunter.model.entities import Project
from hunter.model.findings import Coverage
from hunter.model.match import Index, Match, normalise_domain_value, qualified_key

#: Legend words that mean "this exists in production".
BUILT_CLAIMS = frozenset({"built", "live", "delivered", "done", "complete", "implemented"})

#: Legend words that mean "this is not built yet".
PLANNED_CLAIMS = frozenset({"planned", "proposed", "designed", "backlog", "future"})

#: States consistent with a claim of "built".
BUILT_STATES = frozenset(
    {
        AlignmentState.DESIGNED_AND_DELIVERED,
        AlignmentState.BUILT_NOT_DEPLOYED,
        AlignmentState.BUILT_OFF_PLAN,
        AlignmentState.APPROVED_OFF_PLAN,
    }
)

#: States consistent with a claim of "planned".
PLANNED_STATES = frozenset(
    {
        AlignmentState.DESIGNED_NOT_STARTED,
        AlignmentState.CONCEPTUAL_ONLY,
        AlignmentState.LOGICAL_ONLY,
        AlignmentState.NOT_PRESENT,
    }
)


@dataclass
class AlignmentRow:
    """One entity, seen at every level Hunter can see."""

    key: str
    business_name: str | None = None
    domain: str | None = None

    conceptual: Presence = Presence.ABSENT
    logical: Presence = Presence.UNKNOWN
    designed: Presence = Presence.ABSENT
    repo: Presence = Presence.ABSENT
    warehouse: Presence = Presence.UNKNOWN

    conceptual_name: str | None = None
    designed_name: str | None = None
    model_name: str | None = None

    state: AlignmentState = AlignmentState.NOT_PRESENT
    grain: str | None = None
    owner: str | None = None

    claimed_status: str | None = None
    claim_matches_reality: bool | None = None

    match_method: str = "exact"
    match_confidence: float = 1.0
    match_candidates: tuple[str, ...] = ()

    approved_off_plan: bool = False
    approval_reason: str | None = None
    design_file: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        """What a non-technical reader sees. FR14.3, FR17.5."""
        return self.business_name or (self.key.split("/")[-1].replace("_", " "))

    @property
    def state_label(self) -> str:
        return ALIGNMENT_STATE_LABELS[self.state]

    @property
    def state_meaning(self) -> str:
        return ALIGNMENT_STATE_MEANINGS[self.state]

    @property
    def is_built(self) -> bool:
        return self.repo is Presence.PRESENT

    @property
    def technical_name(self) -> str | None:
        """Physical name, shown under the business name on demand. FR14.3."""
        return self.model_name or self.designed_name


@dataclass
class Alignment:
    """The whole chain, plus the counts the scorecard reports."""

    rows: list[AlignmentRow] = field(default_factory=list)
    coverage: Coverage = field(default_factory=Coverage)
    warehouse_known: bool = False

    def by_state(self, state: AlignmentState) -> list[AlignmentRow]:
        return [row for row in self.rows if row.state is state]

    def state_counts(self) -> dict[AlignmentState, int]:
        """Counts per state, for the trend in FR17.6."""
        counts: dict[AlignmentState, int] = {}
        for row in self.rows:
            counts[row.state] = counts.get(row.state, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: item[0].value))

    def by_domain(self) -> dict[str, list[AlignmentRow]]:
        """Grouped for the site table. FR17.5."""
        grouped: dict[str, list[AlignmentRow]] = {}
        for row in self.rows:
            grouped.setdefault(row.domain or "ungrouped", []).append(row)
        return dict(sorted(grouped.items()))

    def stale_claims(self) -> list[AlignmentRow]:
        """Rows where the authored diagram disagrees with reality."""
        return [row for row in self.rows if row.claim_matches_reality is False]

    def ambiguous_matches(self) -> list[AlignmentRow]:
        return [row for row in self.rows if row.match_method == "ambiguous"]


def _decide_state(
    designed: Presence,
    repo: Presence,
    warehouse: Presence,
    *,
    approved_off_plan: bool,
    conceptual: Presence = Presence.ABSENT,
    logical: Presence = Presence.UNKNOWN,
) -> AlignmentState:
    """The state table from section 17, extended by two states."""
    if designed is Presence.PRESENT:
        if repo is Presence.PRESENT:
            if warehouse is Presence.ABSENT:
                return AlignmentState.BUILT_NOT_DEPLOYED
            return AlignmentState.DESIGNED_AND_DELIVERED
        if repo is Presence.DISABLED:
            return AlignmentState.BUILT_DISABLED
        if warehouse is Presence.PRESENT:
            return AlignmentState.LIVE_WITHOUT_CODE
        return AlignmentState.DESIGNED_NOT_STARTED

    if repo is Presence.PRESENT:
        if approved_off_plan:
            return AlignmentState.APPROVED_OFF_PLAN
        if warehouse is Presence.ABSENT:
            return AlignmentState.OFF_PLAN_NOT_DEPLOYED
        return AlignmentState.BUILT_OFF_PLAN
    if repo is Presence.DISABLED:
        return AlignmentState.OFF_PLAN_NOT_DEPLOYED
    if warehouse is Presence.PRESENT:
        return AlignmentState.UNTRACKED_TABLE
    if conceptual is Presence.PRESENT:
        return AlignmentState.CONCEPTUAL_ONLY
    if logical is Presence.PRESENT:
        return AlignmentState.LOGICAL_ONLY
    return AlignmentState.NOT_PRESENT


def _claim_matches(claim: str | None, state: AlignmentState) -> bool | None:
    """Whether the diagram's claim agrees with the computed state.

    Returns None where there is no claim, or where the claim is a deviation
    marker that carries no expectation of its own.
    """
    if not claim:
        return None
    lowered = claim.strip().lower()
    if lowered in BUILT_CLAIMS:
        return state in BUILT_STATES
    if lowered in PLANNED_CLAIMS:
        return state in PLANNED_STATES
    return None


def _alignment_models(project: Project, config: HunterConfig) -> tuple[dict[str, str], set[str]]:
    """Client-owned models in layers that hold modelled entities.

    Returns the enabled ones and the disabled ones. Staging and integration
    models are working steps, not entities: including them would report 129
    staging models as built off-plan.
    """
    layers = {layer.name for layer in config.layers if layer.in_alignment}
    enabled: dict[str, str] = {}
    disabled: set[str] = set()
    for name, model in project.models.items():
        if model.layer in layers and not model.vendored:
            enabled[name] = name
    for name, model in project.disabled_models.items():
        if model.layer in layers and not model.vendored:
            disabled.add(name)
    return enabled, disabled


def build_alignment(
    project: Project,
    config: HunterConfig,
    register: Register,
    *,
    logical: LogicalData | None = None,
) -> Alignment:
    """Build one row per entity across every level Hunter can see."""
    alignment = Alignment(warehouse_known=project.has_warehouse)

    suffixes = tuple(spec.suffix for spec in config.entities) or None
    prefixes = tuple(layer.prefix for layer in config.layers if layer.prefix) or None
    index_kwargs = {}
    if suffixes:
        index_kwargs["suffixes"] = suffixes
    if prefixes:
        index_kwargs["prefixes"] = prefixes

    enabled_models, disabled_models = _alignment_models(project, config)
    all_model_names = sorted(set(enabled_models) | disabled_models)

    design_index = Index.build(sorted(project.designed), **index_kwargs)
    model_index = Index.build(all_model_names, **index_kwargs)
    implements = register.implements_map()

    rows: dict[str, AlignmentRow] = {}

    def key_for(name: str) -> str:
        return qualified_key(
            name,
            suffixes=index_kwargs.get("suffixes", ()) or (),
            prefixes=index_kwargs.get("prefixes", ()) or (),
        )

    def row_for(name: str) -> AlignmentRow:
        key = key_for(name)
        row = rows.get(key)
        if row is None:
            row = AlignmentRow(key=key)
            rows[key] = row
        return row

    # 1. Every designed entity. The design is the model of record, so it
    #    anchors the row.
    for name, design in sorted(project.designed.items()):
        row = row_for(name)
        row.designed = Presence.PRESENT
        row.designed_name = name
        row.domain = design.domain or row.domain
        row.grain = design.grain_note
        row.design_file = design.source_file

        match = model_index.find(name, declared=None)
        _apply_match(row, match)
        if match.matched:
            _set_repo(row, match.target, enabled_models, disabled_models)

    # 2. Every model in an alignment layer, whether or not it was designed.
    for name in all_model_names:
        declared_design = implements.get(name)
        match = design_index.find(name, declared=declared_design)
        if match.target is not None:
            row = row_for(match.target)
            if row.model_name is None:
                _apply_match(row, match)
                _set_repo(row, name, enabled_models, disabled_models)
            continue
        row = row_for(name)
        if row.model_name is None:
            _set_repo(row, name, enabled_models, disabled_models)
        if match.method == "ambiguous":
            row.match_method = "ambiguous"
            row.match_candidates = match.candidates
            row.notes.append(
                "This model could be either of two designed entities, so Hunter did "
                "not choose. Add an implements entry to the register to settle it."
            )

    # 3. Conceptual entities, matched onto whatever exists below them.
    conceptual_index = Index.build(
        sorted(set(project.designed) | set(all_model_names)), **index_kwargs
    )
    for name, concept in sorted(project.conceptual.items()):
        match = conceptual_index.find(name, declared=implements.get(name))
        row = row_for(match.target or name)
        row.conceptual = Presence.PRESENT
        row.conceptual_name = name
        row.claimed_status = concept.claimed_status
        if concept.business_name:
            row.business_name = concept.business_name
        if row.domain is None:
            row.domain = concept.domain
        if match.method == "ambiguous":
            row.match_candidates = match.candidates
            row.notes.append("This business entity matches more than one designed table by name.")

    # 4. Logical presence, where a logical diagram was authored.
    if logical is not None and logical.entities:
        logical_keys = {key_for(name) for name in logical.entities}
        for key, row in rows.items():
            row.logical = Presence.PRESENT if key in logical_keys else Presence.ABSENT
        for name in sorted(logical.entities):
            key = key_for(name)
            if key not in rows:
                row = row_for(name)
                row.logical = Presence.PRESENT
                row.business_name = logical.entities[name] or None

    # 5. Approvals, owners, state and the claim comparison.
    domain_prefixes = index_kwargs.get("prefixes", ()) or ()
    for row in rows.values():
        row.domain = normalise_domain_value(row.domain, prefixes=domain_prefixes)
        model_name = row.model_name
        approval = register.approval(model_name) if model_name else None
        row.approved_off_plan = approval is not None
        row.approval_reason = approval.reason if approval else None

        if model_name:
            model = project.any_model(model_name)
            if model is not None:
                row.owner = model.owner or row.owner
                if row.domain is None:
                    row.domain = model.domain
        if row.owner is None and model_name:
            entry = register.entry(model_name)
            if entry is not None:
                row.owner = entry.owner
                row.grain = row.grain or entry.grain

        row.state = _decide_state(
            row.designed,
            row.repo,
            row.warehouse,
            approved_off_plan=row.approved_off_plan,
            conceptual=row.conceptual,
            logical=row.logical,
        )
        row.claim_matches_reality = _claim_matches(row.claimed_status, row.state)

    alignment.rows = sorted(rows.values(), key=lambda row: (row.domain or "~", row.key))
    alignment.coverage = _coverage(alignment, project)
    return alignment


def _apply_match(row: AlignmentRow, match: Match) -> None:
    if match.matched:
        row.match_method = match.method
        row.match_confidence = match.confidence
    elif match.method == "ambiguous":
        row.match_method = "ambiguous"
        row.match_confidence = 0.0
        row.match_candidates = match.candidates


def _set_repo(
    row: AlignmentRow,
    model_name: str | None,
    enabled: dict[str, str],
    disabled: set[str],
) -> None:
    if model_name is None:
        return
    row.model_name = model_name
    if model_name in enabled:
        row.repo = Presence.PRESENT
    elif model_name in disabled:
        row.repo = Presence.DISABLED
    else:
        row.repo = Presence.ABSENT


def _coverage(alignment: Alignment, project: Project) -> Coverage:
    """Counts reported beside the score rather than folded into it."""
    coverage = Coverage()
    coverage.conceptual_entities = sum(
        1 for row in alignment.rows if row.conceptual is Presence.PRESENT
    )
    coverage.designed_entities = sum(
        1 for row in alignment.rows if row.designed is Presence.PRESENT
    )
    coverage.built_entities = sum(1 for row in alignment.rows if row.is_built)
    coverage.conceptual_designed = sum(
        1
        for row in alignment.rows
        if row.conceptual is Presence.PRESENT and row.designed is Presence.PRESENT
    )
    coverage.designed_and_built = sum(
        1 for row in alignment.rows if row.designed is Presence.PRESENT and row.is_built
    )

    counts = alignment.state_counts()
    coverage.off_plan_built = counts.get(AlignmentState.BUILT_OFF_PLAN, 0)
    coverage.off_plan_approved = counts.get(AlignmentState.APPROVED_OFF_PLAN, 0)
    coverage.built_disabled = counts.get(AlignmentState.BUILT_DISABLED, 0)
    coverage.designed_not_started = counts.get(AlignmentState.DESIGNED_NOT_STARTED, 0)
    coverage.unmanaged_production = counts.get(AlignmentState.UNTRACKED_TABLE, 0) + counts.get(
        AlignmentState.LIVE_WITHOUT_CODE, 0
    )

    documented = 0
    column_documented = 0
    tested = 0
    tested_models = {test.tests_model for test in project.tests if test.is_key_test}
    for row in alignment.rows:
        if not row.is_built or row.model_name is None:
            continue
        model = project.model(row.model_name)
        if model is None:
            continue
        if model.has_description:
            documented += 1
        if model.columns and all(column.has_description for column in model.columns):
            column_documented += 1
        if row.model_name in tested_models:
            tested += 1
    coverage.documented_entities = documented
    coverage.column_documented_entities = column_documented
    coverage.tested_entities = tested
    return coverage
