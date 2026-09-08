"""Findings, dimension scores and the interpretation bands.

Every deduction names its rule, the affected object, and the file and line, per
FR7.3. Every finding carries a consequence line in business terms, per FR14.2:
"three dashboards will show incorrect figures if this changes", not "high
severity: relationships test missing".

The consequence line is written from a template held with the rule and filled
with that finding's own evidence. Nothing is generated. That is what makes the
plain-language layer traceable to a deterministic finding.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from hunter.enums import Dimension, Severity

#: FR7.10. One set of thresholds serves both the letter grade and the
#: interpretation panel, so the two can never disagree.
SCORE_BANDS: tuple[tuple[int, str, str], ...] = (
    (85, "A", "Well maintained. Safe to build on"),
    (70, "B", "Sound, with known gaps"),
    (55, "C", "Workable but accumulating risk"),
    (40, "D", "Fragile. Changes are likely to break things"),
    (0, "E", "Unmanaged. Treat findings as a remediation backlog"),
)


def grade_for(score: float) -> str:
    """Letter grade for a 0 to 100 score."""
    for floor, letter, _ in SCORE_BANDS:
        if score >= floor:
            return letter
    return "E"


def interpretation_for(score: float) -> str:
    """The panel text shown beneath the number, never in place of it. FR7.10."""
    for floor, _, text in SCORE_BANDS:
        if score >= floor:
            return text
    return SCORE_BANDS[-1][2]


class Finding(BaseModel):
    """One thing that is wrong, with the evidence behind it."""

    model_config = ConfigDict(extra="forbid")

    rule: str
    dimension: Dimension
    severity: Severity
    subject: str
    subject_kind: str = "model"
    summary: str
    consequence: str
    points: float = 0.0
    file: str | None = None
    line: int | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)

    #: How sure Hunter is. Below the configured floor a finding is reported as a
    #: suggestion and excluded from the score. FR3.6.
    confidence: float = 1.0
    scored: bool = True

    #: Set when a live ignore covers this finding. It still appears on the site,
    #: with its reason, so a silenced finding is visible rather than gone.
    suppressed: bool = False
    suppression_reason: str | None = None
    suppression_expires: dt.date | None = None

    # Attribution. Routed by owner, reported by team. FR6.3 forbids a
    # per-person league table.
    owner: str | None = None
    team: str | None = None
    introduced_by_commit: str | None = None
    introduced_in_pr: str | None = None
    first_seen: dt.date | None = None

    @property
    def counts_towards_score(self) -> bool:
        return self.scored and not self.suppressed

    @property
    def effective_points(self) -> float:
        return self.points if self.counts_towards_score else 0.0

    @property
    def location(self) -> str:
        if self.file and self.line:
            return f"{self.file}:{self.line}"
        return self.file or self.subject

    def age_days(self, as_of: dt.date | None = None) -> int | None:
        """How long this finding has been open, in days. FR8.1."""
        if self.first_seen is None:
            return None
        return ((as_of or dt.date.today()) - self.first_seen).days

    def sort_key(self) -> tuple[Any, ...]:
        """Deterministic order: severity, then points, then name. 11.9."""
        from hunter.enums import SEVERITY_ORDER

        return (
            SEVERITY_ORDER[self.severity],
            -self.points,
            self.rule,
            self.subject,
            self.file or "",
            self.line or 0,
        )


class DimensionScore(BaseModel):
    """One dimension's contribution to the total."""

    model_config = ConfigDict(extra="forbid")

    dimension: Dimension
    weight: float
    effective_weight: float
    points_available: float
    points_lost: float
    score: float
    grade: str
    scored: bool = True
    skipped_reason: str | None = None
    finding_count: int = 0

    @property
    def contribution(self) -> float:
        """Points this dimension contributes to the 0 to 100 total."""
        if not self.scored:
            return 0.0
        return self.effective_weight * (self.score / 100.0)


class ScoreResult(BaseModel):
    """The score, and enough context to defend it."""

    model_config = ConfigDict(extra="forbid")

    total: float
    grade: str
    interpretation: str
    dimensions: list[DimensionScore] = Field(default_factory=list)

    baseline: float | None = None
    delta: float | None = None

    #: Movement caused by a Hunter or house-ruleset upgrade, reported apart from
    #: real repository change. FR7.9: a client on a support plan must never see
    #: an apparent regression caused by an upgrade.
    version_attributed_delta: float | None = None
    real_delta: float | None = None

    dimensions_scored: list[Dimension] = Field(default_factory=list)
    dimensions_skipped: list[Dimension] = Field(default_factory=list)
    weights_renormalised: bool = False

    @property
    def passed(self) -> bool:
        return self.total > 0

    def dimension(self, name: Dimension) -> DimensionScore | None:
        for entry in self.dimensions:
            if entry.dimension is name:
                return entry
        return None


class Coverage(BaseModel):
    """Coverage percentages reported beside the score, not folded into it.

    Section 9: a repository can be internally healthy while implementing only
    part of the design, so design coverage is reported separately.
    """

    model_config = ConfigDict(extra="forbid")

    conceptual_entities: int = 0
    designed_entities: int = 0
    built_entities: int = 0
    deployed_entities: int = 0

    conceptual_designed: int = 0
    designed_and_built: int = 0
    off_plan_built: int = 0
    off_plan_approved: int = 0
    built_disabled: int = 0
    designed_not_started: int = 0
    unmanaged_production: int = 0

    #: Model-level and column-level documentation are counted apart. The pilot
    #: describes 1,615 of 1,615 columns and 0 of 54 warehouse tables, so a
    #: single figure would report a well-documented project as undocumented.
    documented_entities: int = 0
    column_documented_entities: int = 0
    tested_entities: int = 0

    @staticmethod
    def _percent(part: int, whole: int) -> float | None:
        if whole <= 0:
            return None
        return round(100.0 * part / whole, 1)

    @property
    def design_coverage(self) -> float | None:
        """Share of the business model that has been designed. FR8.4."""
        return self._percent(self.conceptual_designed, self.conceptual_entities)

    @property
    def delivery_coverage(self) -> float | None:
        """Share of the design that has been built. FR17.2."""
        return self._percent(self.designed_and_built, self.designed_entities)

    @property
    def documentation_coverage(self) -> float | None:
        """Share of built entities carrying a table-level description."""
        return self._percent(self.documented_entities, self.built_entities)

    @property
    def column_documentation_coverage(self) -> float | None:
        """Share of built entities with every column described."""
        return self._percent(self.column_documented_entities, self.built_entities)

    @property
    def test_coverage(self) -> float | None:
        return self._percent(self.tested_entities, self.built_entities)
