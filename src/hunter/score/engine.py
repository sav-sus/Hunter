"""Turn findings into a score from 0 to 100.

Deterministic arithmetic only, per FR7.1. No language model touches any number
here.

Three things make the result defensible rather than merely a number:

* **Every dimension has a denominator.** A dimension's score is the share of
  its checks that passed, weighted by what depends on the object. So the
  scorecard can say "73, because 57 of 63 models have no description and 63 of
  63 name no owner" and a reader can audit it.
* **Skipped dimensions are declared.** Where a dimension had nothing to measure
  (no warehouse access, no design files) its weight is redistributed across the
  rest and the report says so. A score is never quietly computed on a smaller
  basis than the reader assumes.
* **Version movement is separated.** FR7.9: a client paying for support must
  never see an apparent regression caused by an upgrade, so movement caused by
  a Hunter or house-ruleset change is reported apart from real change.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from hunter import SCORE_MODEL_VERSION, __version__
from hunter.checks.base import Denominator, dimensions_with_runnable_rules
from hunter.config.schema import HunterConfig
from hunter.enums import Dimension
from hunter.model.findings import (
    DimensionScore,
    Finding,
    ScoreResult,
    SystemicGap,
    grade_for,
    interpretation_for,
)

#: A rule must have looked at at least this many objects before failing on all
#: of them counts as systemic rather than as a small sample.
SYSTEMIC_MINIMUM = 3

#: Why a dimension was left out, in words a reader can act on.
SKIP_REASONS: dict[str, str] = {
    "no_rules": (
        "No rule for this dimension could run, because the data it needs was not available."
    ),
    "nothing_checked": (
        "Every rule for this dimension ran and found nothing of this kind to check "
        "in the repository."
    ),
    "no_weight": "The ruleset gives this dimension no weight.",
}


def dimension_scores(
    findings: Iterable[Finding],
    examined: Mapping[str, Denominator],
    config: HunterConfig,
    *,
    available: Iterable[str],
) -> list[DimensionScore]:
    """Score each dimension, and say why any of them were skipped."""
    from hunter.checks.base import REGISTRY

    runnable = dimensions_with_runnable_rules(available)

    # Per rule, not per dimension. A dimension's score is a weighted mean of
    # its rules' pass rates, each rule weighted by its declared points.
    #
    # The obvious alternative -- total points lost over total points available
    # across the dimension -- has a perverse property: a rule that examines
    # 230 models contributes a denominator 70 times larger than one examining
    # 3, so adding a rule to a dimension mechanically raises its score. That
    # kind of movement is exactly what FR7.9 asks Hunter not to present to a
    # client as if it were real change.
    lost_by_rule: dict[str, float] = {}
    counted: dict[Dimension, int] = dict.fromkeys(Dimension, 0)
    for finding in findings:
        lost_by_rule[finding.rule] = lost_by_rule.get(finding.rule, 0.0) + finding.effective_points
        counted[finding.dimension] += 1

    lost: dict[Dimension, float] = dict.fromkeys(Dimension, 0.0)
    possible: dict[Dimension, float] = dict.fromkeys(Dimension, 0.0)
    checked: dict[Dimension, int] = dict.fromkeys(Dimension, 0)
    weighted_loss: dict[Dimension, float] = dict.fromkeys(Dimension, 0.0)
    rule_weight: dict[Dimension, float] = dict.fromkeys(Dimension, 0.0)

    for rule_id, entry in sorted(examined.items()):
        try:
            spec = REGISTRY.get(rule_id)
        except KeyError:
            continue
        dimension = spec.dimension
        possible[dimension] += entry.points_available
        checked[dimension] += entry.checked
        lost[dimension] += lost_by_rule.get(rule_id, 0.0)

        if entry.points_available <= 0:
            continue
        setting = config.rule_setting(rule_id)
        weight = setting.points if setting.points is not None else spec.points
        weight = max(weight, 0.0)
        if weight <= 0:
            # A zero-point rule reports without scoring, which is how the
            # informational rules work. It carries no weight either way.
            continue
        loss_rate = min(1.0, lost_by_rule.get(rule_id, 0.0) / entry.points_available)
        weighted_loss[dimension] += weight * loss_rate
        rule_weight[dimension] += weight

    results: list[DimensionScore] = []
    for dimension in Dimension:
        weight = config.scoring.weights.get(dimension, 0.0)
        available_points = possible[dimension]

        skipped_reason: str | None = None
        if weight <= 0:
            skipped_reason = SKIP_REASONS["no_weight"]
        elif dimension not in runnable:
            skipped_reason = SKIP_REASONS["no_rules"]
        elif rule_weight[dimension] <= 0:
            skipped_reason = SKIP_REASONS["nothing_checked"]

        if skipped_reason is not None:
            results.append(
                DimensionScore(
                    dimension=dimension,
                    weight=weight,
                    effective_weight=0.0,
                    points_available=available_points,
                    points_lost=lost[dimension],
                    score=0.0,
                    grade="-",
                    scored=False,
                    skipped_reason=skipped_reason,
                    finding_count=counted[dimension],
                )
            )
            continue

        # Each rule's pass rate, weighted by the rule's declared points. The
        # denominator is built from the same weighting as the numerator, so a
        # dimension can reach 0 but never go below it.
        raw = 100.0 * (1.0 - weighted_loss[dimension] / rule_weight[dimension])
        score = round(max(0.0, min(100.0, raw)), 1)
        results.append(
            DimensionScore(
                dimension=dimension,
                weight=weight,
                effective_weight=weight,
                points_available=round(available_points, 2),
                points_lost=round(lost[dimension], 2),
                score=score,
                grade=grade_for(score),
                scored=True,
                finding_count=counted[dimension],
            )
        )

    return _renormalise(results)


def _renormalise(results: list[DimensionScore]) -> list[DimensionScore]:
    """Spread the weight of skipped dimensions across the ones that ran.

    Without this, a repository with no warehouse access would be scored out of
    93 rather than 100 and would look worse than it is for a reason that has
    nothing to do with the repository.
    """
    total = sum(entry.weight for entry in results if entry.scored)
    if total <= 0:
        return results

    factor = 100.0 / total
    adjusted: list[DimensionScore] = []
    for entry in results:
        if not entry.scored:
            adjusted.append(entry)
            continue
        adjusted.append(
            entry.model_copy(update={"effective_weight": round(entry.weight * factor, 3)})
        )
    return adjusted


def compute_score(
    findings: Iterable[Finding],
    examined: Mapping[str, Denominator],
    config: HunterConfig,
    *,
    available: Iterable[str],
    baseline: float | None = None,
    baseline_score_model_version: str | None = None,
    baseline_house_version: str | None = None,
) -> ScoreResult:
    """The whole score, and enough context to defend it.

    Args:
        findings: every finding, suppressed and unscored ones included. The
            arithmetic uses ``effective_points``, so a silenced finding still
            appears in the report and costs nothing.
        examined: what each rule looked at, which gives every dimension its
            denominator.
        available: which data sources this run had, which decides what is
            scored and what is declared skipped.
        baseline: the committed baseline total, if there is one.
        baseline_score_model_version: the score model version the baseline was
            computed with. A difference means part of any movement is caused by
            the upgrade rather than by the repository, and FR7.9 requires
            reporting the two apart.
    """
    findings = list(findings)
    dimensions = dimension_scores(findings, examined, config, available=available)

    total = round(sum(entry.contribution for entry in dimensions), 1)
    result = ScoreResult(
        total=total,
        grade=grade_for(total),
        interpretation=interpretation_for(total),
        dimensions=dimensions,
        dimensions_scored=[entry.dimension for entry in dimensions if entry.scored],
        dimensions_skipped=[entry.dimension for entry in dimensions if not entry.scored],
        weights_renormalised=any(not entry.scored for entry in dimensions),
    )

    result.systemic_gaps = systemic_gaps(findings, examined, config)

    if baseline is not None:
        result.baseline = baseline
        result.delta = round(total - baseline, 1)

        version_changed = (
            baseline_score_model_version is not None
            and baseline_score_model_version != SCORE_MODEL_VERSION
        ) or (baseline_house_version is not None and baseline_house_version != config.house_version)
        if version_changed:
            # Hunter cannot separate the two exactly without re-running the old
            # arithmetic, which it does not carry. So it attributes the movement
            # to the version change and says so, rather than presenting it as a
            # repository regression a client would be asked to explain.
            result.version_attributed_delta = result.delta
            result.real_delta = 0.0
        else:
            result.version_attributed_delta = 0.0
            result.real_delta = result.delta

    return result


def systemic_gaps(
    findings: Iterable[Finding],
    examined: Mapping[str, Denominator],
    config: HunterConfig,
) -> list[SystemicGap]:
    """Rules that failed on everything they looked at.

    Named apart from the score because they are one decision nobody has taken
    rather than many separate defects, and a weighted mean can make them look
    smaller than they are.
    """
    from hunter.checks.base import REGISTRY
    from hunter.enums import SEVERITY_ORDER

    counts: dict[str, int] = {}
    examples: dict[str, Finding] = {}
    for finding in findings:
        if not finding.counts_towards_score:
            continue
        counts[finding.rule] = counts.get(finding.rule, 0) + 1
        examples.setdefault(finding.rule, finding)

    gaps: list[SystemicGap] = []
    for rule_id, failed in counts.items():
        entry = examined.get(rule_id)
        if entry is None or entry.checked < SYSTEMIC_MINIMUM:
            continue
        if failed < entry.checked:
            continue
        try:
            spec = REGISTRY.get(rule_id)
        except KeyError:
            continue
        if spec.points <= 0 or spec.about_coverage:
            # A zero-point rule reports without scoring, and a coverage rule
            # reports what Hunter could not check. Neither is a gap in the
            # repository.
            continue
        example = examples[rule_id]
        setting = config.rule_setting(rule_id)
        gaps.append(
            SystemicGap(
                rule=rule_id,
                dimension=spec.dimension,
                severity=setting.severity or spec.severity,
                summary=spec.title.split(":")[0],
                consequence=example.consequence,
                failed=failed,
                checked=entry.checked,
                plain_heading=spec.plain_heading,
            )
        )

    gaps.sort(key=lambda gap: (SEVERITY_ORDER[gap.severity], -gap.checked, gap.rule))
    return gaps


def report_meta(
    config: HunterConfig,
    *,
    repo: str | None = None,
    commit: str | None = None,
) -> dict[str, str | None]:
    """The version stamp every report carries. FR7.8."""
    return {
        "hunter_version": __version__,
        "house_ruleset_version": config.house_version,
        "score_model_version": SCORE_MODEL_VERSION,
        "repo": repo,
        "commit": commit,
    }


def fails_build(result: ScoreResult, config: HunterConfig) -> tuple[bool, str | None]:
    """Whether this score should fail a build, and why.

    Advisory mode never fails. FR11.6 and FR11.7.
    """
    from hunter.enums import PrMode

    mode = config.pull_request.mode
    if mode is PrMode.ADVISORY:
        return False, None

    threshold = config.scoring.fail_under
    if threshold is not None and result.total < threshold:
        return True, (f"The score is {result.total:g}, below the agreed threshold of {threshold}.")

    if (
        config.scoring.fail_on_regression
        and result.real_delta is not None
        and result.real_delta < 0
    ):
        return True, (
            f"The score fell by {abs(result.real_delta):g} points against the committed baseline."
        )

    return False, None
