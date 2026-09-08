"""Match one entity across the model levels.

Names differ between levels, and on the pilot repository they differ a lot: the
conceptual diagram calls something ``wh_commerce__demand_orders`` while the
design calls it ``wh_commerce__demand_order_fact``. Exact matching finds 3 of
72; normalising the names finds 36. The rest is a real gap, not a matching
failure, and the alignment check reports it as one.

Three ways to match, strongest first:

1. Declared. The register's ``implements`` field. A person said so.
2. Exact. The names are identical.
3. Normalised. Layer prefix, entity suffix and plural removed.

A normalised match that lands on two candidates is reported as ambiguous rather
than resolved by picking one, because picking one silently produces a wrong
reconciliation row that reads as fact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Entity suffixes stripped before comparison. Read from config at the call
#: site; this is the fallback for callers with no config to hand.
DEFAULT_SUFFIXES = ("_fact", "_dim", "_xa", "_bridge", "_snapshot")

#: Layer prefixes stripped before comparison.
DEFAULT_PREFIXES = ("wh_", "int_", "stg_", "base_")

#: Domain aliases seen in practice: the conceptual diagram and the design do
#: not always spell a domain the same way.
_DOMAIN_TRIM = re.compile(r"_(data|engagement|domain)$")


def singularise(word: str) -> str:
    """Crude English singularisation, enough for entity names."""
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("sses", "shes", "ches", "xes", "zes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def normalise_name(
    name: str,
    *,
    suffixes: tuple[str, ...] = DEFAULT_SUFFIXES,
    prefixes: tuple[str, ...] = DEFAULT_PREFIXES,
) -> str:
    """Reduce an entity name to a comparable form.

    ``wh_commerce__demand_orders`` and ``wh_commerce__demand_order_fact`` both
    reduce to ``demand_order``.
    """
    lowered = name.strip().lower()
    for suffix in sorted(suffixes, key=len, reverse=True):
        if lowered.endswith(suffix):
            lowered = lowered[: -len(suffix)]
            break
    lowered = lowered.rstrip("_")
    if "__" in lowered:
        lowered = lowered.split("__", 1)[1]
    else:
        for prefix in prefixes:
            if lowered.startswith(prefix):
                lowered = lowered[len(prefix) :]
                break
    parts = [singularise(part) for part in lowered.split("_") if part]
    return "_".join(parts)


def normalise_domain(name: str, *, prefixes: tuple[str, ...] = DEFAULT_PREFIXES) -> str | None:
    """Domain part of a name, spelt comparably.

    ``wh_master_data__customer`` and ``wh_master__customer_dim`` both give
    ``master``.
    """
    lowered = name.strip().lower()
    if "__" not in lowered:
        return None
    head = lowered.split("__", 1)[0]
    for prefix in prefixes:
        if head.startswith(prefix):
            head = head[len(prefix) :]
            break
    head = _DOMAIN_TRIM.sub("", head)
    return head or None


def normalise_domain_value(
    value: str | None, *, prefixes: tuple[str, ...] = DEFAULT_PREFIXES
) -> str | None:
    """Spell a bare domain name comparably.

    Domains reach Hunter from three places that disagree: a DBML table group
    (``wh_commerce``), a model name (``commerce``), and a conceptual diagram
    block (``wh_master_data``). Left alone they produce 16 domain groups on the
    pilot where there are 10, splitting the site's grouping in two.
    """
    if not value:
        return None
    lowered = value.strip().lower()
    for prefix in prefixes:
        if lowered.startswith(prefix):
            lowered = lowered[len(prefix) :]
            break
    lowered = _DOMAIN_TRIM.sub("", lowered)
    return lowered or None


def qualified_key(
    name: str,
    *,
    suffixes: tuple[str, ...] = DEFAULT_SUFFIXES,
    prefixes: tuple[str, ...] = DEFAULT_PREFIXES,
) -> str:
    """Domain-qualified comparable key, e.g. ``master/customer``."""
    domain = normalise_domain(name, prefixes=prefixes)
    base = normalise_name(name, suffixes=suffixes, prefixes=prefixes)
    return f"{domain}/{base}" if domain else base


@dataclass(frozen=True)
class Match:
    """The outcome of matching one name against a set of candidates."""

    target: str | None
    method: str
    confidence: float
    candidates: tuple[str, ...] = ()

    @property
    def matched(self) -> bool:
        return self.target is not None

    @property
    def ambiguous(self) -> bool:
        return self.target is None and len(self.candidates) > 1


NO_MATCH = Match(target=None, method="none", confidence=0.0)


@dataclass
class Index:
    """Candidate names, indexed for exact, qualified and loose matching."""

    exact: dict[str, str] = field(default_factory=dict)
    qualified: dict[str, list[str]] = field(default_factory=dict)
    loose: dict[str, list[str]] = field(default_factory=dict)
    suffixes: tuple[str, ...] = DEFAULT_SUFFIXES
    prefixes: tuple[str, ...] = DEFAULT_PREFIXES

    @classmethod
    def build(
        cls,
        names: list[str],
        *,
        suffixes: tuple[str, ...] = DEFAULT_SUFFIXES,
        prefixes: tuple[str, ...] = DEFAULT_PREFIXES,
    ) -> Index:
        index = cls(suffixes=suffixes, prefixes=prefixes)
        for name in sorted(names):
            index.exact[name.lower()] = name
            index.qualified.setdefault(
                qualified_key(name, suffixes=suffixes, prefixes=prefixes), []
            ).append(name)
            index.loose.setdefault(
                normalise_name(name, suffixes=suffixes, prefixes=prefixes), []
            ).append(name)
        return index

    def find(self, name: str, *, declared: str | None = None) -> Match:
        """Match one name, strongest method first."""
        if declared:
            target = self.exact.get(declared.lower())
            if target is not None:
                return Match(target=target, method="declared", confidence=1.0)

        target = self.exact.get(name.lower())
        if target is not None:
            return Match(target=target, method="exact", confidence=1.0)

        # Domain-qualified before loose, so two entities named the same thing in
        # different domains are not confused with each other.
        key = qualified_key(name, suffixes=self.suffixes, prefixes=self.prefixes)
        candidates = self.qualified.get(key, [])
        if len(candidates) == 1:
            return Match(target=candidates[0], method="normalised", confidence=0.9)
        if len(candidates) > 1:
            return Match(
                target=None,
                method="ambiguous",
                confidence=0.0,
                candidates=tuple(sorted(candidates)),
            )

        base = normalise_name(name, suffixes=self.suffixes, prefixes=self.prefixes)
        loose = self.loose.get(base, [])
        if len(loose) == 1:
            return Match(target=loose[0], method="normalised", confidence=0.75)
        if len(loose) > 1:
            return Match(
                target=None,
                method="ambiguous",
                confidence=0.0,
                candidates=tuple(sorted(loose)),
            )

        return NO_MATCH
