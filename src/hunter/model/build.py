"""Assemble the normalised project from the ingest results.

Pipeline step 3. This is where the separate readers become one cross-referenced
model: layers assigned, the graph built, consumers counted, persistence
classified and authorship attached.

Steps 1 to 5 of the pipeline are pure functions over the ingested data, per
section 11.4, so this takes data in and returns data out. It reads no files and
runs no commands.
"""

from __future__ import annotations

import datetime as dt

from hunter.config.register import Register
from hunter.config.schema import HunterConfig
from hunter.enums import EntityKind, Persistence
from hunter.ingest.dbml import DbmlData
from hunter.ingest.diagrams import ConceptualData, LogicalData
from hunter.ingest.droughty import DroughtyData
from hunter.ingest.git import GitData
from hunter.ingest.lookml import LookmlData
from hunter.ingest.manifest import ManifestData
from hunter.model.entities import Model, ParseIssue, Project, classify_persistence, domain_of
from hunter.model.graph import Consumers, Graph, exposure_weight
from hunter.model.layers import discover_layers, with_layers


def _assign_layer_and_domain(model: Model, config: HunterConfig) -> None:
    """Place a model in a layer, and read its domain from its name.

    Path first, since that is what the ruleset declares. Prefix second, so a
    model in an undeclared directory still lands in the right layer if it is
    named correctly.
    """
    layer = config.layer_for_path(model.path)
    if layer is None:
        for candidate in config.layers:
            if candidate.prefix and model.name.startswith(candidate.prefix):
                layer = candidate
                break
    model.layer = layer.name if layer else None
    model.domain = domain_of(model.name, layer.prefix if layer else None)


def _declared_entity_kind(model: Model, config: HunterConfig) -> EntityKind:
    spec = config.entity_for_name(model.name)
    return spec.kind if spec else EntityKind.UNKNOWN


def _count_consumers(
    model_name: str,
    lookml: LookmlData | None,
    exposures_by_model: dict[str, int],
) -> Consumers:
    """What reads this model, beyond other models. Feeds exposure weighting."""
    if lookml is None:
        return Consumers(exposures=exposures_by_model.get(model_name, 0))

    views = [view for view in lookml.views.values() if view.model_name == model_name]
    view_names = {view.name for view in views}
    field_count = sum(len(view.fields) for view in views)
    explore_count = sum(
        1
        for explore in lookml.explores.values()
        if explore.view_name in view_names or view_names.intersection(explore.joined_views())
    )
    return Consumers(
        lookml_fields=field_count,
        lookml_views=len(views),
        explores=explore_count,
        exposures=exposures_by_model.get(model_name, 0),
    )


def _git_index(git: GitData | None) -> dict[str, str]:
    """Index git paths by their trailing segments.

    Needed because manifest paths are relative to the dbt project directory
    (``models/x.sql``) while git paths are relative to the repository root
    (``analytics_warehouse/models/x.sql``). Rather than make every client
    declare the offset, match on the suffix.
    """
    if git is None:
        return {}
    return {path: path for path in git.histories}


def _find_history(model_path: str, git: GitData | None, index: dict[str, str]) -> str | None:
    if git is None or not model_path:
        return None
    if model_path in index:
        return model_path
    needle = "/" + model_path
    matches = [path for path in index if path.endswith(needle)]
    if len(matches) == 1:
        return matches[0]
    # More than one match means the same relative path exists under two
    # directories. Attributing to either would be a guess, so attribute to
    # neither and let the "no identifiable owner" finding stand. FR6.5.
    return None


def _attach_git(project: Project, git: GitData | None) -> None:
    index = _git_index(git)
    for model in project.models.values():
        key = _find_history(model.path, git, index)
        if key is None:
            continue
        history = git.histories[key] if git else None
        if history is None:
            continue
        model.created_by = history.created_by
        model.created_at = history.created_at
        model.created_in_pr = history.created_in_pr
        model.last_modified_by = history.last_modified_by
        model.last_modified_at = history.last_modified_at

        if model.schema_file:
            docs_key = _find_history(model.schema_file, git, index)
            if docs_key is not None:
                docs = git.histories[docs_key] if git else None
                if docs is not None:
                    model.docs_modified_at = docs.last_modified_at


def _apply_register(project: Project, register: Register) -> None:
    """Fold in what a person has declared. Metadata only; no rule silencing.

    Suppression happens at scoring time so a silenced finding still appears on
    the site with its reason, rather than vanishing here.
    """
    for name, entry in register.models.items():
        model = project.any_model(name)
        if model is None:
            continue
        if entry.owner:
            model.owner = entry.owner
        if entry.entity_type is not None:
            model.entity_kind_declared = entry.entity_type


def build_project(
    *,
    config: HunterConfig,
    register: Register,
    manifest: ManifestData | None = None,
    dbml: DbmlData | None = None,
    conceptual: ConceptualData | None = None,
    logical: LogicalData | None = None,
    lookml: LookmlData | None = None,
    droughty: DroughtyData | None = None,
    git: GitData | None = None,
    as_of: dt.date | None = None,
) -> tuple[Project, Graph]:
    """Cross-reference every ingested source into one project and its graph."""
    project = Project()

    if manifest is not None:
        project.has_manifest = True
        project.models = dict(manifest.models)
        project.disabled_models = dict(manifest.disabled_models)
        project.sources = dict(manifest.sources)
        project.exposures = list(manifest.exposures)
        project.tests = list(manifest.tests)
        project.parse_issues.extend(manifest.issues)

    if dbml is not None:
        project.designed = dict(dbml.entities)
        project.designed_refs = list(dbml.refs)
        project.has_dbml = bool(dbml.entities)
        project.parse_issues.extend(dbml.issues)

    if conceptual is not None:
        project.conceptual = dict(conceptual.entities)
        project.has_conceptual = bool(conceptual.entities)
        project.parse_issues.extend(conceptual.issues)

    if logical is not None:
        project.parse_issues.extend(logical.issues)

    if lookml is not None:
        project.lookml_views = dict(lookml.views)
        project.explores = dict(lookml.explores)
        project.has_lookml = bool(lookml.views)
        project.parse_issues.extend(lookml.issues)

    if droughty is not None:
        project.droughty = droughty.artifacts
        project.has_droughty = droughty.found_any
        project.parse_issues.extend(droughty.issues)

    if git is not None:
        project.has_git = git.available
        project.parse_issues.extend(git.issues)

    # A directory of models the ruleset does not name becomes a layer of its
    # own, so a new part of the warehouse appears on the report without anyone
    # editing hunter.yml. The caller picks the extended config up from the
    # project, so every check and page sees the same layers.
    every_model = [*project.models.values(), *project.disabled_models.values()]
    discovered = discover_layers(config, every_model)
    if discovered:
        config = with_layers(config, discovered)
        project.discovered_layers = [layer.name for layer in discovered]
        project.parse_issues.append(
            ParseIssue(
                source="hunter.yml",
                subject=", ".join(layer.name for layer in discovered),
                message=(
                    "Found in the models directory and not declared as a layer. Hunter "
                    "grouped these models by directory and held them to no layer rules. "
                    "Declare the layer in hunter.yml to say what it should look like."
                ),
            )
        )

    # Layers, domains and declared entity kinds, for enabled and disabled alike:
    # a disabled model is still part of the repository.
    for collection in (project.models, project.disabled_models):
        for model in collection.values():
            _assign_layer_and_domain(model, config)
            model.entity_kind_declared = _declared_entity_kind(model, config)

    graph = Graph.build(project.models)
    known = set(project.models)
    for name, model in project.models.items():
        model.downstream_models = sorted(graph.descendants(name) & known)

    exposures_by_model: dict[str, int] = {}
    for exposure in project.exposures:
        for name in exposure.depends_on_models:
            exposures_by_model[name] = exposures_by_model.get(name, 0) + 1

    cap = config.scoring.exposure_weight_cap
    for name, model in project.models.items():
        consumers = _count_consumers(name, lookml, exposures_by_model)
        model.exposure_weight = (
            exposure_weight(len(model.downstream_models), consumers, cap=cap)
            if config.scoring.exposure_weighting
            else 1.0
        )
        persistence, signal = classify_persistence(model, config, register)
        model.persistence = persistence
        model.persistence_signal = signal

    for model in project.disabled_models.values():
        model.persistence = Persistence.UNKNOWN
        model.exposure_weight = 1.0

    _attach_git(project, git)
    _apply_register(project, register)

    project.parse_issues.sort(key=lambda issue: (issue.source, issue.subject or "", issue.message))
    return project, graph


def consumers_of(model_name: str, project: Project, lookml: LookmlData | None = None) -> Consumers:
    """Recount consumers for one model, for blast radius. FR5.2, FR11.3."""
    exposures = sum(1 for exposure in project.exposures if model_name in exposure.depends_on_models)
    views = project.views_for_model(model_name)
    view_names = {view.name for view in views}
    explores = sum(
        1
        for explore in project.explores.values()
        if explore.view_name in view_names or view_names.intersection(explore.joined_views())
    )
    return Consumers(
        lookml_fields=sum(len(view.fields) for view in views),
        lookml_views=len(views),
        explores=explores,
        exposures=exposures,
    )
