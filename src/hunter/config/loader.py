"""Resolve configuration across levels, and record where each value came from.

Precedence, weakest first: built-in defaults, the RA house ruleset, the project
``hunter.yml``, the register, then per-model ``meta.hunter``. Section 7.

The provenance map is not a debugging aid. FR7b requires Hunter to report which
house rules a project has overridden, disabled or reweighted, and why, and FR7d
makes that divergence report a first-class output. So the merge records the
origin of every leaf value as it goes.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from hunter.config.schema import DEFAULT_WEIGHTS, HunterConfig
from hunter.enums import CONFIG_PRECEDENCE, ConfigLevel

HOUSE_DIR = Path(__file__).parent / "house"
DEFAULT_HOUSE = "ra-house@1"

#: Lists of objects merged item by item, keyed on the named field, rather than
#: replaced wholesale. A project adding one layer should not have to restate
#: every layer the house defines.
KEYED_LISTS: dict[str, str] = {"layers": "name", "entities": "kind"}

#: Lists that accumulate across levels instead of replacing.
APPEND_LISTS: frozenset[str] = frozenset({"ignores"})


class ConfigError(Exception):
    """Configuration could not be loaded or is not valid."""


@dataclass(frozen=True)
class Divergence:
    """One place the project departs from the house standard. FR7b, FR7d."""

    path: str
    house_value: Any
    project_value: Any
    level: ConfigLevel
    reason: str | None = None

    @property
    def kind(self) -> str:
        if isinstance(self.project_value, bool) and not self.project_value:
            return "disabled"
        if isinstance(self.project_value, int | float) and isinstance(
            self.house_value, int | float
        ):
            return "reweighted"
        return "overridden"

    def describe(self) -> str:
        why = f" Reason: {self.reason}" if self.reason else " No reason recorded."
        return (
            f"{self.path} {self.kind} at {self.level} level: "
            f"house {self.house_value!r}, project {self.project_value!r}.{why}"
        )


@dataclass
class ResolvedConfig:
    """A validated ruleset, plus the audit trail behind it."""

    config: HunterConfig
    provenance: dict[str, ConfigLevel] = field(default_factory=dict)
    divergences: list[Divergence] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    def level_of(self, path: str) -> ConfigLevel:
        return self.provenance.get(path, ConfigLevel.DEFAULT)

    def overridden_paths(self) -> list[str]:
        return sorted(d.path for d in self.divergences)


def read_yaml(path: Path) -> dict[str, Any]:
    """Read one YAML file into a mapping. An empty file is an empty mapping."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(f"configuration file not found: {path}") from exc
    except OSError as exc:
        raise ConfigError(f"could not read {path}: {exc}") from exc

    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path} is not valid YAML: {exc}") from exc

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ConfigError(f"{path} must contain a mapping at the top level")
    return loaded


def builtin_defaults() -> dict[str, Any]:
    """The floor. Only what pydantic field defaults cannot express.

    Everything else defaults on the model, so this stays short on purpose.
    """
    return {"scoring": {"weights": {str(k): v for k, v in DEFAULT_WEIGHTS.items()}}}


def house_path(spec: str) -> Path:
    """Turn ``ra-house@1`` into the shipped file path.

    Version-pinned by name, per FR15.8: RA changing its standard must not move a
    client's score until the client bumps this string.
    """
    name, _, version = spec.partition("@")
    if not version:
        raise ConfigError(f"house ruleset {spec!r} must name a version, for example {name}@1")
    path = HOUSE_DIR / f"{name}-{version}.yml"
    if not path.exists():
        available = sorted(p.stem for p in HOUSE_DIR.glob("*.yml"))
        raise ConfigError(
            f"house ruleset {spec!r} is not shipped with this version of Hunter. "
            f"Available: {', '.join(available) or 'none'}"
        )
    return path


def _merge_keyed_list(
    base: list[Any],
    overlay: list[Any],
    key: str,
    path: str,
    provenance: dict[str, ConfigLevel],
    level: ConfigLevel,
) -> list[Any]:
    """Merge two lists of mappings on a key field, preserving base order."""
    by_key: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in base:
        if not isinstance(item, dict) or key not in item:
            raise ConfigError(f"{path}: every entry needs a {key!r} field")
        by_key[str(item[key])] = copy.deepcopy(item)
        order.append(str(item[key]))

    for item in overlay:
        if not isinstance(item, dict) or key not in item:
            raise ConfigError(f"{path}: every entry needs a {key!r} field")
        name = str(item[key])
        if name in by_key:
            _merge_into(by_key[name], item, f"{path}.{name}", provenance, level)
        else:
            by_key[name] = copy.deepcopy(item)
            order.append(name)
            _mark_leaves(item, f"{path}.{name}", provenance, level)

    return [by_key[name] for name in order]


def _merge_into(
    base: dict[str, Any],
    overlay: dict[str, Any],
    path: str,
    provenance: dict[str, ConfigLevel],
    level: ConfigLevel,
) -> None:
    """Deep-merge ``overlay`` into ``base``, recording provenance of each leaf."""
    for key, value in overlay.items():
        here = f"{path}.{key}" if path else key
        if key in KEYED_LISTS and isinstance(value, list):
            base[key] = _merge_keyed_list(
                base.get(key, []) or [], value, KEYED_LISTS[key], here, provenance, level
            )
        elif key in APPEND_LISTS and isinstance(value, list):
            existing = base.get(key) or []
            base[key] = list(existing) + copy.deepcopy(value)
            provenance[here] = level
        elif isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge_into(base[key], value, here, provenance, level)
        else:
            base[key] = copy.deepcopy(value)
            # Record every leaf, not just the subtree root. Otherwise a level
            # that introduces a whole section gets one provenance entry and the
            # divergence report cannot see individual values. FR7b.
            _mark_leaves(value, here, provenance, level)


def _mark_leaves(
    value: Any,
    path: str,
    provenance: dict[str, ConfigLevel],
    level: ConfigLevel,
) -> None:
    """Attribute ``value`` and every leaf beneath it to ``level``."""
    if isinstance(value, dict):
        for key, inner in value.items():
            _mark_leaves(inner, f"{path}.{key}" if path else str(key), provenance, level)
        return
    if isinstance(value, list):
        key_field = KEYED_LISTS.get(path.rsplit(".", 1)[-1])
        if key_field is not None:
            for item in value:
                if isinstance(item, dict) and key_field in item:
                    _mark_leaves(item, f"{path}.{item[key_field]}", provenance, level)
            return
    provenance[path] = level


def _lookup(root: dict[str, Any], dotted: str) -> tuple[bool, Any]:
    """Follow a dotted path, resolving keyed lists by their key field.

    Returns ``(found, value)`` so a legitimately falsy value is not mistaken
    for an absent one.
    """
    parts = dotted.split(".")
    current: Any = root
    for index, part in enumerate(parts):
        if isinstance(current, list):
            container = parts[index - 1] if index else ""
            key_field = KEYED_LISTS.get(container)
            if key_field is None:
                return False, None
            match = next(
                (
                    item
                    for item in current
                    if isinstance(item, dict) and str(item.get(key_field)) == part
                ),
                None,
            )
            if match is None:
                return False, None
            current = match
            continue
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _reason_for(merged: dict[str, Any], path: str) -> str | None:
    """Pull the recorded reason for a rule override, if the project gave one."""
    parts = path.split(".")
    if len(parts) >= 2 and parts[0] == "rules":
        found, value = _lookup(merged, f"rules.{parts[1]}")
        if found and isinstance(value, dict):
            reason = value.get("reason")
            return str(reason) if reason else None
    return None


def _collect_divergences(
    merged: dict[str, Any],
    house: dict[str, Any],
    provenance: dict[str, ConfigLevel],
) -> list[Divergence]:
    """Every place the project departs from the house standard.

    Two kinds. A leaf the project changed that the house had already set, and a
    rule the project switched off or repointed. The second needs handling
    separately because the house ruleset declares no ``rules`` block: its
    position is the implicit one that every rule is on at its declared points.
    Without this, FR7b's "disabled or reweighted" would never appear in the
    report, which is exactly the case the fixture caught.
    """
    stronger = {ConfigLevel.PROJECT, ConfigLevel.REGISTER, ConfigLevel.MODEL}
    out: list[Divergence] = []
    for path, level in sorted(provenance.items()):
        if level not in stronger:
            continue
        if path.startswith("rules."):
            continue  # handled below, against the implicit house position
        found, house_value = _lookup(house, path)
        if not found:
            continue
        _, project_value = _lookup(merged, path)
        if house_value == project_value:
            continue
        out.append(
            Divergence(
                path=path,
                house_value=house_value,
                project_value=project_value,
                level=level,
                reason=_reason_for(merged, path),
            )
        )

    out.extend(_rule_divergences(merged, provenance, stronger))
    out.sort(key=lambda item: item.path)
    return out


def _rule_divergences(
    merged: dict[str, Any],
    provenance: dict[str, ConfigLevel],
    stronger: set[ConfigLevel],
) -> list[Divergence]:
    """Rules the project switched off, reweighted or re-graded."""
    rules = merged.get("rules")
    if not isinstance(rules, dict):
        return []

    out: list[Divergence] = []
    for rule_id, setting in sorted(rules.items()):
        if not isinstance(setting, dict):
            continue
        level = (
            provenance.get(f"rules.{rule_id}.enabled")
            or provenance.get(f"rules.{rule_id}.points")
            or provenance.get(f"rules.{rule_id}.severity")
            or ConfigLevel.PROJECT
        )
        if level not in stronger:
            continue
        reason = setting.get("reason")

        if setting.get("enabled") is False:
            out.append(
                Divergence(
                    path=f"rules.{rule_id}.enabled",
                    house_value=True,
                    project_value=False,
                    level=level,
                    reason=str(reason) if reason else None,
                )
            )
        if setting.get("points") is not None:
            out.append(
                Divergence(
                    path=f"rules.{rule_id}.points",
                    house_value="the rule's declared points",
                    project_value=setting["points"],
                    level=level,
                    reason=str(reason) if reason else None,
                )
            )
        if setting.get("severity") is not None:
            out.append(
                Divergence(
                    path=f"rules.{rule_id}.severity",
                    house_value="the rule's declared severity",
                    project_value=setting["severity"],
                    level=level,
                    reason=str(reason) if reason else None,
                )
            )
    return out


def resolve(
    project_file: Path | None = None,
    *,
    house: str | None = None,
    overlays: dict[ConfigLevel, dict[str, Any]] | None = None,
) -> ResolvedConfig:
    """Build the resolved ruleset.

    Args:
        project_file: the client's ``hunter.yml``. Omit to score against the
            house standard alone, which is how a first assessment runs.
        house: house ruleset spec, e.g. ``ra-house@1``. Defaults to the project
            file's ``extends``, then to the shipped default.
        overlays: extra levels to apply, used for per-model overrides and by
            tests. Applied in precedence order.

    Raises:
        ConfigError: the files are missing, malformed, or the merged result is
            not a valid ruleset.
    """
    sources: list[str] = []
    provenance: dict[str, ConfigLevel] = {}

    merged = builtin_defaults()
    _mark_leaves(merged, "", provenance, ConfigLevel.DEFAULT)

    project_raw: dict[str, Any] = {}
    if project_file is not None:
        project_raw = read_yaml(project_file)
        sources.append(str(project_file))

    house_spec = house or project_raw.get("extends") or DEFAULT_HOUSE
    hpath = house_path(str(house_spec))
    house_raw = read_yaml(hpath)
    sources.append(str(hpath))
    house_version = str(house_raw.pop("version", house_spec))

    _merge_into(merged, house_raw, "", provenance, ConfigLevel.HOUSE)
    house_snapshot = copy.deepcopy(merged)

    if project_raw:
        _merge_into(merged, project_raw, "", provenance, ConfigLevel.PROJECT)

    for level in CONFIG_PRECEDENCE:
        overlay = (overlays or {}).get(level)
        if overlay and level in {ConfigLevel.REGISTER, ConfigLevel.MODEL}:
            _merge_into(merged, overlay, "", provenance, level)

    merged["extends"] = str(house_spec)
    merged["house_version"] = house_version
    provenance["house_version"] = ConfigLevel.HOUSE

    try:
        config = HunterConfig.model_validate(merged)
    except Exception as exc:  # pydantic ValidationError, kept readable
        where = project_file or hpath
        raise ConfigError(f"resolved configuration is not valid ({where}): {exc}") from exc

    return ResolvedConfig(
        config=config,
        provenance=provenance,
        divergences=_collect_divergences(merged, house_snapshot, provenance),
        sources=sources,
    )
