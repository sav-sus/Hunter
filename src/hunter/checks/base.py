"""The check framework: rules, context, and how a finding gets made.

Every rule is declared here with its dimension, severity, points and its
plain-language consequence template. Declaring them in one place is what makes
NFR6 hold: there are no thresholds or point values buried in check modules.

The consequence template is the mechanism behind F14.2 and F14.8. A finding
reads "three dashboards will show incorrect figures if this changes", not "high
severity: relationships test missing". The template is filled from that
finding's own evidence, so nothing is generated and every consequence line
traces back to a deterministic finding.

A check module exposes one function::

    def run(context: CheckContext) -> list[Finding]

and builds findings through ``context.finding(...)``, which applies rule
overrides, ignores and exposure weighting centrally. A check that constructs a
Finding directly bypasses all of that.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol

from hunter.config.register import Register
from hunter.config.schema import HunterConfig
from hunter.enums import Dimension, Severity
from hunter.model.align import Alignment
from hunter.model.entities import Project
from hunter.model.findings import Finding
from hunter.model.graph import Graph

#: Data a rule needs before it can run. A rule whose requirements are unmet is
#: skipped, and its dimension's weight is renormalised rather than the project
#: being scored as though the rule had passed.
Requirement = str

REQ_MANIFEST: Requirement = "manifest"
REQ_DBML: Requirement = "dbml"
REQ_CONCEPTUAL: Requirement = "conceptual"
REQ_LOOKML: Requirement = "lookml"
REQ_DROUGHTY: Requirement = "droughty"
REQ_WAREHOUSE: Requirement = "warehouse"
REQ_GIT: Requirement = "git"


@dataclass(frozen=True)
class Rule:
    """One rule Hunter can report.

    ``consequence`` is a format template. Placeholders are filled from the
    finding's evidence plus the subject label, so a rule with a placeholder that
    the evidence cannot fill is a bug the rule test will catch.
    """

    id: str
    dimension: Dimension
    severity: Severity
    points: float
    title: str
    consequence: str
    plain_heading: str
    requires: tuple[Requirement, ...] = (REQ_MANIFEST,)
    confidence: float = 1.0
    #: Whether points scale with how much depends on the object. FR7.4.
    exposure_weighted: bool = True

    #: True for rules that report what Hunter could not check rather than what
    #: the repository got wrong. These belong on the "what was not checked"
    #: page and must never appear as a gap in the repository: "Hunter could not
    #: resolve this table name" is not something the team failed to do.
    about_coverage: bool = False

    def format_title(self, values: dict[str, Any]) -> str:
        return _fill(self.title, values)

    def format_consequence(self, values: dict[str, Any]) -> str:
        return _fill(self.consequence, values)


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    """``1 column`` or ``58 columns``.

    Consequence lines are read by people, so "1 columns" is not acceptable
    output. Checks build count phrases through this rather than interpolating a
    bare number next to a fixed noun.
    """
    word = singular if count == 1 else (plural_form or f"{singular}s")
    return f"{count} {word}"


class _Missing(dict[str, Any]):
    """Leaves an unfilled placeholder visible rather than raising.

    A rule with a placeholder its evidence cannot fill should show up in review
    as ``{whatever}`` in the text, not crash a client's run.
    """

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _fill(template: str, values: dict[str, Any]) -> str:
    try:
        return template.format_map(_Missing(values))
    except (IndexError, ValueError):
        return template


class Registry:
    """Every rule, by id."""

    def __init__(self) -> None:
        self._rules: dict[str, Rule] = {}

    def add(self, rule: Rule) -> Rule:
        if rule.id in self._rules:
            raise ValueError(f"rule {rule.id!r} is declared twice")
        self._rules[rule.id] = rule
        return rule

    def get(self, rule_id: str) -> Rule:
        try:
            return self._rules[rule_id]
        except KeyError:
            raise KeyError(f"no such rule: {rule_id!r}") from None

    def ids(self) -> set[str]:
        return set(self._rules)

    def by_dimension(self, dimension: Dimension) -> list[Rule]:
        return sorted(
            (rule for rule in self._rules.values() if rule.dimension is dimension),
            key=lambda rule: rule.id,
        )

    def all(self) -> list[Rule]:
        return sorted(self._rules.values(), key=lambda rule: rule.id)


REGISTRY = Registry()


def rule(
    rule_id: str,
    *,
    dimension: Dimension,
    severity: Severity,
    points: float,
    title: str,
    consequence: str,
    plain_heading: str,
    requires: tuple[Requirement, ...] = (REQ_MANIFEST,),
    confidence: float = 1.0,
    exposure_weighted: bool = True,
    about_coverage: bool = False,
) -> Rule:
    """Declare a rule and add it to the registry."""
    return REGISTRY.add(
        Rule(
            id=rule_id,
            dimension=dimension,
            severity=severity,
            points=points,
            title=title,
            consequence=consequence,
            plain_heading=plain_heading,
            requires=requires,
            confidence=confidence,
            exposure_weighted=exposure_weighted,
            about_coverage=about_coverage,
        )
    )


@dataclass
class Denominator:
    """How much a rule could have deducted, and how much it did.

    Without this a score is a number with no denominator: 283 points lost out
    of what? Checks call ``examine`` for every object they look at, pass or
    fail, so the engine can say "62, because 147 of 389 checks failed" and a
    reader can audit it.
    """

    rule_id: str
    checked: int = 0
    points_available: float = 0.0


@dataclass
class CheckContext:
    """Everything a check may read, and the one way it reports.

    Checks are pure over this: they read it and return findings. Nothing here
    opens a file or runs a command.
    """

    project: Project
    graph: Graph
    config: HunterConfig
    register: Register
    alignment: Alignment
    as_of: dt.date = field(default_factory=dt.date.today)

    #: Set by the runner, so a check can ask what was available this run.
    available: frozenset[Requirement] = frozenset()

    #: What each rule examined this run, filled by ``examine``.
    examined: dict[str, Denominator] = field(default_factory=dict)

    def has(self, *requirements: Requirement) -> bool:
        return all(requirement in self.available for requirement in requirements)

    def examine(
        self,
        rule_id: str,
        subject: str,
        *,
        weight: float | None = None,
        count: int = 1,
    ) -> None:
        """Record that a rule looked at an object, whether or not it failed.

        Weighted the same way a finding would be, so the denominator and the
        numerator are always on the same scale and a dimension score cannot go
        below zero.
        """
        spec = REGISTRY.get(rule_id)
        setting = self.config.rule_setting(rule_id)
        if not setting.enabled:
            return

        model = self.project.any_model(subject)
        if model is not None and not model.is_scoreable:
            return

        points = setting.points if setting.points is not None else spec.points
        factor = 1.0
        if spec.exposure_weighted and self.config.scoring.exposure_weighting:
            if weight is not None:
                factor = weight
            else:
                enabled_model = self.project.models.get(subject)
                factor = enabled_model.exposure_weight if enabled_model else 1.0

        entry = self.examined.setdefault(rule_id, Denominator(rule_id=rule_id))
        entry.checked += count
        entry.points_available += points * factor * count

    def label_for(self, subject: str) -> str:
        """Business name for an object, falling back to its technical name.

        FR14.3: summary views name entities the way the business does, with the
        physical name available underneath.
        """
        for row in self.alignment.rows:
            if subject in {row.model_name, row.designed_name, row.conceptual_name}:
                return row.label
        return subject

    def consumer_summary(self, model_name: str) -> str:
        """A complete clause describing what depends on a model.

        Returns the verb as well as the count, so a consequence template can
        drop it in without producing "1 other model depend on it". Used so a
        finding says what breaks rather than how severe it is.
        """
        views = self.project.views_for_model(model_name)
        field_count = sum(len(view.fields) for view in views)
        model = self.project.models.get(model_name)
        downstream = len(model.downstream_models) if model else 0

        parts: list[str] = []
        if field_count:
            parts.append(f"{field_count} report field{'s' if field_count != 1 else ''}")
        if downstream:
            parts.append(f"{downstream} other model{'s' if downstream != 1 else ''}")

        if not parts:
            return "nothing downstream depends on it"
        subject = " and ".join(parts)
        many = len(parts) > 1 or field_count > 1 or downstream > 1
        return f"{subject} depend{'' if many else 's'} on it"

    def finding(
        self,
        rule_id: str,
        *,
        subject: str,
        subject_kind: str = "model",
        file: str | None = None,
        line: int | None = None,
        evidence: dict[str, Any] | None = None,
        confidence: float | None = None,
        owner: str | None = None,
        team: str | None = None,
        exposure_weight: float | None = None,
        points_scale: float = 1.0,
    ) -> Finding | None:
        """Build one finding, applying every policy centrally.

        Returns None where the rule is disabled, so a check can build findings
        without first asking whether it should.

        ``points_scale`` scales the deduction for a rule that aggregates. A
        model missing 1 of 58 column descriptions should not cost the same as
        one missing all 58, and the denominator stays one check per model
        either way, so table-level and column-level gaps weigh comparably.
        """
        spec = REGISTRY.get(rule_id)
        setting = self.config.rule_setting(rule_id)
        if not setting.enabled:
            return None

        severity = setting.severity or spec.severity
        base_points = setting.points if setting.points is not None else spec.points

        values = dict(evidence or {})
        values.setdefault("subject", subject)
        values.setdefault("label", self.label_for(subject))

        weight = 1.0
        if spec.exposure_weighted and self.config.scoring.exposure_weighting:
            if exposure_weight is not None:
                weight = exposure_weight
            else:
                model = self.project.models.get(subject)
                weight = model.exposure_weight if model else 1.0

        actual_confidence = spec.confidence if confidence is None else confidence
        scored = actual_confidence >= self.config.scoring.min_confidence_to_score

        model = self.project.any_model(subject)
        if model is not None and not model.is_scoreable:
            # Vendored code: reported for completeness, never scored.
            scored = False

        ignore = self.register.ignore_for(rule_id, subject, self.as_of)

        return Finding(
            rule=rule_id,
            dimension=spec.dimension,
            severity=severity,
            subject=subject,
            subject_kind=subject_kind,
            summary=spec.format_title(values),
            consequence=spec.format_consequence(values),
            points=round(base_points * weight * points_scale, 3),
            file=file,
            line=line,
            evidence=dict(sorted(values.items())),
            confidence=actual_confidence,
            scored=scored,
            suppressed=ignore is not None,
            suppression_reason=ignore.reason if ignore else None,
            suppression_expires=ignore.expires if ignore else None,
            owner=owner or (model.owner if model else None),
            team=team,
            introduced_by_commit=None,
            first_seen=model.created_at if model else None,
        )


class Findings(list[Finding]):
    """Collects findings, dropping the None a disabled rule returns.

    ``context.finding`` returns None when a rule is switched off, so a check
    can build findings without first asking whether it should. This keeps that
    convenience without every check ending in a filter.
    """

    def add(self, finding: Finding | None) -> None:
        if finding is not None:
            self.append(finding)

    def extend_from(self, findings: Iterable[Finding | None]) -> None:
        for finding in findings:
            self.add(finding)


class Check(Protocol):
    """What every check module provides."""

    def __call__(self, context: CheckContext) -> list[Finding]: ...


def collect(
    checks: Iterable[Callable[[CheckContext], list[Finding]]],
    context: CheckContext,
) -> list[Finding]:
    """Run checks and return their findings in a deterministic order."""
    findings: list[Finding] = []
    for check in checks:
        findings.extend(item for item in check(context) if item is not None)
    findings.sort(key=lambda item: item.sort_key())
    return findings


def rules_runnable(available: Iterable[Requirement]) -> set[str]:
    """Rule ids whose data requirements are met this run."""
    have = set(available)
    return {rule.id for rule in REGISTRY.all() if set(rule.requires) <= have}


def dimensions_with_runnable_rules(available: Iterable[Requirement]) -> set[Dimension]:
    """Dimensions that have at least one runnable rule.

    Drives weight renormalisation: a dimension with nothing to measure is
    excluded and declared, rather than scored as though it passed.
    """
    have = set(available)
    return {rule.dimension for rule in REGISTRY.all() if set(rule.requires) <= have}
