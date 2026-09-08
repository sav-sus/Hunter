"""Every check, in the order they run.

Importing this module registers every rule. That matters because the registry
is built as a side effect of importing each check module: anything that needs a
complete rule list (the conventions page, the register's own validation, the
score engine's renormalisation) must import from here rather than from one
module.
"""

from __future__ import annotations

from collections.abc import Callable

from hunter.checks import (
    alignment,
    conformance,
    crosslayer,
    documentation,
    droughty,
    entity,
    lineage,
    naming,
    structure,
    testing,
)
from hunter.checks.base import (
    REGISTRY,
    CheckContext,
    Denominator,
    Findings,
    Registry,
    Rule,
    collect,
    dimensions_with_runnable_rules,
    rules_runnable,
)
from hunter.model.findings import Finding

#: Run order. Alignment runs last because its findings read best after the
#: detail, and because the register validation it carries reads as a summary.
ALL_CHECKS: tuple[Callable[[CheckContext], list[Finding]], ...] = (
    documentation.run,
    naming.run,
    structure.run,
    testing.run,
    entity.run,
    lineage.run,
    conformance.run,
    crosslayer.run,
    droughty.run,
    alignment.run,
)

CHECK_MODULES: dict[str, Callable[[CheckContext], list[Finding]]] = {
    "documentation": documentation.run,
    "naming": naming.run,
    "structure": structure.run,
    "testing": testing.run,
    "entity": entity.run,
    "lineage": lineage.run,
    "conformance": conformance.run,
    "crosslayer": crosslayer.run,
    "droughty": droughty.run,
    "alignment": alignment.run,
}

__all__ = [
    "ALL_CHECKS",
    "CHECK_MODULES",
    "REGISTRY",
    "CheckContext",
    "Denominator",
    "Finding",
    "Findings",
    "Registry",
    "Rule",
    "collect",
    "dimensions_with_runnable_rules",
    "rules_runnable",
]
