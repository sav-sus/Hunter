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
        if row.grain:
            lines.append(f"    grain {safe_id(row.grain[:40])}")
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
