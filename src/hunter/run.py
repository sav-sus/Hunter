"""The pipeline: config, ingest, normalise, check, score, emit.

Section 11.4. Steps 1 to 5 are pure functions over the ingested data, so the
only work here that touches the outside world is the ingest step. That is what
makes FR7.7 hold: the same inputs give the same output, every time.

The CLI is a thin wrapper over this, and so is the GitHub Action. Keeping the
logic here rather than in ``cli.py`` is what makes local and CI results
identical by construction, per section 5.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from hunter.checks import ALL_CHECKS, collect
from hunter.checks.base import (
    REQ_CONCEPTUAL,
    REQ_DBML,
    REQ_DROUGHTY,
    REQ_GIT,
    REQ_LOOKML,
    REQ_MANIFEST,
    REQ_WAREHOUSE,
    CheckContext,
    Denominator,
)
from hunter.config import ResolvedConfig, load_register, resolve
from hunter.config.register import Register
from hunter.config.schema import HunterConfig
from hunter.ingest import dbml as dbml_ingest
from hunter.ingest import diagrams as diagram_ingest
from hunter.ingest import lookml as lookml_ingest
from hunter.ingest.droughty import load_droughty
from hunter.ingest.git import load_git
from hunter.ingest.manifest import ManifestError, load_catalog, load_manifest
from hunter.model.align import Alignment, build_alignment
from hunter.model.build import build_project
from hunter.model.entities import Project
from hunter.model.findings import Finding, ScoreResult
from hunter.model.graph import Graph
from hunter.score.baseline import Baseline, load_baseline
from hunter.score.engine import compute_score, report_meta


@dataclass
class RunResult:
    """Everything one run produced. Every emitter renders from this."""

    config: HunterConfig
    resolved: ResolvedConfig
    register: Register
    project: Project
    graph: Graph
    alignment: Alignment
    findings: list[Finding]
    score: ScoreResult
    examined: dict[str, Denominator]
    available: frozenset[str]
    meta: dict[str, str | None] = field(default_factory=dict)
    baseline: Baseline | None = None
    sources_read: list[str] = field(default_factory=list)
    as_of: dt.date = field(default_factory=dt.date.today)

    @property
    def open_findings(self) -> list[Finding]:
        """Findings that count. Suppressed ones stay in ``findings``."""
        return [item for item in self.findings if item.counts_towards_score]

    @property
    def suppressed_findings(self) -> list[Finding]:
        return [item for item in self.findings if item.suppressed]

    @property
    def suggestions(self) -> list[Finding]:
        """Low-confidence findings, reported but not scored. FR3.6."""
        return [item for item in self.findings if not item.scored and not item.suppressed]


def run(
    root: Path,
    *,
    project_file: Path | None = None,
    manifest_path: Path | None = None,
    house: str | None = None,
    as_of: dt.date | None = None,
    read_git: bool = True,
) -> RunResult:
    """Score a repository.

    Args:
        root: the repository root.
        project_file: the client's ``hunter.yml``. Omitted means score against
            the house standard alone, which is how a first assessment runs.
        manifest_path: overrides the path in the ruleset. Useful when the
            manifest comes from wherever the client's own dbt job puts it.
        as_of: the date to treat as today, for expiry and staleness. Pinned in
            tests so golden files stay stable.
        read_git: set False to skip history, which halves the run on a very
            large repository at the cost of attribution.

    Raises:
        ManifestError: no manifest could be found. Every other source is
            optional and its absence is reported as a skipped dimension.
    """
    today = as_of or dt.date.today()

    if project_file is None:
        for candidate in (root / ".hunter" / "hunter.yml", root / "hunter.yml"):
            if candidate.exists():
                project_file = candidate
                break

    resolved = resolve(project_file, house=house)
    config = resolved.config
    paths = config.paths

    project_dir = root / paths.dbt_project_dir
    register = load_register(root / paths.register_file)

    manifest_file = manifest_path or (project_dir / paths.manifest)
    manifest = load_manifest(manifest_file)
    load_catalog(manifest_file.parent / "catalog.json", manifest)
    sources = [str(manifest_file)]

    dbml_files = dbml_ingest.resolve_paths(project_dir, paths.dbml)
    dbml = dbml_ingest.load_dbml(dbml_files) if dbml_files else None
    sources.extend(str(path) for path in dbml_files)

    conceptual = None
    if paths.conceptual_diagram:
        candidate = project_dir / paths.conceptual_diagram
        if candidate.exists():
            conceptual = diagram_ingest.parse_conceptual(candidate)
            sources.append(str(candidate))

    logical = None
    if paths.logical_diagram:
        candidate = project_dir / paths.logical_diagram
        if candidate.exists():
            logical = diagram_ingest.parse_logical(candidate)
            sources.append(str(candidate))

    lookml = None
    if paths.lookml:
        lookml_files = lookml_ingest.resolve_paths(project_dir, paths.lookml)
        if lookml_files:
            lookml = lookml_ingest.load_lookml(lookml_files)
            sources.extend(str(path) for path in lookml_files[:20])

    droughty = None
    if config.integrations.droughty.enabled:
        droughty = load_droughty(
            project_dir,
            repo_root=root,
            project_file=paths.droughty_project,
            schema_file=paths.droughty_schema,
            field_descriptions=paths.field_descriptions,
            dbml_patterns=paths.droughty_dbml or None,
        )
        if not droughty.found_any:
            droughty = None
        elif droughty.artifacts.schema_file:
            sources.append(droughty.artifacts.schema_file)

    git = load_git(root) if read_git else None

    project, graph = build_project(
        config=config,
        register=register,
        manifest=manifest,
        dbml=dbml,
        conceptual=conceptual,
        logical=logical,
        lookml=lookml,
        droughty=droughty,
        git=git,
        as_of=today,
    )
    alignment = build_alignment(project, config, register, logical=logical)

    available = availability(project)
    context = CheckContext(
        project=project,
        graph=graph,
        config=config,
        register=register,
        alignment=alignment,
        as_of=today,
        available=available,
    )
    findings = collect(ALL_CHECKS, context)

    baseline = load_baseline(root / config.paths.baseline)
    score = compute_score(
        findings,
        context.examined,
        config,
        available=available,
        baseline=baseline.total if baseline else None,
        baseline_score_model_version=baseline.score_model_version if baseline else None,
        baseline_house_version=baseline.house_ruleset_version if baseline else None,
    )

    return RunResult(
        config=config,
        resolved=resolved,
        register=register,
        project=project,
        graph=graph,
        alignment=alignment,
        findings=findings,
        score=score,
        examined=dict(context.examined),
        available=available,
        meta=report_meta(
            config,
            repo=root.name,
            commit=git.head_sha if git and git.available else None,
        ),
        baseline=baseline,
        sources_read=sorted(set(sources)),
        as_of=today,
    )


def availability(project: Project) -> frozenset[str]:
    """Which data sources this run had.

    Drives which rules run and which dimensions are declared skipped, so a
    reader always knows what the score was computed from.
    """
    present: set[str] = set()
    if project.has_manifest:
        present.add(REQ_MANIFEST)
    if project.has_dbml:
        present.add(REQ_DBML)
    if project.has_conceptual:
        present.add(REQ_CONCEPTUAL)
    if project.has_lookml:
        present.add(REQ_LOOKML)
    if project.has_droughty:
        present.add(REQ_DROUGHTY)
    if project.has_warehouse:
        present.add(REQ_WAREHOUSE)
    if project.has_git:
        present.add(REQ_GIT)
    return frozenset(present)


__all__ = ["ManifestError", "RunResult", "availability", "run"]
