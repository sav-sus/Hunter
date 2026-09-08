"""The dependency graph, and the lineage questions checks ask of it.

Built once per run from the models' ``depends_on_models``. Traversals are
memoised because several checks walk the same subtrees: exposure weighting needs
every model's descendants, and blast radius needs them again for one model.

dbt will not build a project containing a cycle, so a cycle here means the
manifest is inconsistent with itself. It is reported rather than causing an
endless walk.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from math import log

from hunter.model.entities import Model


@dataclass
class Graph:
    """A directed graph of model dependencies, parents pointing to children."""

    children: dict[str, set[str]] = field(default_factory=dict)
    parents: dict[str, set[str]] = field(default_factory=dict)
    nodes: set[str] = field(default_factory=set)

    #: Traversal results, memoised. Several checks walk the same subtrees:
    #: exposure weighting needs every model's descendants, and blast radius
    #: needs them again for one model.
    _descendants: dict[str, frozenset[str]] = field(default_factory=dict, repr=False)
    _ancestors: dict[str, frozenset[str]] = field(default_factory=dict, repr=False)

    @classmethod
    def build(cls, models: dict[str, Model]) -> Graph:
        """Build from the normalised models.

        Dependencies on models Hunter does not have (a disabled model, or one
        from a package) are kept as nodes so lineage stays connected, but they
        carry no attributes.
        """
        graph = cls()
        for name, model in models.items():
            graph.nodes.add(name)
            graph.children.setdefault(name, set())
            graph.parents.setdefault(name, set())
            for parent in model.depends_on_models:
                graph.nodes.add(parent)
                graph.children.setdefault(parent, set()).add(name)
                graph.parents.setdefault(parent, set())
                graph.parents.setdefault(name, set()).add(parent)
        return graph

    # ---- neighbours ----

    def direct_children(self, name: str) -> list[str]:
        return sorted(self.children.get(name, set()))

    def direct_parents(self, name: str) -> list[str]:
        return sorted(self.parents.get(name, set()))

    def fanout(self, name: str) -> int:
        """How many models read directly from this one. FR5.3."""
        return len(self.children.get(name, set()))

    # ---- traversal ----

    def descendants(self, name: str) -> frozenset[str]:
        """Every model downstream of this one, at any depth."""
        cached = self._descendants.get(name)
        if cached is not None:
            return cached
        seen: set[str] = set()
        queue = deque(self.children.get(name, set()))
        while queue:
            current = queue.popleft()
            if current in seen or current == name:
                continue
            seen.add(current)
            queue.extend(self.children.get(current, set()) - seen)
        result = frozenset(seen)
        self._descendants[name] = result
        return result

    def ancestors(self, name: str) -> frozenset[str]:
        """Every model upstream of this one, at any depth."""
        cached = self._ancestors.get(name)
        if cached is not None:
            return cached
        seen: set[str] = set()
        queue = deque(self.parents.get(name, set()))
        while queue:
            current = queue.popleft()
            if current in seen or current == name:
                continue
            seen.add(current)
            queue.extend(self.parents.get(current, set()) - seen)
        result = frozenset(seen)
        self._ancestors[name] = result
        return result

    def roots(self) -> list[str]:
        """Models with no model parents. They read from sources or seeds."""
        return sorted(name for name in self.nodes if not self.parents.get(name))

    def leaves(self) -> list[str]:
        """Models nothing else reads."""
        return sorted(name for name in self.nodes if not self.children.get(name))

    def topological_order(self) -> list[str]:
        """Dependency order. Nodes in a cycle are appended, sorted, at the end."""
        indegree = {name: len(self.parents.get(name, set())) for name in self.nodes}
        ready = deque(sorted(name for name, count in indegree.items() if count == 0))
        order: list[str] = []
        while ready:
            current = ready.popleft()
            order.append(current)
            for child in sorted(self.children.get(current, set())):
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
        if len(order) < len(self.nodes):
            order.extend(sorted(self.nodes - set(order)))
        return order

    def cycles(self) -> list[list[str]]:
        """Cycles in the graph. dbt cannot build one, so any result is a bug."""
        colour: dict[str, int] = dict.fromkeys(self.nodes, 0)
        found: list[list[str]] = []
        stack: list[str] = []

        def walk(node: str) -> None:
            colour[node] = 1
            stack.append(node)
            for child in sorted(self.children.get(node, set())):
                if colour.get(child, 0) == 0:
                    walk(child)
                elif colour.get(child) == 1:
                    start = stack.index(child)
                    found.append([*stack[start:], child])
            stack.pop()
            colour[node] = 2

        for node in sorted(self.nodes):
            if colour.get(node, 0) == 0:
                walk(node)
        return found

    # ---- lineage anti-patterns, FR5.3 ----

    def rejoin_paths(self, name: str) -> list[str]:
        """Ancestors this model reaches by more than one direct path.

        A model that reads the same upstream table twice through different
        intermediates is the shape that causes double counting.
        """
        direct = self.direct_parents(name)
        if len(direct) < 2:
            return []
        counts: dict[str, int] = {}
        for parent in direct:
            for reached in {parent, *self.ancestors(parent)}:
                counts[reached] = counts.get(reached, 0) + 1
        return sorted(node for node, count in counts.items() if count > 1)

    def shares_no_path(self, first: str, second: str) -> bool:
        return second not in self.descendants(first) and second not in self.ancestors(first)


@dataclass(frozen=True)
class Consumers:
    """What reads a model, beyond other models.

    Used for exposure weighting, per FR7.4: a missing test on a model feeding 12
    dashboard fields costs more than the same gap on an orphan.
    """

    lookml_fields: int = 0
    lookml_views: int = 0
    explores: int = 0
    exposures: int = 0

    @property
    def total(self) -> int:
        return self.lookml_fields + self.explores + self.exposures

    @property
    def any(self) -> bool:
        return self.total > 0 or self.lookml_views > 0


def exposure_weight(
    downstream_models: int,
    consumers: Consumers,
    *,
    cap: float = 3.0,
) -> float:
    """How much more a finding on this model costs, given what depends on it.

    Grows with the log of the consumer count rather than linearly, so one very
    heavily used model cannot dominate the whole score, and is capped. A model
    nothing consumes still weighs 1.0: findings on it are real, just cheaper.
    """
    reach = downstream_models + consumers.lookml_fields + 2 * consumers.explores
    reach += 2 * consumers.exposures
    if reach <= 0:
        return 1.0
    weight = 1.0 + log(1 + reach, 4)
    return round(min(weight, cap), 3)
