"""Finding layers the ruleset does not declare.

A ruleset names the layers it expects: staging, integration, warehouse. A
repository grows, and one day there is a ``models/marts/`` directory nobody
added to ``hunter.yml``. Before this module, those models landed in no layer
and were quietly held to no standard. Now they land in a layer named after
their directory, the report says the layer was found rather than declared, and
nothing needs editing for a new part of the warehouse to show up.

A discovered layer carries no rules of its own. Hunter knows the models are
grouped; it does not know what the group should look like. Declaring the layer
in the ruleset is how a team says what it should look like, and the report
prompts for that.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import PurePosixPath

from hunter.config.schema import HunterConfig, LayerSpec
from hunter.model.entities import Model

#: A model directly under the models directory has no directory to name a
#: layer after, and a name with no ``__`` has no prefix to read. Both are left
#: unlayered, and the naming checks report them as such.


def _directory_under(path: str, models_dir: str) -> str | None:
    """The first directory under the models directory, or None."""
    parts = PurePosixPath(path).parts
    root = PurePosixPath(models_dir).parts
    if len(parts) <= len(root) + 1 or tuple(parts[: len(root)]) != root:
        return None
    return parts[len(root)]


def _prefix_of(name: str) -> str | None:
    """``mart_shop__orders`` has the prefix ``mart_``; ``orders_by_day`` has none.

    House naming is ``prefix_domain__entity``. Without the double underscore
    there is no way to tell a prefix from the first word of a name.
    """
    if "__" not in name:
        return None
    head, _, _ = name.partition("_")
    return f"{head}_" if head else None


def _is_placed(model: Model, config: HunterConfig) -> bool:
    if config.layer_for_path(model.path) is not None:
        return True
    return any(
        candidate.prefix and model.name.startswith(candidate.prefix) for candidate in config.layers
    )


def discover_layers(config: HunterConfig, models: Iterable[Model]) -> list[LayerSpec]:
    """Layers present in the models directory that the ruleset does not name.

    One layer per first-level directory holding models the ruleset places
    nowhere. The layer takes a prefix only where every model in the directory
    shares one, so a mixed directory is not held to a naming rule nobody set.
    """
    taken = {layer.name for layer in config.layers}
    grouped: dict[str, list[Model]] = {}
    for model in models:
        if not model.is_sql_model or model.vendored or _is_placed(model, config):
            continue
        directory = _directory_under(model.path, config.paths.models_dir)
        if directory is None or directory in taken:
            continue
        grouped.setdefault(directory, []).append(model)

    found: list[LayerSpec] = []
    for directory in sorted(grouped):
        prefixes = {_prefix_of(model.name) for model in grouped[directory]}
        prefix = prefixes.pop() if len(prefixes) == 1 else None
        found.append(
            LayerSpec(
                name=directory,
                paths=[f"{config.paths.models_dir}/{directory}/**"],
                prefix=prefix,
                discovered=True,
            )
        )
    return found


def with_layers(config: HunterConfig, extra: Iterable[LayerSpec]) -> HunterConfig:
    """The same ruleset with discovered layers appended. Declared ones win."""
    extra = list(extra)
    if not extra:
        return config
    return config.model_copy(update={"layers": [*config.layers, *extra]})
