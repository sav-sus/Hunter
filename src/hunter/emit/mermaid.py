"""Mermaid diagrams: the three model levels, the graph, and blast radius.

Hunter draws these rather than only embedding the authored ones. The reason is
in F17 and in what the pilot repository shows: the authored conceptual diagram
encodes build status as fill colour across 88 hand-maintained style lines, and
21 of its 107 claims are out of date. Hunter knows the real state, so it draws
the truth and shows the authored original beside it.

Size is the other reason. A flowchart of 280 models is unreadable, so the graph
is drawn collapsed by layer and domain by default, with a per-domain view
underneath. A diagram nobody can read is not a diagram.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from hunter.enums import AlignmentState, Presence
from hunter.model.align import Alignment, AlignmentRow
from hunter.model.entities import Project
from hunter.model.graph import Graph

#: Mermaid node ids must be simple identifiers.
_UNSAFE = re.compile(r"[^A-Za-z0-9_]")

#: Colour per alignment state. Chosen for contrast rather than decoration, and
#: legible in both light and dark rendering.
STATE_STYLE: dict[AlignmentState, str] = {
    AlignmentState.DESIGNED_AND_DELIVERED: "fill:#d6ead6,stroke:#4a7a4a",
    AlignmentState.BUILT_NOT_DEPLOYED: "fill:#fdf2cc,stroke:#9a8330",
    AlignmentState.BUILT_DISABLED: "fill:#e8e8e8,stroke:#777,stroke-dasharray:4 3",
    AlignmentState.DESIGNED_NOT_STARTED: "fill:#f2f2f2,stroke:#999,stroke-dasharray:4 3",
    AlignmentState.CONCEPTUAL_ONLY: "fill:#fafafa,stroke:#bbb,stroke-dasharray:2 3",
    AlignmentState.LOGICAL_ONLY: "fill:#fafafa,stroke:#bbb,stroke-dasharray:2 3",
    AlignmentState.BUILT_OFF_PLAN: "fill:#fbe3de,stroke:#c0392b",
    AlignmentState.APPROVED_OFF_PLAN: "fill:#e6eefb,stroke:#3b6fb6",
    AlignmentState.OFF_PLAN_NOT_DEPLOYED: "fill:#fbe3de,stroke:#c0392b,stroke-dasharray:4 3",
    AlignmentState.LIVE_WITHOUT_CODE: "fill:#fbe3de,stroke:#c0392b",
    AlignmentState.UNTRACKED_TABLE: "fill:#fbe3de,stroke:#c0392b",
    AlignmentState.NOT_PRESENT: "fill:#ffffff,stroke:#ccc",
}

#: DBML relationship words to Mermaid ER cardinality.
CARDINALITY: dict[str, str] = {
    "many-to-one": "}o--||",
    "one-to-many": "||--o{",
    "one-to-one": "||--||",
    "many-to-many": "}o--o{",
}
DEFAULT_CARDINALITY = "}o--||"

#: Column role, for grouping attributes on the logical diagram.
ROLE_ORDER = ("key", "link", "natural key", "date", "measure", "flag", "attribute")


def safe_id(name: str, prefix: str = "n") -> str:
    """A Mermaid-safe node id, stable for the same input."""
    cleaned = _UNSAFE.sub("_", name).strip("_")
    if not cleaned:
        cleaned = "unnamed"
    if not cleaned[0].isalpha():
        cleaned = f"{prefix}_{cleaned}"
    return cleaned


def escape(text: str) -> str:
    """Text safe inside a Mermaid quoted label."""
    return text.replace('"', "'").replace("\n", " ").strip()


def _legend(states: set[AlignmentState]) -> list[str]:
    """A legend naming only the states this diagram actually uses."""
    from hunter.enums import ALIGNMENT_STATE_LABELS

    if not states:
        return []
    lines = ['  subgraph legend["What the colours mean"]', "    direction LR"]
    for state in sorted(states, key=lambda item: item.value):
        node = f"legend_{safe_id(state.value)}"
        lines.append(f'    {node}["{escape(ALIGNMENT_STATE_LABELS[state])}"]')
    lines.append("  end")
    for state in sorted(states, key=lambda item: item.value):
        node = f"legend_{safe_id(state.value)}"
        lines.append(f"  style {node} {STATE_STYLE[state]}")
    return lines


def conceptual_diagram(
    alignment: Alignment,
    *,
    domain: str | None = None,
    include_legend: bool = True,
) -> str:
    """Business entities, grouped by domain, coloured by their real state.

    This is the non-technical entry point, per FR14.6, so it carries business
    names and no columns at all.
    """
    rows = [
        row
        for row in alignment.rows
        if row.conceptual is Presence.PRESENT and (domain is None or row.domain == domain)
    ]
    if not rows:
        return 'flowchart TB\n  empty["No business entities were found"]\n'

    lines = ["flowchart TB"]
    used: set[AlignmentState] = set()
    grouped: dict[str, list[AlignmentRow]] = {}
    for row in rows:
        grouped.setdefault(row.domain or "ungrouped", []).append(row)

    for group, members in sorted(grouped.items()):
        lines.append(f'  subgraph {safe_id(group, "d")}["{escape(group.replace("_", " "))}"]')
        for row in sorted(members, key=lambda item: item.label):
            node = safe_id(row.key, "e")
            lines.append(f'    {node}["{escape(row.label)}"]')
            used.add(row.state)
        lines.append("  end")

    for row in rows:
        lines.append(f"  style {safe_id(row.key, 'e')} {STATE_STYLE[row.state]}")

    if include_legend:
        lines.extend(_legend(used))
    return "\n".join(lines) + "\n"


def _designed_role(column) -> str:
    name = column.name.lower()
    if column.is_primary_key:
        return "key"
    if name.endswith("_fk"):
        return "link"
    if name.endswith("_natural_key"):
        return "natural key"
    if name.endswith(("_dt", "_ts")):
        return "date"
    if name.startswith(("is_", "has_")) or "_is_" in name or name.endswith("_flag"):
        return "flag"
    from hunter.checks.entity import looks_like_measure

    if looks_like_measure(name):
        return "measure"
    return "attribute"


#: Lines of a DBML table note that state the grain, which is shown on its own.
GRAIN_PREFIXES = ("table grain:", "grain:")

#: How much of a table's description fits in an ER diagram before it is cut.
ABOUT_LIMIT = 56


def describe(note: str | None, limit: int = ABOUT_LIMIT) -> str:
    """The table's description from its DBML note, without the grain line.

    Notes follow the house shape: a grain line, a source line, then anything
    else. The grain is drawn separately, so it is dropped here, and the rest is
    joined and cut to fit a diagram cell.
    """
    if not note:
        return ""
    kept = [
        line.strip()
        for line in note.splitlines()
        if line.strip() and not line.strip().lower().startswith(GRAIN_PREFIXES)
    ]
    text = " ".join(kept)
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def logical_diagram(
    project: Project,
    alignment: Alignment,
    *,
    domain: str | None = None,
    max_attributes: int = 12,
) -> str:
    """Designed entities with their attributes grouped by role.

    Derived from the authored design, deliberately without warehouse types or
    materialisation: those belong on the physical view. Attributes are capped so
    a 90-column fact does not make the diagram unreadable, and the cap is
    stated on the entity rather than hidden.
    """
    rows = {
        row.designed_name: row
        for row in alignment.rows
        if row.designed_name and (domain is None or row.domain == domain)
    }
    entities = [project.designed[name] for name in sorted(rows) if name in project.designed]
    if not entities:
        return "erDiagram\n"

    lines = ["erDiagram"]
    names = {entity.name for entity in entities}

    for ref in project.designed_refs:
        if ref.from_table not in names or ref.to_table not in names:
            continue
        link = CARDINALITY.get(ref.cardinality or "", DEFAULT_CARDINALITY)
        label = escape(", ".join(ref.from_columns) or "relates to")
        lines.append(
            f'  {safe_id(ref.from_table, "e")} {link} {safe_id(ref.to_table, "e")} : "{label}"'
        )

    for entity in entities:
        row = rows[entity.name]
        lines.append(f"  {safe_id(entity.name, 'e')} {{")
        # What one row means and what the table is for come first, where a
        # reader looks before the columns. The comment slot of an attribute is
        # the only place an ER diagram allows free text.
        grain = row.grain or entity.grain_note
        if grain:
            lines.append(f'    note grain "{escape(grain)}"')
        about = describe(entity.note)
        if about:
            lines.append(f'    note about "{escape(about)}"')
        by_role: dict[str, list[str]] = {}
        for column in entity.columns:
            by_role.setdefault(_designed_role(column), []).append(column.name)

        shown = 0
        for role in ROLE_ORDER:
            for name in sorted(by_role.get(role, [])):
                if shown >= max_attributes:
                    break
                marker = "PK" if role == "key" else ("FK" if role == "link" else "")
                lines.append(
                    f"    {escape(role.replace(' ', '_'))} {safe_id(name)} {marker}".rstrip()
                )
                shown += 1
        total = len(entity.columns)
        if total > shown:
            lines.append(f"    more and_{total - shown}_further_attributes")
        lines.append("  }")

    return "\n".join(lines) + "\n"


def physical_diagram(
    project: Project,
    alignment: Alignment,
    *,
    domain: str | None = None,
    max_attributes: int = 12,
) -> str:
    """Deployed tables, with the types and materialisation they were built with."""
    rows = [
        row for row in alignment.rows if row.model_name and (domain is None or row.domain == domain)
    ]
    models = [project.models[row.model_name] for row in rows if row.model_name in project.models]
    if not models:
        return "erDiagram\n"

    lines = ["erDiagram"]
    names = {model.name for model in models}

    for model in models:
        for parent in model.depends_on_models:
            if parent in names:
                lines.append(
                    f'  {safe_id(parent, "m")} ||--o{{ {safe_id(model.name, "m")} : "feeds"'
                )

    for model in sorted(models, key=lambda item: item.name):
        lines.append(f"  {safe_id(model.name, 'm')} {{")
        lines.append(f"    built_as {safe_id(model.materialisation)}")
        for column in sorted(model.columns, key=lambda item: item.name)[:max_attributes]:
            data_type = safe_id((column.data_type or "unknown").lower())
            lines.append(f"    {data_type} {safe_id(column.name)}")
        if len(model.columns) > max_attributes:
            remaining = len(model.columns) - max_attributes
            lines.append(f"    more and_{remaining}_further_columns")
        lines.append("  }")

    return "\n".join(lines) + "\n"


def collapsed_graph(project: Project, graph: Graph) -> str:
    """The graph one node per layer and domain, with model counts.

    The entry point to lineage. 280 models in one flowchart is unreadable, so
    the full detail is per-domain and this is what a reader sees first.
    """
    groups: dict[tuple[str, str], int] = {}
    for model in project.models.values():
        if model.vendored:
            continue
        key = (model.layer or "unplaced", model.domain or "ungrouped")
        groups[key] = groups.get(key, 0) + 1

    if not groups:
        return 'flowchart LR\n  empty["No models were found"]\n'

    edges: dict[tuple[tuple[str, str], tuple[str, str]], int] = {}
    for model in project.models.values():
        if model.vendored:
            continue
        target = (model.layer or "unplaced", model.domain or "ungrouped")
        for parent_name in model.depends_on_models:
            parent = project.any_model(parent_name)
            if parent is None or parent.vendored:
                continue
            source = (parent.layer or "unplaced", parent.domain or "ungrouped")
            if source == target:
                continue
            edges[(source, target)] = edges.get((source, target), 0) + 1

    def node_id(key: tuple[str, str]) -> str:
        return safe_id(f"{key[0]}__{key[1]}", "g")

    by_layer: dict[str, list[tuple[str, str]]] = {}
    for key in groups:
        by_layer.setdefault(key[0], []).append(key)

    lines = ["flowchart LR"]
    stages = {layer.name: layer.pipeline_stage for layer in _layers(project)}
    for layer in sorted(by_layer, key=lambda name: (stages.get(name, 99), name)):
        lines.append(f'  subgraph {safe_id(layer, "l")}["{escape(layer.replace("_", " "))}"]')
        for key in sorted(by_layer[layer]):
            count = groups[key]
            label = f"{key[1].replace('_', ' ')} ({count})"
            lines.append(f'    {node_id(key)}["{escape(label)}"]')
        lines.append("  end")

    for (source, target), count in sorted(edges.items()):
        label = f"|{count}|" if count > 1 else ""
        lines.append(f"  {node_id(source)} -->{label} {node_id(target)}")

    return "\n".join(lines) + "\n"


def domain_graph(project: Project, graph: Graph, domain: str) -> str:
    """Every model in one domain, plus its immediate neighbours outside it."""
    inside = sorted(
        model.name
        for model in project.models.values()
        if model.domain == domain and not model.vendored
    )
    if not inside:
        return 'flowchart LR\n  empty["No models in this domain"]\n'

    members = set(inside)
    neighbours: set[str] = set()
    for name in inside:
        neighbours.update(graph.direct_parents(name))
        neighbours.update(graph.direct_children(name))
    neighbours -= members

    lines = ["flowchart LR"]
    lines.append(f'  subgraph focus["{escape(domain.replace("_", " "))}"]')
    for name in inside:
        model = project.models[name]
        shape = f'["{escape(name)}"]'
        if model.is_temporary:
            shape = f'("{escape(name)}")'
        lines.append(f"    {safe_id(name, 'm')}{shape}")
    lines.append("  end")

    for name in sorted(neighbours):
        lines.append(f'  {safe_id(name, "m")}["{escape(name)}"]')
        lines.append(f"  style {safe_id(name, 'm')} fill:#f7f7f7,stroke:#bbb")

    seen: set[tuple[str, str]] = set()
    for name in inside:
        for parent in graph.direct_parents(name):
            if parent in members or parent in neighbours:
                edge = (parent, name)
                if edge not in seen:
                    seen.add(edge)
                    lines.append(f"  {safe_id(parent, 'm')} --> {safe_id(name, 'm')}")
        for child in graph.direct_children(name):
            if child in members or child in neighbours:
                edge = (name, child)
                if edge not in seen:
                    seen.add(edge)
                    lines.append(f"  {safe_id(name, 'm')} --> {safe_id(child, 'm')}")

    return "\n".join(lines) + "\n"


def blast_radius(
    model_name: str,
    project: Project,
    graph: Graph,
    *,
    max_nodes: int = 25,
) -> str:
    """What a change to one model reaches. FR5.2 and FR11.4.

    Capped, because a change to a shared staging model can reach a hundred
    things and a hundred-node diagram in a pull request comment helps nobody.
    """
    downstream = sorted(graph.descendants(model_name))
    views = project.views_for_model(model_name)

    lines = ["flowchart LR"]
    lines.append(f'  {safe_id(model_name, "m")}["{escape(model_name)}"]')
    lines.append(f"  style {safe_id(model_name, 'm')} fill:#fdf2cc,stroke:#9a8330")

    for name in downstream[:max_nodes]:
        lines.append(f'  {safe_id(name, "m")}["{escape(name)}"]')

    # Iterate the sorted list, never the set: set order over strings varies with
    # the hash seed, so two runs of one commit would draw the edges in a
    # different order. The set is for membership only.
    shown = set(downstream[:max_nodes])
    for name in downstream[:max_nodes]:
        for parent in graph.direct_parents(name):
            if parent == model_name or parent in shown:
                lines.append(f"  {safe_id(parent, 'm')} --> {safe_id(name, 'm')}")

    if len(downstream) > max_nodes:
        remaining = len(downstream) - max_nodes
        lines.append(f'  more["and {remaining} more"]')
        lines.append(f"  {safe_id(model_name, 'm')} --> more")

    for view in views[:8]:
        node = safe_id(f"view_{view.name}", "v")
        lines.append(f'  {node}("{escape(view.name)}")')
        lines.append(f"  style {node} fill:#e6eefb,stroke:#3b6fb6")
        lines.append(f"  {safe_id(model_name, 'm')} --> {node}")

    return "\n".join(lines) + "\n"


def _layers(project: Project) -> list:
    """Layer specs, if the project knows them. Used only for ordering."""
    from hunter.config import resolve

    try:
        return resolve().config.layers
    except Exception:
        return []


#: How many models a pipeline diagram draws before it stops. Past this the
#: picture is a hairball, and the per-area tabs carry the detail.
PIPELINE_LIMIT = 60

#: Mermaid shapes the pipeline uses, by node kind. The browser-side selector
#: assembles the same diagram from the same spec, so these names are the
#: contract between the two.
PIPELINE_SHAPES: dict[str, tuple[str, str]] = {
    "box": ('["', '"]'),
    "round": ('("', '")'),
    "cylinder": ('[("', '")]'),
    "parallelogram": ('[/"', '"/]'),
    "hexagon": ('{{"', '"}}'),
}


@dataclass(frozen=True)
class PipelineNode:
    id: str
    label: str
    group: str
    shape: str
    kind: str
    style: str = ""


@dataclass(frozen=True)
class PipelineGroup:
    id: str
    label: str


@dataclass
class PipelineSpec:
    """The DAG as data: groups in reading order, nodes, edges.

    Kept separate from the Mermaid text so the dashboard can ship the same
    structure to the browser and redraw a selection of it there, with the
    health colouring decided once, here.
    """

    groups: list[PipelineGroup] = field(default_factory=list)
    nodes: list[PipelineNode] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)
    hidden: int = 0

    def to_json(self) -> str:
        import json

        return json.dumps(
            {
                "groups": [{"id": g.id, "label": g.label} for g in self.groups],
                "nodes": [
                    {
                        "id": n.id,
                        "label": n.label,
                        "group": n.group,
                        "shape": n.shape,
                        "kind": n.kind,
                        "style": n.style,
                    }
                    for n in self.nodes
                ],
                "edges": [list(edge) for edge in self.edges],
            },
            separators=(",", ":"),
            sort_keys=True,
        )


STYLE_OFF_PLAN = "fill:#fbe3de,stroke:#c0392b,stroke-width:2px"
STYLE_UNTESTED = "fill:#fdf2cc,stroke:#b7791f,stroke-dasharray:4 3"
STYLE_TEMPORARY = "fill:#f4f4f6,stroke:#9aa1ad"
STYLE_SOURCE = "fill:#e1f6fe,stroke:#4a90b8"
STYLE_VIEW = "fill:#e8e0fa,stroke:#7c5cbf"
STYLE_EXPLORE = "fill:#525aff,stroke:#3a40c4,color:#fff"


def pipeline_spec(
    project: Project,
    graph: Graph,
    alignment: Alignment,
    *,
    domain: str | None = None,
    max_models: int = PIPELINE_LIMIT,
) -> PipelineSpec:
    """The whole path data takes: raw sources, each layer, then the reports.

    Sources sit on the left, models in one column per layer in pipeline order,
    then the LookML views that read them, then the explores people open in
    Looker. Colour is health, not decoration:

    * red border, a table that was built with no design behind it
    * amber dashed border, a table nothing tests
    * grey rounded, a temporary working step that should never be reported from

    With ``domain`` set, that area's tables are drawn together with everything
    that feeds them, so a reader can follow one area from its raw sources to
    the explores that read it. Staging and integration models carry the source
    system's name as their area, not the business area, which is why the
    upstream walk is needed rather than a filter on the area alone.
    """
    spec = PipelineSpec()
    candidates = {model.name: model for model in project.models.values() if not model.vendored}
    if domain is None:
        chosen = set(candidates)
    else:
        chosen = {name for name, model in candidates.items() if model.domain == domain}
        frontier = list(chosen)
        while frontier:
            parent_names = [
                parent
                for name in frontier
                for parent in graph.direct_parents(name)
                if parent in candidates and parent not in chosen
            ]
            chosen.update(parent_names)
            frontier = parent_names
    models = sorted((candidates[name] for name in chosen), key=lambda model: model.name)
    if not models:
        return spec
    spec.hidden = max(0, len(models) - max_models)
    models = models[:max_models]
    names = {model.name for model in models}

    layers = _layers(project)
    stage = {layer.name: layer.pipeline_stage for layer in layers}
    by_layer: dict[str, list] = {}
    for model in models:
        by_layer.setdefault(model.layer or "unplaced", []).append(model)

    off_plan = {
        row.model_name
        for row in alignment.rows
        if row.model_name and row.designed is not Presence.PRESENT and row.repo is Presence.PRESENT
    }
    untested = {model.name for model in models if not project.tests_for(model.name)}

    # Views are often named after the model they read, and explores after
    # views, so each kind carries a marker in its id that a model id cannot.
    def source_id(unique_id: str) -> str:
        return safe_id(f"src__{unique_id}", "s")

    def view_id(name: str) -> str:
        return safe_id(f"view__{name}", "v")

    def explore_id(name: str) -> str:
        return safe_id(f"explore__{name}", "x")

    sources_used: dict[str, str] = {}
    for model in models:
        for unique_id in model.depends_on_sources:
            source = project.sources.get(unique_id)
            label = f"{source.source_name}.{source.name}" if source else unique_id.split(".")[-1]
            sources_used[unique_id] = label
    if sources_used:
        spec.groups.append(PipelineGroup("sources", "raw sources"))
        for unique_id, label in sorted(sources_used.items(), key=lambda item: item[1]):
            spec.nodes.append(
                PipelineNode(
                    source_id(unique_id), label, "sources", "cylinder", "source", STYLE_SOURCE
                )
            )

    for layer in sorted(by_layer, key=lambda name: (stage.get(name, 99), name)):
        group_id = safe_id(layer, "l")
        spec.groups.append(PipelineGroup(group_id, layer.replace("_", " ")))
        for model in by_layer[layer]:
            if model.name in off_plan:
                style = STYLE_OFF_PLAN
            elif model.name in untested and not model.is_temporary:
                style = STYLE_UNTESTED
            elif model.is_temporary:
                style = STYLE_TEMPORARY
            else:
                style = ""
            spec.nodes.append(
                PipelineNode(
                    safe_id(model.name, "m"),
                    model.name,
                    group_id,
                    "round" if model.is_temporary else "box",
                    "model",
                    style,
                )
            )

    views = sorted(
        (view for view in project.lookml_views.values() if view.model_name in names),
        key=lambda view: view.name,
    )
    view_names = {view.name for view in views}
    if views:
        spec.groups.append(PipelineGroup("looker_views", "Looker views (base layer)"))
        for view in views:
            spec.nodes.append(
                PipelineNode(
                    view_id(view.name),
                    view.name,
                    "looker_views",
                    "parallelogram",
                    "view",
                    STYLE_VIEW,
                )
            )

    explores = sorted(
        (
            explore
            for explore in project.explores.values()
            if explore.view_name in view_names or view_names.intersection(explore.joined_views())
        ),
        key=lambda explore: explore.name,
    )
    if explores:
        spec.groups.append(PipelineGroup("looker_explores", "Looker explores"))
        for explore in explores:
            spec.nodes.append(
                PipelineNode(
                    explore_id(explore.name),
                    explore.label or explore.name,
                    "looker_explores",
                    "hexagon",
                    "explore",
                    STYLE_EXPLORE,
                )
            )

    for model in models:
        for unique_id in model.depends_on_sources:
            if unique_id in sources_used:
                spec.edges.append((source_id(unique_id), safe_id(model.name, "m")))
        for parent in graph.direct_parents(model.name):
            if parent in names:
                spec.edges.append((safe_id(parent, "m"), safe_id(model.name, "m")))
    for view in views:
        spec.edges.append((safe_id(view.model_name or "", "m"), view_id(view.name)))
    for explore in explores:
        for name in [explore.view_name, *explore.joined_views()]:
            if name in view_names:
                spec.edges.append((view_id(name), explore_id(explore.name)))
    return spec


def render_pipeline(spec: PipelineSpec, keep: set[str] | None = None) -> str:
    """Mermaid text for a spec, or for the subset of its nodes in ``keep``.

    The browser does the same assembly from the same JSON, so anything added
    here has to be added there too. It is deliberately nothing but assembly.
    """
    if not spec.nodes:
        return 'flowchart LR\n  empty["No models were found"]\n'
    nodes = [node for node in spec.nodes if keep is None or node.id in keep]
    kept = {node.id for node in nodes}
    lines = ["flowchart LR"]
    for group in spec.groups:
        members = [node for node in nodes if node.group == group.id]
        if not members:
            continue
        lines.append(f'  subgraph {group.id}["{escape(group.label)}"]')
        for node in members:
            open_, close = PIPELINE_SHAPES[node.shape]
            lines.append(f"    {node.id}{open_}{escape(node.label)}{close}")
        lines.append("  end")
    for left, right in spec.edges:
        if left in kept and right in kept:
            lines.append(f"  {left} --> {right}")
    for node in nodes:
        if node.style:
            lines.append(f"  style {node.id} {node.style}")
    if spec.hidden and keep is None:
        lines.append(f'  more["and {spec.hidden} more models not drawn"]')
        lines.append("  style more fill:#fff,stroke:#ccc,stroke-dasharray:2 3")
    return "\n".join(lines) + "\n"


def pipeline_graph(
    project: Project,
    graph: Graph,
    alignment: Alignment,
    *,
    domain: str | None = None,
    max_models: int = PIPELINE_LIMIT,
) -> str:
    """The pipeline DAG as Mermaid text. See :func:`pipeline_spec`."""
    return render_pipeline(
        pipeline_spec(project, graph, alignment, domain=domain, max_models=max_models)
    )


#: Node id prefixes in an authored data flow diagram, and how each is coloured.
LOGICAL_FURNITURE_STYLE: dict[str, str] = {
    "data_source__": STYLE_SOURCE,
    "dashboard__": "fill:#e8e0fa,stroke:#7c5cbf",
}

_FRONTMATTER = re.compile(r"\A\s*---\n.*?\n---\n", re.S)

#: Presentation markup teams put in labels: bold wrappers sized by hand, and
#: icon elements that need a font the report does not carry. The text inside
#: a bold wrapper is kept; an icon element has no text and goes.
_LABEL_MARKUP = re.compile(r"</?b(?:\s[^>]*)?>|<i\s[^>]*>\s*</i>|<i\s[^>]*/>")

#: Room for a container's title, so it does not sit on top of what it holds.
_TITLE_ROOM = '%%{init: {"flowchart": {"subGraphTitleMargin": {"top": 12, "bottom": 12}}}}%%'

_FURNITURE_ID = re.compile(r"\b((?:data_source|dashboard)__[A-Za-z0-9_]+)")


def decorate_logical(source: str | None, alignment: Alignment) -> str:
    """The team's own data flow diagram, with Hunter's colours laid over it.

    The picture is theirs and is kept as drawn. Three things are changed:

    * The front matter is dropped. Its title collided with the diagram's own
      container label when both were drawn, and the tab already names it. It
      also asked for a layout engine the bundled library does not carry.
    * Every entity Hunter matched to the alignment is coloured by its real
      state, the same colours as the conceptual model, so the two agree.
    * Data sources and dashboards get the same colours they have on the data
      flow card, so a reader moving between the two is not relearning them.
    * Hand-sized bold wrappers and icon elements are taken out of labels. The
      library measures a label by its plain text, so a label drawn at another
      size overlaps its neighbours, and an icon font the page does not load
      renders as a gap.
    """
    if not source or not source.strip():
        return ""
    text = _FRONTMATTER.sub("", source, count=1).rstrip("\n")
    text = _LABEL_MARKUP.sub("", text)
    lines = [_TITLE_ROOM, text]

    by_node = {row.logical_name: row for row in alignment.rows if row.logical_name}
    for node, row in sorted(by_node.items()):
        lines.append(f"  style {node} {STATE_STYLE[row.state]}")

    seen: set[str] = set()
    for match in _FURNITURE_ID.finditer(text):
        node = match.group(1)
        if node in seen:
            continue
        seen.add(node)
        for prefix, style in LOGICAL_FURNITURE_STYLE.items():
            if node.startswith(prefix):
                lines.append(f"  style {node} {style}")
    return "\n".join(lines) + "\n"
