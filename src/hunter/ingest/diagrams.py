"""Read authored Mermaid diagrams: the conceptual and logical models.

Rittman Analytics authors the conceptual model as a Mermaid ``block-beta``
diagram and the logical model as a flowchart. Both live in the repository, so
Hunter reads them rather than asking for the same information a second time in
YAML.

What Hunter takes, and what it deliberately does not:

* Entity names, business labels and domain grouping are taken as given. They are
  what the business calls things, and nothing else knows them.
* Build status is read as a **claim**, never as truth. It is hand-maintained
  colour coding on 88 style lines in the pilot, so it drifts. Hunter computes
  real status from the repository and reports where the diagram disagrees. That
  disagreement is the finding.

The colour code is learnt from the diagram's own legend rather than hardcoded,
so a project that recolours its legend still reads correctly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from hunter.model.entities import ConceptualEntity, ParseIssue

#: ``block:wh_finance:1`` opens a domain block in a block-beta diagram.
BLOCK_OPEN = re.compile(r"^\s*block:(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?::(?P<span>\d+))?\s*$")

#: ``wh_finance__budgets("budgets")``, ``id["label"]``, ``id[(label)]``.
#: The label is captured by scanning rather than by a bracket-matching pattern,
#: because labels legitimately contain the delimiters: one pilot entity is
#: labelled "billing document (billed sales)".
NODE_HEAD = re.compile(
    r"^\s*(?P<id>[A-Za-z_][A-Za-z0-9_]*)\s*(?P<open>\(\(|\[\(|\(|\[|\{)(?P<body>.*)$"
)

CLOSERS: dict[str, str] = {"((": "))", "[(": ")]", "(": ")", "[": "]", "{": "}"}

#: ``style wh_finance__billed_sales stroke:#c0392b,stroke-width:2px``
STYLE = re.compile(r"^\s*style\s+(?P<id>[A-Za-z_][A-Za-z0-9_]*)\s+(?P<props>.+?)\s*$")

#: ``A --> B``, ``A -->|label| B``, ``A -.-> B``, ``A --- B``
EDGE = re.compile(
    r"(?P<left>[A-Za-z_][A-Za-z0-9_]*)\s*"
    r"(?:-{2,3}>|-\.->|={2,3}>|-{3}|-\.-)"
    r"\s*(?:\|[^|]*\|\s*)?"
    r"(?P<right>[A-Za-z_][A-Za-z0-9_]*)"
)

#: Style properties that carry meaning rather than decoration.
DISTINGUISHING = frozenset({"stroke", "stroke-width", "stroke-dasharray", "opacity"})

#: Node id prefixes that are diagram furniture, not entities.
FURNITURE_PREFIXES = ("legend__", "subgraph", "data_source__", "dashboard__", "classdef__")

#: Node id suffixes that mark a domain heading rather than an entity.
FURNITURE_SUFFIXES = ("__label", "_label", "__title", "_title")

FURNITURE_IDS = frozenset({"title", "legend", "header", "space", "columns", "groups"})

#: Legend names that mean "this exists". Used to pick the default status.
BUILT_WORDS = ("built", "live", "delivered", "done", "complete", "implemented")

#: A warning glyph in a label is a second signal that the entity deviates.
WARN_GLYPHS = ("⚠", "❗", "❌")


@dataclass
class ConceptualData:
    """What the conceptual diagram yielded."""

    entities: dict[str, ConceptualEntity] = field(default_factory=dict)
    issues: list[ParseIssue] = field(default_factory=list)
    legend: dict[str, dict[str, str]] = field(default_factory=dict)
    source_file: str | None = None


@dataclass
class LogicalData:
    """What the logical diagram yielded."""

    entities: dict[str, str] = field(default_factory=dict)
    data_sources: dict[str, str] = field(default_factory=dict)
    flows: list[tuple[str, str]] = field(default_factory=list)
    issues: list[ParseIssue] = field(default_factory=list)
    source_file: str | None = None

    def sources_for(self, entity: str) -> list[str]:
        """Data sources feeding an entity, directly."""
        return sorted(
            {left for left, right in self.flows if right == entity and left in self.data_sources}
        )


def parse_node(line: str) -> tuple[str, str] | None:
    """Extract ``(node id, label)`` from one Mermaid node declaration.

    Returns None where the line declares no node. Labels are unquoted, and HTML
    tags inside them are stripped, so what comes back is what a reader sees.
    """
    head = NODE_HEAD.match(line)
    if head is None:
        return None

    body = head.group("body")
    closer = CLOSERS[head.group("open")]

    stripped = body.strip()
    if stripped.startswith(('"', "'")):
        quote = stripped[0]
        end = stripped.rfind(quote)
        label = stripped[1:end] if end > 0 else stripped[1:]
    else:
        end = body.rfind(closer)
        label = body[:end] if end >= 0 else body

    label = re.sub(r"<[^>]+>", " ", label)
    label = " ".join(label.split()).strip().strip("\"'")
    return head.group("id"), label


def is_furniture(node_id: str) -> bool:
    """True for titles, legends, spacers and other diagram scaffolding."""
    if node_id in FURNITURE_IDS:
        return True
    if node_id.startswith(FURNITURE_PREFIXES):
        return True
    return node_id.endswith(FURNITURE_SUFFIXES)


def parse_style_props(text: str) -> dict[str, str]:
    """``stroke:#666,stroke-width:1px`` into a mapping."""
    props: dict[str, str] = {}
    for part in text.split(","):
        if ":" not in part:
            continue
        key, _, value = part.partition(":")
        props[key.strip().lower()] = value.strip().lower()
    return props


def _signatures(styles: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """Learn each status's visual signature from the diagram's own legend."""
    out: dict[str, dict[str, str]] = {}
    for node_id, props in styles.items():
        if not node_id.startswith("legend__"):
            continue
        status = node_id[len("legend__") :]
        if status in {"label", "title"}:
            continue
        signature = {key: value for key, value in props.items() if key in DISTINGUISHING}
        if signature:
            out[status] = signature
    return out


def _default_status(signatures: dict[str, dict[str, str]]) -> str | None:
    """Which legend entry means "this exists"."""
    for status in signatures:
        if any(word in status.lower() for word in BUILT_WORDS):
            return status
    return next(iter(signatures), None)


def _claimed_status(
    props: dict[str, str],
    label: str,
    signatures: dict[str, dict[str, str]],
    default: str | None,
) -> str | None:
    """Match a node's style against the legend signatures.

    A node's properties must all appear, with the same values, in a signature
    for that status to be a candidate. The candidate matching most properties
    wins. An unstyled node takes the default, which is what the legend calls
    "built".
    """
    if any(glyph in label for glyph in WARN_GLYPHS):
        for status in signatures:
            if "flag" in status.lower() or "deviat" in status.lower():
                return status

    meaningful = {key: value for key, value in props.items() if key in DISTINGUISHING}
    if not meaningful:
        return default

    best: str | None = None
    best_score = 0
    for status, signature in signatures.items():
        if any(signature.get(key) != value for key, value in meaningful.items()):
            continue
        if len(meaningful) > best_score:
            best, best_score = status, len(meaningful)
    return best or default


def parse_conceptual(path: Path) -> ConceptualData:
    """Read a Mermaid ``block-beta`` conceptual model.

    Entity names come from node ids, business names from node labels, and
    domains from the enclosing ``block:`` name.
    """
    data = ConceptualData(source_file=str(path))
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        data.issues.append(
            ParseIssue(source=str(path), message=f"could not read: {exc}", recoverable=False)
        )
        return data

    styles: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        match = STYLE.match(line)
        if match:
            styles[match.group("id")] = parse_style_props(match.group("props"))

    signatures = _signatures(styles)
    data.legend = signatures
    default = _default_status(signatures)

    domain: str | None = None
    depth = 0
    for raw_line in text.splitlines():
        line = raw_line.split("%%", 1)[0]
        if not line.strip():
            continue

        opener = BLOCK_OPEN.match(line)
        if opener:
            name = opener.group("name")
            depth += 1
            if not is_furniture(name):
                domain = name
            continue

        if line.strip() == "end":
            depth = max(0, depth - 1)
            if depth == 0:
                domain = None
            continue

        parsed = parse_node(line)
        if parsed is None:
            continue
        node_id, label = parsed
        if is_furniture(node_id):
            continue

        cleaned_label = label
        for glyph in WARN_GLYPHS:
            cleaned_label = cleaned_label.replace(glyph, "")
        cleaned_label = " ".join(cleaned_label.split())

        data.entities[node_id] = ConceptualEntity(
            name=node_id,
            business_name=cleaned_label or None,
            domain=domain,
            claimed_status=_claimed_status(styles.get(node_id, {}), label, signatures, default),
            source_file=str(path),
        )

    if not data.entities:
        data.issues.append(
            ParseIssue(
                source=str(path),
                message=(
                    "no entities were found in this conceptual diagram. Either the file is "
                    "not a Mermaid block diagram, or its node naming differs from the "
                    "convention Hunter reads."
                ),
                recoverable=True,
            )
        )
    return data


def parse_logical(path: Path) -> LogicalData:
    """Read a Mermaid flowchart logical model, or data flow diagram.

    Node ids follow the same ``<group>__<entity>`` convention as the conceptual
    diagram, so entities are separated from data sources and dashboards by
    prefix rather than by shape.
    """
    data = LogicalData(source_file=str(path))
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        data.issues.append(
            ParseIssue(source=str(path), message=f"could not read: {exc}", recoverable=False)
        )
        return data

    for raw_line in text.splitlines():
        line = raw_line.split("%%", 1)[0]
        stripped = line.strip()
        if not stripped or stripped.startswith(("subgraph", "style", "classDef", "class ")):
            continue

        parsed = parse_node(line)
        if parsed is not None:
            node_id, label = parsed
            if node_id.startswith("data_source__"):
                data.data_sources[node_id] = label
            elif not is_furniture(node_id):
                data.entities[node_id] = label

        for edge in EDGE.finditer(line):
            data.flows.append((edge.group("left"), edge.group("right")))

    data.flows = sorted(set(data.flows))
    return data
