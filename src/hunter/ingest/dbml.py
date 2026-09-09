"""Read authored DBML into the normalised model.

DBML is the design of record: all data modelling at Rittman Analytics is done in
it, so Hunter parses the files rather than asking for a second YAML description
of the same thing. Section 7.2.

This module is defensive on purpose. ``pydbml`` is MIT licensed with a small
maintainer base, and the pilot repository's main design file does not parse with
it as written: the file escapes a quote inside a note by doubling it, SQL style,
which the grammar rejects. One malformed note must not cost a whole score
dimension, so there are two layers of protection:

1. ``normalise`` rewrites known dialect variants before parsing.
2. If the whole file still fails, it is split into top-level blocks and each is
   parsed alone, so a bad block costs one table and reports itself as a finding.

The library is pinned exactly and wrapped behind this interface, per risk 1 in
section 15. Nothing outside this module imports ``pydbml``.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydbml import PyDBML

from hunter.model.entities import (
    DesignedColumn,
    DesignedEntity,
    DesignedRef,
    ParseIssue,
    extract_grain,
)

#: DBML relationship operators, in words.
CARDINALITY: dict[str, str] = {
    ">": "many-to-one",
    "<": "one-to-many",
    "-": "one-to-one",
    "<>": "many-to-many",
}


@dataclass
class DbmlData:
    """What the DBML files yielded."""

    entities: dict[str, DesignedEntity] = field(default_factory=dict)
    refs: list[DesignedRef] = field(default_factory=list)
    issues: list[ParseIssue] = field(default_factory=list)
    project_name: str | None = None
    normalised_files: list[str] = field(default_factory=list)


def normalise(text: str) -> tuple[str, int]:
    """Rewrite known DBML dialect variants into what ``pydbml`` accepts.

    Currently one rewrite: a doubled single quote inside a single-quoted string
    becomes a backslash escape. Tools in the DBML ecosystem accept the SQL-style
    ``''``; the grammar here does not.

    The rewrite is done with a small scanner rather than a regular expression,
    because ``''`` is genuinely ambiguous: inside a string with content it is an
    escaped quote, but at the start of a string it is an empty string. A regular
    expression cannot tell those apart and corrupts the second case.

    Returns:
        The rewritten text, and how many rewrites were made.
    """
    out: list[str] = []
    changes = 0
    index = 0
    length = len(text)
    state: str | None = None
    content = 0

    while index < length:
        char = text[index]

        if state is None:
            if text.startswith("//", index):
                state = "line_comment"
                out.append("//")
                index += 2
            elif text.startswith("/*", index):
                state = "block_comment"
                out.append("/*")
                index += 2
            elif text.startswith("'''", index):
                state = "triple"
                out.append("'''")
                index += 3
            elif char == "'":
                state = "single"
                content = 0
                out.append(char)
                index += 1
            elif char == '"':
                state = "double"
                out.append(char)
                index += 1
            else:
                out.append(char)
                index += 1
            continue

        if state == "line_comment":
            if char == "\n":
                state = None
            out.append(char)
            index += 1
            continue

        if state == "block_comment":
            if text.startswith("*/", index):
                state = None
                out.append("*/")
                index += 2
            else:
                out.append(char)
                index += 1
            continue

        if state == "triple":
            if text.startswith("'''", index):
                state = None
                out.append("'''")
                index += 3
            else:
                out.append(char)
                index += 1
            continue

        if state == "single":
            if char == "\\" and index + 1 < length:
                out.append(text[index : index + 2])
                index += 2
                content += 1
            elif text.startswith("''", index):
                if content == 0:
                    # An empty string. This pair closes it.
                    state = None
                    out.append("''")
                    index += 2
                else:
                    out.append("\\'")
                    index += 2
                    content += 1
                    changes += 1
            elif char == "'":
                state = None
                out.append(char)
                index += 1
            else:
                out.append(char)
                index += 1
                content += 1
            continue

        # state == "double"
        if char == "\\" and index + 1 < length:
            out.append(text[index : index + 2])
            index += 2
        elif char == '"':
            state = None
            out.append(char)
            index += 1
        else:
            out.append(char)
            index += 1

    return "".join(out), changes


def split_blocks(text: str) -> list[str]:
    """Split DBML into top-level blocks, ignoring braces inside strings.

    Used only by the recovery path, so a single unparseable table can be
    isolated from the ones around it.
    """
    blocks: list[str] = []
    current: list[str] = []
    depth = 0
    index = 0
    length = len(text)
    state: str | None = None

    while index < length:
        char = text[index]
        chunk = char
        step = 1

        if state is None:
            if text.startswith("//", index):
                state = "line_comment"
                chunk, step = "//", 2
            elif text.startswith("/*", index):
                state = "block_comment"
                chunk, step = "/*", 2
            elif text.startswith("'''", index):
                state = "triple"
                chunk, step = "'''", 3
            elif char == "'":
                state = "single"
            elif char == '"':
                state = "double"
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                current.append(chunk)
                index += step
                if depth == 0:
                    blocks.append("".join(current).strip())
                    current = []
                continue
        elif state == "line_comment":
            if char == "\n":
                state = None
        elif state == "block_comment":
            if text.startswith("*/", index):
                state = None
                chunk, step = "*/", 2
        elif state == "triple":
            if text.startswith("'''", index):
                state = None
                chunk, step = "'''", 3
        elif state == "single":
            if char == "\\" and index + 1 < length:
                chunk, step = text[index : index + 2], 2
            elif char == "'":
                state = None
        elif state == "double":
            if char == "\\" and index + 1 < length:
                chunk, step = text[index : index + 2], 2
            elif char == '"':
                state = None

        current.append(chunk)
        index += step

        # A top-level Ref: line ends at its newline rather than a brace.
        if depth == 0 and state is None and char == "\n":
            pending = "".join(current).strip()
            if pending and not pending.endswith(("{", ",")):
                blocks.append(pending)
                current = []

    tail = "".join(current).strip()
    if tail:
        blocks.append(tail)
    return [block for block in blocks if block]


#: ``table "my table" {`` or ``table orders_fact {``. Quoted names may contain
#: spaces, so this cannot be a whitespace split.
_DECLARATION = re.compile(
    r"""^\s*(?P<keyword>table|tablegroup|project)\s+
        (?:"(?P<quoted>[^"]+)"|'(?P<single>[^']+)'|(?P<bare>[^\s{"']+))""",
    re.IGNORECASE | re.VERBOSE,
)


def block_subject(block: str) -> str | None:
    """Name of the table or group a block declares, for error reporting."""
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "/*")):
            continue
        match = _DECLARATION.match(stripped)
        if match is None:
            return None
        return match.group("quoted") or match.group("single") or match.group("bare")
    return None


# pydbml exposes no type stubs, so its objects are Any at this boundary.
# Nothing outside this module sees them.
def _entity_from_table(table: Any, source_file: str, modified: dt.date | None) -> DesignedEntity:
    columns: list[DesignedColumn] = []
    for column in getattr(table, "columns", []):
        note = getattr(column, "note", None)
        columns.append(
            DesignedColumn(
                name=str(column.name),
                data_type=str(column.type) if column.type else None,
                note=str(note) if note and str(note).strip() else None,
                is_primary_key=bool(getattr(column, "pk", False)),
                is_unique=bool(getattr(column, "unique", False)),
                is_not_null=bool(getattr(column, "not_null", False)),
            )
        )
    table_note = getattr(table, "note", None)
    note_text = str(table_note) if table_note and str(table_note).strip() else None
    return DesignedEntity(
        name=str(table.name),
        columns=columns,
        note=note_text,
        grain_note=extract_grain(note_text),
        source_file=source_file,
        file_modified_at=modified,
    )


def _refs_from_db(db: Any) -> list[DesignedRef]:
    out: list[DesignedRef] = []
    for ref in getattr(db, "refs", []):
        table1 = getattr(ref, "table1", None)
        table2 = getattr(ref, "table2", None)
        if table1 is None or table2 is None:
            continue
        out.append(
            DesignedRef(
                from_table=str(table1.name),
                from_columns=sorted(str(column.name) for column in getattr(ref, "col1", [])),
                to_table=str(table2.name),
                to_columns=sorted(str(column.name) for column in getattr(ref, "col2", [])),
                cardinality=CARDINALITY.get(str(getattr(ref, "type", ""))),
            )
        )
    return out


def _domains_from_db(db: Any) -> dict[str, str]:
    """Table name to TableGroup name. Used for domain grouping on the site."""
    out: dict[str, str] = {}
    for group in getattr(db, "table_groups", []):
        for item in getattr(group, "items", []):
            name = getattr(item, "name", None) or str(item)
            out[str(name)] = str(group.name)
    return out


def _file_modified(path: Path) -> dt.date | None:
    """Last modification date of a design file.

    Surfaced on the site because a stale design file is itself a finding: it
    makes the reconciliation report false off-plan builds. Risk 2, section 15.
    """
    try:
        return dt.date.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return None


def parse_file(path: Path) -> DbmlData:
    """Parse one DBML file, recovering block by block if the whole file fails."""
    data = DbmlData()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        data.issues.append(
            ParseIssue(source=str(path), message=f"could not read: {exc}", recoverable=False)
        )
        return data

    modified = _file_modified(path)
    text, rewrites = normalise(raw)
    if rewrites:
        data.normalised_files.append(str(path))

    try:
        db = PyDBML(text)
    except Exception as whole_file_error:
        data.issues.append(
            ParseIssue(
                source=str(path),
                message=(
                    "the file did not parse as a whole, so it was read table by table: "
                    f"{whole_file_error}"
                ),
                recoverable=True,
            )
        )
        return _parse_block_by_block(path, text, modified, data)

    if db.project is not None:
        data.project_name = str(db.project.name)

    domains = _domains_from_db(db)
    for table in db.tables:
        entity = _entity_from_table(table, str(path), modified)
        entity.domain = domains.get(entity.name)
        data.entities[entity.name] = entity
    data.refs.extend(_refs_from_db(db))
    return data


def _parse_block_by_block(
    path: Path, text: str, modified: dt.date | None, data: DbmlData
) -> DbmlData:
    """Recovery path: one bad block costs one table, not the whole file."""
    groups: dict[str, str] = {}

    for block in split_blocks(text):
        first_word = block.split(maxsplit=1)[0].lower() if block.split() else ""
        subject = block_subject(block)

        if first_word == "project":
            continue

        if first_word == "tablegroup":
            # Read group membership textually. The names inside are bare
            # identifiers, so this needs no grammar.
            body = block[block.find("{") + 1 : block.rfind("}")]
            for line in body.splitlines():
                member = line.strip().strip(",")
                if member and not member.startswith("//") and subject:
                    groups[member] = subject
            continue

        if first_word not in {"table", "ref"}:
            continue

        try:
            db = PyDBML(block)
        except Exception as block_error:
            data.issues.append(
                ParseIssue(
                    source=str(path),
                    subject=subject,
                    message=(
                        f"this block did not parse, so it is missing from the design: {block_error}"
                    ),
                    recoverable=True,
                )
            )
            continue

        for table in db.tables:
            entity = _entity_from_table(table, str(path), modified)
            data.entities[entity.name] = entity
        data.refs.extend(_refs_from_db(db))

    for name, group in groups.items():
        if name in data.entities:
            data.entities[name].domain = group

    return data


def load_dbml(paths: list[Path]) -> DbmlData:
    """Parse every DBML file, merging the results.

    A table declared in two files is reported rather than silently overwritten:
    two designs for one entity is a modelling problem worth naming.
    """
    combined = DbmlData()
    for path in sorted(paths):
        result = parse_file(path)
        for name, entity in result.entities.items():
            if name in combined.entities:
                first = combined.entities[name].source_file
                combined.issues.append(
                    ParseIssue(
                        source=str(path),
                        subject=name,
                        message=(
                            f"{name} is designed in two files, {first} and {path}. "
                            "The second was ignored."
                        ),
                        recoverable=True,
                    )
                )
                continue
            combined.entities[name] = entity
        combined.refs.extend(result.refs)
        combined.issues.extend(result.issues)
        combined.normalised_files.extend(result.normalised_files)
        if combined.project_name is None:
            combined.project_name = result.project_name

    combined.refs.sort(key=lambda ref: ref.key)
    return combined


def resolve_paths(root: Path, patterns: list[str]) -> list[Path]:
    """Expand glob patterns against a project root."""
    found: list[Path] = []
    for pattern in patterns:
        found.extend(sorted(root.glob(pattern)))
    return sorted({path for path in found if path.is_file()})
