"""Read a dbt ``manifest.json`` into the normalised model.

The manifest is dbt's index of the project: every model, its columns, its
dependencies and its tests. Hunter reads it rather than importing dbt, which
keeps the dependency tree small and avoids adapter version conflicts.

Two things this module gets right that a naive reader does not:

* Disabled models. A model switched off by a config flag sits in
  ``manifest["disabled"]``, not ``manifest["nodes"]``. It is not unbuilt, and
  calling it unbuilt produces a false finding. The pilot repository has six.
* Test normalisation. What a test proves matters more than which package it
  came from, so ``dbt_utils.at_least_one`` and a bare ``at_least_one`` normalise
  to the same kind, and that kind is not counted as key cover.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hunter.model.entities import (
    Column,
    Exposure,
    Model,
    ParseIssue,
    Source,
    TestRef,
)

#: Manifest schema versions this reader is known to handle.
SUPPORTED_SCHEMA_VERSIONS = frozenset({"v11", "v12"})

#: Test names normalised to what they prove, not where they came from.
TEST_KINDS: dict[str, str] = {
    "unique": "unique",
    "not_null": "not_null",
    "relationships": "relationships",
    "accepted_values": "accepted_values",
    "unique_combination_of_columns": "unique",
    "expression_is_true": "expression",
    "at_least_one": "at_least_one",
    "not_null_proportion": "at_least_one",
    "equal_rowcount": "rowcount",
    "fewer_rows_than": "rowcount",
    "accepted_range": "expression",
}


class ManifestError(Exception):
    """The manifest is missing or unreadable."""


def _strip_package(test_name: str) -> str:
    """``dbt_utils.at_least_one`` -> ``at_least_one``."""
    return test_name.rsplit(".", 1)[-1]


def classify_test(test_name: str | None) -> str:
    """What a test proves. Unrecognised tests are ``custom``, never ignored."""
    if not test_name:
        return "custom"
    return TEST_KINDS.get(_strip_package(test_name), "custom")


def _columns(node: dict[str, Any]) -> list[Column]:
    raw = node.get("columns") or {}
    return [
        Column(
            name=str(name),
            data_type=(spec.get("data_type") or None),
            description=(spec.get("description") or None),
            meta=dict(spec.get("meta") or {}),
            tags=sorted(str(tag) for tag in (spec.get("tags") or [])),
        )
        for name, spec in sorted(raw.items())
        if isinstance(spec, dict)
    ]


def _owner_from_meta(meta: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            for inner in ("name", "email", "team"):
                nested = value.get(inner)
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
    return None


def _model_from_node(node: dict[str, Any], *, enabled: bool) -> Model:
    config = node.get("config") or {}
    meta = dict(node.get("meta") or {}) | dict(config.get("meta") or {})
    depends = (node.get("depends_on") or {}).get("nodes") or []

    return Model(
        name=str(node.get("name") or ""),
        unique_id=str(node.get("unique_id") or ""),
        path=str(node.get("original_file_path") or node.get("path") or ""),
        resource_type=str(node.get("resource_type") or "model"),
        package=str(node.get("package_name") or "") or None,
        schema_name=node.get("schema") or None,
        database=node.get("database") or None,
        alias=node.get("alias") or None,
        relation_name=node.get("relation_name") or None,
        materialisation=str(config.get("materialized") or "view"),
        enabled=enabled,
        description=(node.get("description") or None),
        columns=_columns(node),
        tags=sorted({str(tag) for tag in (node.get("tags") or [])}),
        meta=meta,
        depends_on_models=sorted(
            {ref.split(".")[-1] for ref in depends if ref.startswith("model.")}
        ),
        depends_on_sources=sorted(
            {".".join(ref.split(".")[-2:]) for ref in depends if ref.startswith("source.")}
        ),
        raw_code=str(node.get("raw_code") or ""),
        owner=_owner_from_meta(meta, ("owner", "team")),
    )


def _test_from_node(node: dict[str, Any]) -> TestRef:
    metadata = node.get("test_metadata") or {}
    kwargs = metadata.get("kwargs") or {}
    config = node.get("config") or {}
    depends = (node.get("depends_on") or {}).get("nodes") or []

    test_name = metadata.get("name")
    attached = node.get("attached_node")
    tests_model: str | None = None
    if isinstance(attached, str) and attached.startswith("model."):
        tests_model = attached.split(".")[-1]
    else:
        model_refs = [ref for ref in depends if ref.startswith("model.")]
        if len(model_refs) == 1:
            tests_model = model_refs[0].split(".")[-1]
        elif model_refs:
            # A relationships test depends on both ends. The tested model is the
            # one the test file is attached to; fall back to the first ref.
            tests_model = model_refs[0].split(".")[-1]

    column = node.get("column_name") or kwargs.get("column_name")
    to_ref = kwargs.get("to")
    to_model: str | None = None
    if isinstance(to_ref, str) and "ref(" in to_ref:
        inner = to_ref.split("ref(", 1)[1]
        to_model = inner.strip(" )'\"").split("'")[0].split('"')[0] or None

    return TestRef(
        unique_id=str(node.get("unique_id") or ""),
        name=str(test_name or node.get("name") or ""),
        kind=classify_test(test_name if isinstance(test_name, str) else None),
        tests_model=tests_model,
        column=str(column) if column else None,
        severity=str(config.get("severity") or "error").lower(),
        to_model=to_model,
        to_field=str(kwargs.get("field")) if kwargs.get("field") else None,
        file=str(node.get("original_file_path") or "") or None,
    )


def _source_from_node(node: dict[str, Any]) -> Source:
    return Source(
        name=str(node.get("name") or ""),
        unique_id=str(node.get("unique_id") or ""),
        source_name=str(node.get("source_name") or ""),
        schema_name=node.get("schema") or None,
        database=node.get("database") or None,
        description=(node.get("description") or None),
        columns=_columns(node),
        relation_name=node.get("relation_name") or None,
    )


def _exposure_from_node(node: dict[str, Any]) -> Exposure:
    owner = node.get("owner") or {}
    depends = (node.get("depends_on") or {}).get("nodes") or []
    return Exposure(
        name=str(node.get("name") or ""),
        unique_id=str(node.get("unique_id") or ""),
        exposure_type=node.get("type") or None,
        owner=(owner.get("name") or owner.get("email") or None)
        if isinstance(owner, dict)
        else None,
        depends_on_models=sorted(
            {ref.split(".")[-1] for ref in depends if ref.startswith("model.")}
        ),
        url=node.get("url") or None,
    )


class ManifestData:
    """What one manifest yielded, before cross-referencing."""

    def __init__(self) -> None:
        self.models: dict[str, Model] = {}
        self.disabled_models: dict[str, Model] = {}
        self.sources: dict[str, Source] = {}
        self.exposures: list[Exposure] = []
        self.tests: list[TestRef] = []
        self.issues: list[ParseIssue] = []
        self.dbt_version: str | None = None
        self.schema_version: str | None = None
        self.project_name: str | None = None

    def vendored_counts(self) -> dict[str, int]:
        """How many models each installed package contributed."""
        counts: dict[str, int] = {}
        for model in self.models.values():
            if model.vendored and model.package:
                counts[model.package] = counts.get(model.package, 0) + 1
        return dict(sorted(counts.items()))


def load_manifest(path: Path) -> ManifestData:
    """Read a manifest file.

    Raises:
        ManifestError: the file is absent or is not a dbt manifest.
    """
    if not path.exists():
        raise ManifestError(
            f"no manifest at {path}. Run `dbt parse` in the project, or pass "
            "--manifest with the path to one your dbt job already produces."
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"{path} is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise ManifestError(f"could not read {path}: {exc}") from exc

    if not isinstance(raw, dict) or "nodes" not in raw:
        raise ManifestError(f"{path} does not look like a dbt manifest")

    return parse_manifest(raw, source=str(path))


def parse_manifest(raw: dict[str, Any], *, source: str = "manifest.json") -> ManifestData:
    """Normalise an already-loaded manifest mapping."""
    data = ManifestData()
    metadata = raw.get("metadata") or {}
    data.dbt_version = metadata.get("dbt_version")
    data.project_name = metadata.get("project_name")

    schema_url = str(metadata.get("dbt_schema_version") or "")
    version = schema_url.rstrip(".json").rsplit("/", 1)[-1] if schema_url else ""
    data.schema_version = version or None
    if version and version not in SUPPORTED_SCHEMA_VERSIONS:
        data.issues.append(
            ParseIssue(
                source=source,
                message=(
                    f"manifest schema {version} is newer or older than the versions this "
                    f"Hunter release was tested against "
                    f"({', '.join(sorted(SUPPORTED_SCHEMA_VERSIONS))}). "
                    "Fields may be read incorrectly."
                ),
                recoverable=True,
            )
        )

    for node in (raw.get("nodes") or {}).values():
        if not isinstance(node, dict):
            continue
        resource = node.get("resource_type")
        if resource in {"model", "seed", "snapshot"}:
            model = _model_from_node(node, enabled=True)
            if model.name:
                data.models[model.name] = model
        elif resource == "test":
            data.tests.append(_test_from_node(node))

    # Disabled nodes. Built, switched off: neither delivered nor unstarted.
    for entries in (raw.get("disabled") or {}).values():
        if not isinstance(entries, list):
            continue
        for node in entries:
            if not isinstance(node, dict):
                continue
            if node.get("resource_type") not in {"model", "seed", "snapshot"}:
                continue
            model = _model_from_node(node, enabled=False)
            if model.name and model.name not in data.models:
                data.disabled_models[model.name] = model

    # Keyed on unique_id, not source_name.name: two sources can share the
    # latter across packages, and a collision silently drops one.
    for node in (raw.get("sources") or {}).values():
        if isinstance(node, dict):
            source_table = _source_from_node(node)
            data.sources[source_table.unique_id] = source_table

    for node in (raw.get("exposures") or {}).values():
        if isinstance(node, dict):
            data.exposures.append(_exposure_from_node(node))

    # Anything from an installed package is vendored. Holding a client to
    # their conventions on code they did not write, and cannot change without
    # forking the package, would produce findings nobody can act on.
    root_package = data.project_name
    if root_package:
        for collection in (data.models, data.disabled_models):
            for model in collection.values():
                model.vendored = bool(model.package) and model.package != root_package

    data.exposures.sort(key=lambda exposure: exposure.name)
    data.tests.sort(key=lambda test: test.unique_id)
    return data
