"""``report.json``: the one output everything else is a view over.

Section 11.8. The site, the pull request comment and the showcase all render
from this file, so a caller that wants to build something else needs nothing
from Hunter but this.

``generated_at`` sits in ``meta`` and nowhere else. That is what lets the
golden-file tests compare two runs of the same commit and get an identical
payload, which is how FR7.7 and NFR3 are enforced rather than merely intended.
Every collection is sorted before emitting, per section 11.9: unsorted
dictionary iteration is the usual cause of output that differs between runs.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from hunter.enums import ALIGNMENT_STATE_LABELS, ALIGNMENT_STATE_MEANINGS
from hunter.run import RunResult

#: Bumped when the shape of report.json changes in a way a consumer would
#: notice. FR15.2: a machine-readable output other tools can rely on.
REPORT_SCHEMA_VERSION = "1"


def build_report(result: RunResult, *, generated_at: dt.datetime | None = None) -> dict[str, Any]:
    """Assemble the whole report as plain data."""
    stamped = generated_at or dt.datetime.now(dt.UTC)
    payload = stable_payload(result)
    payload["meta"] = {
        **result.meta,
        "attribution": result.config.branding.attribution,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": stamped.isoformat(),
        "as_of": result.as_of.isoformat(),
        "sources_read": result.sources_read,
        "dimensions_scored": [str(item) for item in result.score.dimensions_scored],
        "dimensions_skipped": [str(item) for item in result.score.dimensions_skipped],
        "data_available": sorted(result.available),
    }
    return payload


def stable_payload(result: RunResult) -> dict[str, Any]:
    """Everything except ``meta``.

    This is what the golden-file tests compare, so nothing in here may carry a
    timestamp, a path outside the repository or an unsorted collection.
    """
    return {
        "score": _score(result),
        "coverage": _coverage(result),
        "inventory": _inventory(result),
        "alignment": _alignment(result),
        "findings": _findings(result),
        "systemic_gaps": [gap.model_dump(mode="json") for gap in result.score.systemic_gaps],
        "conventions": _conventions(result),
        "parse_issues": [
            issue.model_dump(mode="json")
            for issue in sorted(
                result.project.parse_issues,
                key=lambda item: (item.source, item.subject or "", item.message),
            )
        ],
    }


def _score(result: RunResult) -> dict[str, Any]:
    score = result.score
    return {
        "total": score.total,
        "grade": score.grade,
        "interpretation": score.interpretation,
        "baseline": score.baseline,
        "delta": score.delta,
        "real_delta": score.real_delta,
        "version_attributed_delta": score.version_attributed_delta,
        "weights_renormalised": score.weights_renormalised,
        "dimensions": [
            {
                "dimension": str(entry.dimension),
                "score": entry.score,
                "grade": entry.grade,
                "weight": entry.weight,
                "effective_weight": entry.effective_weight,
                "points_lost": entry.points_lost,
                "points_available": entry.points_available,
                "finding_count": entry.finding_count,
                "scored": entry.scored,
                "skipped_reason": entry.skipped_reason,
            }
            for entry in score.dimensions
        ],
    }


def _coverage(result: RunResult) -> dict[str, Any]:
    coverage = result.alignment.coverage
    return {
        "conceptual_entities": coverage.conceptual_entities,
        "designed_entities": coverage.designed_entities,
        "built_entities": coverage.built_entities,
        "design_coverage_percent": coverage.design_coverage,
        "delivery_coverage_percent": coverage.delivery_coverage,
        "table_documentation_percent": coverage.documentation_coverage,
        "column_documentation_percent": coverage.column_documentation_coverage,
        "key_test_percent": coverage.test_coverage,
        "off_plan_built": coverage.off_plan_built,
        "off_plan_approved": coverage.off_plan_approved,
        "built_disabled": coverage.built_disabled,
        "designed_not_started": coverage.designed_not_started,
        "unmanaged_production": coverage.unmanaged_production,
        "state_counts": {
            str(state): count for state, count in result.alignment.state_counts().items()
        },
    }


def _inventory(result: RunResult) -> list[dict[str, Any]]:
    """One row per model, enabled and disabled alike. F1."""
    rows: list[dict[str, Any]] = []
    for model in result.project.sorted_models() + [
        result.project.disabled_models[name] for name in sorted(result.project.disabled_models)
    ]:
        rows.append(
            {
                "name": model.name,
                "layer": model.layer,
                "domain": model.domain,
                "resource_type": model.resource_type,
                "materialisation": model.materialisation,
                "enabled": model.enabled,
                "vendored": model.vendored,
                "package": model.package,
                "persistence": str(model.persistence),
                "persistence_signal": str(model.persistence_signal),
                "entity_type_declared": str(model.entity_kind_declared),
                "entity_type_inferred": str(model.entity_kind_inferred),
                "inference_confidence": model.inference_confidence,
                "owner": model.owner,
                "has_description": model.has_description,
                "column_count": len(model.columns),
                "downstream_models": model.downstream_models,
                "exposure_weight": model.exposure_weight,
                "file": model.path,
                "created_by": model.created_by,
                "created_at": model.created_at.isoformat() if model.created_at else None,
                "created_in_pr": model.created_in_pr,
                "last_modified_at": (
                    model.last_modified_at.isoformat() if model.last_modified_at else None
                ),
            }
        )
    return rows


def _alignment(result: RunResult) -> list[dict[str, Any]]:
    """The five-point chain, one row per entity. F17."""
    return [
        {
            "entity": row.key,
            "business_name": row.label,
            "technical_name": row.technical_name,
            "domain": row.domain,
            "conceptual": str(row.conceptual),
            "logical": str(row.logical),
            "designed": str(row.designed),
            "in_repo": str(row.repo),
            "in_warehouse": str(row.warehouse),
            "state": str(row.state),
            "state_label": ALIGNMENT_STATE_LABELS[row.state],
            "state_meaning": ALIGNMENT_STATE_MEANINGS[row.state],
            "grain": row.grain,
            "owner": row.owner,
            "claimed_status": row.claimed_status,
            "claim_matches_reality": row.claim_matches_reality,
            "match_method": row.match_method,
            "match_confidence": row.match_confidence,
            "approved_off_plan": row.approved_off_plan,
            "approval_reason": row.approval_reason,
            "design_file": row.design_file,
            "notes": row.notes,
        }
        for row in result.alignment.rows
    ]


def _findings(result: RunResult) -> list[dict[str, Any]]:
    return [
        {
            "rule": finding.rule,
            "dimension": str(finding.dimension),
            "severity": str(finding.severity),
            "object": finding.subject,
            "object_kind": finding.subject_kind,
            "summary": finding.summary,
            "consequence_plain": finding.consequence,
            "points": finding.points,
            "effective_points": finding.effective_points,
            "file": finding.file,
            "line": finding.line,
            "confidence": finding.confidence,
            "scored": finding.scored,
            "suppressed": finding.suppressed,
            "suppression_reason": finding.suppression_reason,
            "suppression_expires": (
                finding.suppression_expires.isoformat() if finding.suppression_expires else None
            ),
            "owner": finding.owner,
            "team": finding.team,
            "first_seen": finding.first_seen.isoformat() if finding.first_seen else None,
            "age_days": finding.age_days(result.as_of),
            "evidence": finding.evidence,
        }
        for finding in result.findings
    ]


def _conventions(result: RunResult) -> dict[str, Any]:
    """The active ruleset, so the score is auditable. F10, FR7d."""
    from hunter.checks.base import REGISTRY

    return {
        "extends": result.config.extends,
        "house_ruleset_version": result.config.house_version,
        "weights": {
            str(dimension): weight
            for dimension, weight in sorted(
                result.config.scoring.weights.items(), key=lambda item: item[0].value
            )
        },
        "exposure_weighting": result.config.scoring.exposure_weighting,
        "fail_under": result.config.scoring.fail_under,
        "layers": [
            {
                "name": layer.name,
                "prefix": layer.prefix,
                "pipeline_stage": layer.pipeline_stage,
                "persistence": str(layer.persistence),
                "may_reference": layer.may_reference,
                "in_alignment": layer.in_alignment,
                "discovered": layer.discovered,
            }
            for layer in result.config.layers
        ],
        "entities": [
            {"kind": str(spec.kind), "suffix": spec.suffix} for spec in result.config.entities
        ],
        "divergences": [
            {
                "path": item.path,
                "kind": item.kind,
                "level": str(item.level),
                "house_value": item.house_value,
                "project_value": item.project_value,
                "reason": item.reason,
            }
            for item in sorted(result.resolved.divergences, key=lambda item: item.path)
        ],
        "rules": [
            {
                "id": spec.id,
                "dimension": str(spec.dimension),
                "severity": str(result.config.rule_setting(spec.id).severity or spec.severity),
                "points": spec.points,
                "enabled": result.config.is_rule_enabled(spec.id),
                "requires": list(spec.requires),
                "plain_heading": spec.plain_heading,
                "ran": spec.id in result.examined,
            }
            for spec in REGISTRY.all()
        ],
        "silences": [
            {
                "rule": ignore.rule,
                "models": ignore.models,
                "reason": ignore.reason,
                "expires": ignore.expires.isoformat(),
                "expired": ignore.is_expired(result.as_of),
            }
            for ignore in sorted(
                result.register.ignores, key=lambda item: (item.rule, item.expires)
            )
        ],
    }


def write_report(path: Path, result: RunResult, *, generated_at: dt.datetime | None = None) -> Path:
    """Write ``report.json``, sorted and newline-terminated."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_report(result, generated_at=generated_at)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return path
