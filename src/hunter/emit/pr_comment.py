"""The pull request comment.

F11. Short, specific to the change, and quiet by default. The risk register
names comment noise on first install as the thing that gets a tool muted within
days, so the comment shows what this change did and leaves standing debt on the
site.

On "only violations the change introduced", FR11.2: a true before-and-after
needs two manifests, and one run has one. Two paths are offered, and the comment
says which it used:

* Given a previous ``report.json``, Hunter diffs the two finding sets and
  reports exactly what appeared.
* Without one, it reports findings on the files the change touched, which is a
  superset. That is stated in the comment rather than presented as the same
  thing.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from hunter.emit import mermaid
from hunter.emit.plain import severity_label
from hunter.enums import PrMode, Severity
from hunter.model.findings import Finding
from hunter.run import RunResult

#: Lets the Action find its own comment and edit it rather than adding another.
#: FR11.5.
MARKER = "<!-- rittman-hunter-comment -->"


def finding_key(finding: Finding) -> tuple[str, str, str]:
    """What makes two findings the same finding across runs."""
    return (finding.rule, finding.subject, finding.file or "")


def previous_keys(report_path: Path) -> set[tuple[str, str, str]] | None:
    """Finding keys from a previous ``report.json``, for a true diff."""
    if not report_path.exists():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    findings = payload.get("findings")
    if not isinstance(findings, list):
        return None
    return {
        (str(item.get("rule")), str(item.get("object")), str(item.get("file") or ""))
        for item in findings
        if isinstance(item, dict)
    }


def findings_for_changed_files(result: RunResult, changed_files: Iterable[str]) -> list[Finding]:
    """Findings on the models this change touched."""
    changed = {path.strip() for path in changed_files if path.strip()}
    if not changed:
        return []

    touched: set[str] = set()
    for model in result.project.models.values():
        for path in changed:
            if path.endswith(model.path) or model.path.endswith(path):
                touched.add(model.name)
    for view in result.project.lookml_views.values():
        if view.file and any(view.file.endswith(path) for path in changed):
            touched.add(view.name)

    return [
        finding
        for finding in result.findings
        if finding.subject in touched and finding.counts_towards_score
    ]


def build_comment(
    result: RunResult,
    *,
    changed_files: Iterable[str] | None = None,
    previous_report: Path | None = None,
    pull_request: str | None = None,
) -> str:
    """The comment body, as markdown."""
    config = result.config
    spec = config.pull_request
    score = result.score

    before = previous_keys(previous_report) if previous_report else None
    if before is not None:
        new_findings = [
            finding
            for finding in result.findings
            if finding.counts_towards_score and finding_key(finding) not in before
        ]
        cleared = len(before) - len({finding_key(item) for item in result.findings} & before)
        basis = "Comparing against the previous run's findings."
    else:
        new_findings = findings_for_changed_files(result, changed_files or [])
        cleared = 0
        basis = (
            "No previous report was available, so this lists findings on the files "
            "this change touched. Some may predate the change."
        )

    lines = [MARKER, "", "## Rittman Hunter", ""]

    if score.baseline is not None and score.delta is not None:
        arrow = "up" if score.delta > 0 else ("down" if score.delta < 0 else "level")
        lines.append(
            f"**Score {score.total:g} / 100** ({arrow} {abs(score.delta):g} from "
            f"{score.baseline:g}). {score.interpretation}."
        )
    else:
        lines.append(f"**Score {score.total:g} / 100.** {score.interpretation}.")
    lines.append("")

    if spec.new_violations_only:
        if new_findings:
            shown = sorted(new_findings, key=lambda item: item.sort_key())[
                : spec.max_findings_shown
            ]
            lines += [
                f"### {len(new_findings)} finding"
                + ("s" if len(new_findings) != 1 else "")
                + " on what this change touches",
                "",
            ]
            for finding in shown:
                where = f" — `{finding.location}`" if finding.file else ""
                lines += [
                    f"- **{severity_label(finding.severity)}**: {finding.summary}{where}",
                    f"  {finding.consequence}",
                ]
            if len(new_findings) > len(shown):
                lines.append(f"- and {len(new_findings) - len(shown)} more.")
            lines.append("")
        else:
            lines += ["No new findings on the files this change touches.", ""]

    if cleared > 0:
        lines += [f"{cleared} findings that were open before are now cleared.", ""]

    if spec.include_blast_radius and changed_files:
        radius = _blast_radius_summary(result, changed_files)
        if radius:
            lines += ["### What this change reaches", "", radius, ""]

    if spec.include_subgraph and changed_files:
        subgraph = _subgraph(result, changed_files)
        if subgraph:
            summary = "Show the affected tables"
            body = "```mermaid\n" + subgraph.rstrip() + "\n```"
            if spec.collapse_subgraph:
                lines += [f"<details>\n<summary>{summary}</summary>\n\n{body}\n</details>", ""]
            else:
                lines += [body, ""]

    failed, reason = _gate(result)
    if failed:
        lines += ["### This check failed", "", reason or "", ""]
    elif spec.mode is PrMode.ADVISORY:
        lines += [
            "_Advisory only: this check never fails a build._",
            "",
        ]

    lines += [
        f"<sub>{basis} "
        f"Hunter {result.meta.get('hunter_version')}, ruleset "
        f"{result.meta.get('house_ruleset_version')}. "
        f"[Full report]({_site_hint(result)}).</sub>",
        f"<sub>{config.branding.attribution}.</sub>",
    ]
    if pull_request:
        lines.append(f"<sub>Pull request #{pull_request}.</sub>")

    return "\n".join(lines) + "\n"


def _gate(result: RunResult) -> tuple[bool, str | None]:
    from hunter.score.engine import fails_build

    return fails_build(result.score, result.config)


def _site_hint(result: RunResult) -> str:
    return "../../actions" if not result.config.branding.client_name else "#"


def _changed_models(result: RunResult, changed_files: Iterable[str]) -> list[str]:
    changed = {path.strip() for path in changed_files if path.strip()}
    names: list[str] = []
    for model in result.project.sorted_models():
        if any(path.endswith(model.path) or model.path.endswith(path) for path in changed):
            names.append(model.name)
    return names


def _blast_radius_summary(result: RunResult, changed_files: Iterable[str]) -> str:
    """What the changed models feed, in one table. FR11.3."""
    names = _changed_models(result, changed_files)
    if not names:
        return ""

    rows: list[str] = [
        "| Table changed | Other tables downstream | Report fields | Report views |",
        "|---|---|---|---|",
    ]
    for name in names[:10]:
        model = result.project.models.get(name)
        if model is None:
            continue
        views = result.project.views_for_model(name)
        fields = sum(len(view.fields) for view in views)
        rows.append(f"| `{name}` | {len(model.downstream_models)} | {fields} | {len(views)} |")
    if len(names) > 10:
        rows.append(f"| and {len(names) - 10} more | | | |")
    return "\n".join(rows)


def _subgraph(result: RunResult, changed_files: Iterable[str]) -> str:
    """A diagram of the affected nodes only. FR11.4."""
    names = _changed_models(result, changed_files)
    if not names:
        return ""
    return mermaid.blast_radius(names[0], result.project, result.graph, max_nodes=15)


def severity_counts(findings: Iterable[Finding]) -> dict[Severity, int]:
    counts = dict.fromkeys(Severity, 0)
    for finding in findings:
        counts[finding.severity] += 1
    return counts
