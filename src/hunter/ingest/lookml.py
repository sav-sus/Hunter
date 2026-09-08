"""Read LookML views and explores into the normalised model.

Scope at this version, per risk 6 in section 15: view files, field references
and explores. No Liquid, no derived-table SQL analysis. Derived tables are
recorded and skipped, which costs almost nothing on the pilot repository where 5
of 50 files use them.

The point of this module is FR4.1: map every LookML field to the dbt column it
depends on, so a column rename in dbt surfaces as a broken dashboard field in
the same pull request rather than in a client's report.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import lkml

from hunter.model.entities import Explore, ExploreJoin, LookmlField, LookmlView, ParseIssue

#: ``${TABLE}.column_name`` inside a field's SQL.
TABLE_COLUMN = re.compile(r"\$\{TABLE\}\.([A-Za-z_][A-Za-z0-9_]*)")

#: ``${other_view.field_name}`` or ``${field_name}``.
FIELD_REFERENCE = re.compile(r"\$\{(?!TABLE\})([A-Za-z_][A-Za-z0-9_.]*)\}")

FIELD_SECTIONS: tuple[tuple[str, str], ...] = (
    ("dimensions", "dimension"),
    ("dimension_groups", "dimension_group"),
    ("measures", "measure"),
    ("filters", "filter"),
    ("parameters", "parameter"),
)


@dataclass
class LookmlData:
    """What the LookML files yielded."""

    views: dict[str, LookmlView] = field(default_factory=dict)
    explores: dict[str, Explore] = field(default_factory=dict)
    datagroups: list[str] = field(default_factory=list)
    issues: list[ParseIssue] = field(default_factory=list)
    files_read: int = 0

    #: Refinements awaiting their base view, keyed by the base view name.
    refinements: dict[str, list[LookmlView]] = field(default_factory=dict)


#: Liquid expressions inside a sql_table_name. The pilot templates the project
#: and dataset from user attributes while leaving the table name literal.
LIQUID = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.DOTALL)

#: What a resolved table name must look like to be usable.
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def table_to_model_name(sql_table_name: str | None) -> str | None:
    """Reduce a ``sql_table_name`` to the dbt model it points at.

    Handles the forms that appear in practice: a bare model name, a
    ``dataset.table`` pair, a fully qualified ``project.dataset.table``,
    backticks, quotes, and Liquid substitution of the project or dataset.

    Liquid is stripped rather than treated as unresolvable, because the common
    case templates only the project and dataset and leaves the table name
    literal. Where the table name itself is templated, nothing identifier-shaped
    remains and this returns None: the cross-layer check then reports the view
    as unresolvable rather than inventing a broken link.
    """
    if not sql_table_name:
        return None

    cleaned = sql_table_name.strip()
    while cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        cleaned = cleaned[1:-1]

    cleaned = LIQUID.sub("", cleaned).replace("`", "").replace('"', "").strip()
    if not cleaned:
        return None

    last = cleaned.rsplit(".", 1)[-1].strip()
    return last if IDENTIFIER.match(last) else None


def _is_yes(value: Any) -> bool:
    return str(value).strip().lower() in {"yes", "true"}


def _field_from_spec(spec: dict[str, object], view_name: str, kind: str, file: str) -> LookmlField:
    sql = spec.get("sql")
    sql_text = str(sql) if sql is not None else None
    referenced = sorted(set(TABLE_COLUMN.findall(sql_text))) if sql_text else []

    # A dimension_group with a timeframes block has no sql of its own on some
    # projects; the datatype field still names the underlying column.
    if not referenced and kind == "dimension_group":
        datatype_sql = spec.get("datatype")
        if isinstance(datatype_sql, str):
            referenced = sorted(set(TABLE_COLUMN.findall(datatype_sql)))

    return LookmlField(
        name=str(spec.get("name") or ""),
        view=view_name,
        field_type=kind,
        lookml_type=str(spec["type"]) if spec.get("type") is not None else None,
        sql=sql_text,
        label=str(spec["label"]) if spec.get("label") is not None else None,
        description=str(spec["description"]) if spec.get("description") is not None else None,
        hidden=_is_yes(spec.get("hidden")),
        referenced_columns=referenced,
        file=file,
    )


def is_refinement(view_name: str) -> bool:
    """``view: +orders`` refines ``orders`` rather than redefining it."""
    return view_name.startswith("+")


def refinement_target(view_name: str) -> str:
    return view_name.lstrip("+")


def _view_from_spec(spec: dict[str, Any], file: str) -> LookmlView:
    name = str(spec.get("name") or "")
    derived = spec.get("derived_table")
    sql_table_name = spec.get("sql_table_name")
    extends = spec.get("extends") or spec.get("extends__all") or []
    if isinstance(extends, str):
        extends = [extends]
    flat_extends: list[str] = []
    for item in extends:
        if isinstance(item, list):
            flat_extends.extend(str(inner) for inner in item)
        else:
            flat_extends.append(str(item))

    fields: list[LookmlField] = []
    for section, kind in FIELD_SECTIONS:
        for entry in spec.get(section) or []:
            if isinstance(entry, dict):
                fields.append(_field_from_spec(entry, name, kind, file))

    view = LookmlView(
        name=name,
        sql_table_name=str(sql_table_name) if sql_table_name is not None else None,
        is_derived_table=derived is not None,
        extends=sorted(set(flat_extends)),
        fields=sorted(fields, key=lambda item: (item.field_type, item.name)),
        file=file,
    )
    view.model_name = table_to_model_name(view.sql_table_name)
    return view


def _explore_from_spec(spec: dict[str, Any], file: str) -> Explore:
    joins: list[ExploreJoin] = []
    for entry in spec.get("joins") or []:
        if not isinstance(entry, dict):
            continue
        joins.append(
            ExploreJoin(
                name=str(entry.get("name") or ""),
                relationship=str(entry["relationship"])
                if entry.get("relationship") is not None
                else None,
                join_type=str(entry["type"]) if entry.get("type") is not None else None,
                sql_on=str(entry["sql_on"]) if entry.get("sql_on") is not None else None,
            )
        )

    name = str(spec.get("name") or "")
    # An explore's base view is `from` where given, else `view_name`, else the
    # explore's own name. That order is Looker's.
    base = spec.get("from") or spec.get("view_name") or name
    return Explore(
        name=name,
        view_name=str(base) if base else None,
        label=str(spec["label"]) if spec.get("label") is not None else None,
        datagroup=str(spec["persist_with"]) if spec.get("persist_with") is not None else None,
        persist_for=str(spec["persist_for"]) if spec.get("persist_for") is not None else None,
        joins=sorted(joins, key=lambda join: join.name),
        file=file,
    )


def parse_file(path: Path) -> LookmlData:
    """Parse one LookML file. A parse failure is reported, never raised."""
    data = LookmlData()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        data.issues.append(
            ParseIssue(source=str(path), message=f"could not read: {exc}", recoverable=False)
        )
        return data

    try:
        parsed = lkml.load(text)
    except Exception as exc:
        data.issues.append(
            ParseIssue(
                source=str(path),
                message=f"this file did not parse, so its views are missing: {exc}",
                recoverable=True,
            )
        )
        return data

    if not isinstance(parsed, dict):
        return data

    data.files_read = 1
    file = str(path)

    for spec in parsed.get("views") or []:
        if not isinstance(spec, dict):
            continue
        view = _view_from_spec(spec, file)
        if not view.name:
            continue
        if is_refinement(view.name):
            target = refinement_target(view.name)
            data.refinements.setdefault(target, []).append(view)
        else:
            data.views[view.name] = view

    for spec in parsed.get("explores") or []:
        if isinstance(spec, dict):
            explore = _explore_from_spec(spec, file)
            if explore.name:
                data.explores[explore.name] = explore

    for spec in parsed.get("datagroups") or []:
        if isinstance(spec, dict) and spec.get("name"):
            data.datagroups.append(str(spec["name"]))

    return data


def _merge_refinement(base: LookmlView, refinement: LookmlView) -> None:
    """Fold a ``view: +name`` block into the view it refines.

    Looker's rules: a refinement's field of the same name replaces the base
    field, other fields are added, and a value set in the refinement wins.
    """
    by_name = {existing.name: existing for existing in base.fields}
    for incoming in refinement.fields:
        by_name[incoming.name] = incoming
    base.fields = sorted(by_name.values(), key=lambda item: (item.field_type, item.name))

    if refinement.sql_table_name:
        base.sql_table_name = refinement.sql_table_name
        base.model_name = table_to_model_name(refinement.sql_table_name)
    if refinement.is_derived_table:
        base.is_derived_table = True
    if refinement.extends:
        base.extends = sorted(set(base.extends) | set(refinement.extends))
    if refinement.file and refinement.file not in base.refined_by:
        base.refined_by.append(refinement.file)


def load_lookml(paths: list[Path]) -> LookmlData:
    """Parse every LookML file, merging the results.

    Refinements are folded into the views they refine. A view defined twice in
    full is reported: LookML has refinement syntax for layering, so two whole
    definitions of one name is a mistake worth naming.
    """
    combined = LookmlData()
    for path in sorted(paths):
        result = parse_file(path)
        combined.files_read += result.files_read
        combined.issues.extend(result.issues)
        combined.datagroups.extend(result.datagroups)

        for name, view in result.views.items():
            if name in combined.views:
                combined.issues.append(
                    ParseIssue(
                        source=str(path),
                        subject=name,
                        message=(
                            f"view {name} is defined in full in both "
                            f"{combined.views[name].file} and {path}. The first was kept. "
                            "Use a refinement, view: +name, to layer onto a view."
                        ),
                        recoverable=True,
                    )
                )
                continue
            combined.views[name] = view

        for target, refinements in result.refinements.items():
            combined.refinements.setdefault(target, []).extend(refinements)

        for name, explore in result.explores.items():
            combined.explores.setdefault(name, explore)

    # Apply refinements once every base view has been read, since a refinement
    # may sit in a file that sorts before its base.
    for target in sorted(combined.refinements):
        base = combined.views.get(target)
        refinements = combined.refinements[target]
        if base is None:
            combined.issues.append(
                ParseIssue(
                    source=refinements[0].file or "lookml",
                    subject=target,
                    message=(
                        f"view: +{target} refines a view that is not defined anywhere "
                        "Hunter looked. Its fields are missing from the semantic layer."
                    ),
                    recoverable=True,
                )
            )
            continue
        for refinement in sorted(refinements, key=lambda item: item.file or ""):
            _merge_refinement(base, refinement)

    combined.datagroups = sorted(set(combined.datagroups))
    return combined


def resolve_paths(root: Path, patterns: list[str]) -> list[Path]:
    """Expand glob patterns against a project root.

    Dashboard files are excluded: they carry no view or explore definitions and
    the LookML dialect inside them differs.
    """
    found: list[Path] = []
    for pattern in patterns:
        found.extend(sorted(root.glob(pattern)))
    return sorted({path for path in found if path.is_file() and ".dashboard." not in path.name})
