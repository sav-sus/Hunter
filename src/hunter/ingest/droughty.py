"""Read committed Droughty output.

Droughty introspects a warehouse and generates dbt tests, LookML views and a
DBML picture of what is deployed. Running it needs warehouse credentials, which
is why the requirements document put this at milestone M1.

The pilot repository commits Droughty's output, and that changes the picture:
the comparison can be made from files alone, with no credential. That is the
useful half, and it is the half that makes installing at a client a config
change rather than a security review.

Four files are read:

* ``droughty_project.yaml`` -- paths, plus the ``test_overwrite`` and
  ``test_ignore`` blocks, which record decisions the team has already made.
* ``droughty_schema.yml`` -- the generated tests and description references.
* ``field_descriptions.md`` -- the dbt doc blocks those references point at.
* the introspected DBML -- what Droughty found in the warehouse.

``test_overwrite`` and ``test_ignore`` are read as authored intent. Hunter never
re-reports a decision the team has already recorded there.

One rule here comes from the pilot team's own comment in their config: Droughty
regeneration "has previously applied only the first override per model and
silently dropped the rest with no warning. Hand-verify this block against
models/droughty_schema.yml after any regeneration." That check is deterministic,
so Hunter does it instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from hunter.ingest.dbml import load_dbml
from hunter.ingest.manifest import classify_test
from hunter.model.entities import DroughtyArtifacts, DroughtyTestSpec, ParseIssue

#: ``{% docs column_name %}`` ... ``{% enddocs %}``
DOC_BLOCK = re.compile(
    r"\{%\s*docs\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*%\}(?P<body>.*?)\{%\s*enddocs\s*%\}",
    re.DOTALL,
)

#: ``{{ doc("column_name") }}`` inside a description.
DOC_REF = re.compile(r"doc\(\s*[\"'](?P<name>[A-Za-z_][A-Za-z0-9_]*)[\"']\s*\)")

#: A description that is present but says nothing.
PLACEHOLDER_DESCRIPTIONS = frozenset(
    {"", "tbd", "todo", "fixme", "n/a", "na", "none", "no description", "placeholder", "xxx"}
)


@dataclass
class DroughtyPaths:
    """Paths Droughty is configured to write to, relative to the repository."""

    dbt_path: str | None = None
    dbml_path: str | None = None
    field_description_path: str | None = None
    field_description_file_name: str | None = None
    dbt_tests_filename: str | None = None
    lookml_path: str | None = None


@dataclass
class DroughtyData:
    """What the Droughty files yielded."""

    artifacts: DroughtyArtifacts = field(default_factory=DroughtyArtifacts)
    paths: DroughtyPaths = field(default_factory=DroughtyPaths)
    issues: list[ParseIssue] = field(default_factory=list)
    found_any: bool = False


def _read_yaml(path: Path, issues: list[ParseIssue]) -> dict[str, Any] | None:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        issues.append(
            ParseIssue(source=str(path), message=f"could not read: {exc}", recoverable=True)
        )
        return None
    except yaml.YAMLError as exc:
        issues.append(
            ParseIssue(source=str(path), message=f"is not valid YAML: {exc}", recoverable=True)
        )
        return None
    return loaded if isinstance(loaded, dict) else None


def _resolve(relative: str, bases: list[Path]) -> Path | None:
    """Find a file declared in ``droughty_project.yaml``.

    Droughty's declared paths are relative to the repository root, while the
    config file itself often sits in the dbt project directory below it. Rather
    than make every client state both, this tries each candidate base and takes
    the first that exists.
    """
    cleaned = relative.strip().lstrip("/")
    if not cleaned:
        return None
    for base in bases:
        candidate = base / cleaned
        if candidate.exists():
            return candidate
    return None


def _bases(root: Path, repo_root: Path | None) -> list[Path]:
    """Candidate bases for a declared path, nearest first, without duplicates."""
    candidates = [root]
    if repo_root is not None:
        candidates.append(repo_root)
    candidates.extend([root.parent, root.parent.parent])
    seen: set[Path] = set()
    out: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.add(resolved)
            out.append(candidate)
    return out


def _test_entries(raw: Any) -> list[str]:
    """Normalise a dbt tests list into test names.

    An entry is either a bare name (``not_null``) or a single-key mapping
    carrying arguments (``accepted_values: {values: [...]}}``).
    """
    names: list[str] = []
    if not isinstance(raw, list):
        return names
    for entry in raw:
        if isinstance(entry, str):
            names.append(entry)
        elif isinstance(entry, dict) and len(entry) == 1:
            names.append(next(iter(entry)))
    return names


def parse_project_file(
    path: Path,
) -> tuple[DroughtyPaths, list[DroughtyTestSpec], list[str], list[ParseIssue]]:
    """Read ``droughty_project.yaml``.

    Returns the configured paths, the hand-authored test overrides, the models
    excluded from generation, and any problems reading the file.
    """
    issues: list[ParseIssue] = []
    raw = _read_yaml(path, issues)
    if raw is None:
        return DroughtyPaths(), [], [], issues

    paths = DroughtyPaths(
        dbt_path=raw.get("dbt_path"),
        dbml_path=raw.get("dbml_path"),
        field_description_path=raw.get("field_description_path"),
        field_description_file_name=raw.get("field_description_file_name"),
        dbt_tests_filename=raw.get("dbt_tests_filename"),
        lookml_path=raw.get("lookml_path"),
    )

    overrides: list[DroughtyTestSpec] = []
    overwrite = (raw.get("test_overwrite") or {}).get("models") or {}
    if isinstance(overwrite, dict):
        for model, columns in overwrite.items():
            if not isinstance(columns, dict):
                continue
            for column, tests in columns.items():
                for name in _test_entries(tests):
                    overrides.append(
                        DroughtyTestSpec(
                            model=str(model),
                            column=str(column),
                            test_name=str(name),
                            kind=classify_test(str(name)),
                        )
                    )

    ignored: list[str] = []
    ignore_block = (raw.get("test_ignore") or {}).get("models") or []
    if isinstance(ignore_block, list):
        ignored = sorted({str(name) for name in ignore_block if isinstance(name, str)})

    overrides.sort(key=lambda spec: (spec.model, spec.column, spec.test_name))
    return paths, overrides, ignored, issues


def parse_generated_schema(
    path: Path,
) -> tuple[list[DroughtyTestSpec], dict[str, list[str]], list[str], list[ParseIssue]]:
    """Read ``droughty_schema.yml``: the tests and descriptions Droughty wrote.

    Returns the generated tests, the description text per model, the doc block
    names referenced, and any problems reading the file.
    """
    issues: list[ParseIssue] = []
    raw = _read_yaml(path, issues)
    if raw is None:
        return [], {}, [], issues

    specs: list[DroughtyTestSpec] = []
    descriptions: dict[str, list[str]] = {}
    refs: set[str] = set()

    for entry in raw.get("models") or []:
        if not isinstance(entry, dict):
            continue
        model = str(entry.get("name") or "")
        if not model:
            continue
        described: list[str] = []
        for column in entry.get("columns") or []:
            if not isinstance(column, dict):
                continue
            column_name = str(column.get("name") or "")
            if not column_name:
                continue
            description = column.get("description")
            if isinstance(description, str):
                found = DOC_REF.findall(description)
                refs.update(found)
                text = description.strip().lower()
                if found or text not in PLACEHOLDER_DESCRIPTIONS:
                    described.append(column_name)
            for name in _test_entries(column.get("tests")):
                specs.append(
                    DroughtyTestSpec(
                        model=model,
                        column=column_name,
                        test_name=str(name),
                        kind=classify_test(str(name)),
                    )
                )
        descriptions[model] = sorted(described)

    specs.sort(key=lambda spec: (spec.model, spec.column, spec.test_name))
    return specs, descriptions, sorted(refs), issues


def parse_field_descriptions(path: Path) -> tuple[list[str], list[str], list[ParseIssue]]:
    """Read the dbt doc blocks file.

    Returns the block names defined, the ones whose body is empty or a
    placeholder, and any problems reading the file.
    """
    issues: list[ParseIssue] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        issues.append(
            ParseIssue(source=str(path), message=f"could not read: {exc}", recoverable=True)
        )
        return [], [], issues

    defined: list[str] = []
    empty: list[str] = []
    for match in DOC_BLOCK.finditer(text):
        name = match.group("name")
        defined.append(name)
        body = match.group("body").strip().lower()
        if body in PLACEHOLDER_DESCRIPTIONS:
            empty.append(name)

    return sorted(set(defined)), sorted(set(empty)), issues


def load_droughty(
    root: Path,
    *,
    repo_root: Path | None = None,
    project_file: str | None = None,
    schema_file: str | None = None,
    field_descriptions: str | None = None,
    dbml_patterns: list[str] | None = None,
) -> DroughtyData:
    """Read every Droughty artifact that is present.

    Missing files are not errors. A repository with no Droughty output scores
    without this dimension, and the report says the dimension was skipped rather
    than scoring it as zero.

    Paths given explicitly win. Where they are absent, the ones declared inside
    ``droughty_project.yaml`` are used, which is how a client repository that
    already runs Droughty needs no extra configuration.
    """
    data = DroughtyData()
    artifacts = data.artifacts
    bases = _bases(root, repo_root)

    project_path = (root / project_file) if project_file else (root / "droughty_project.yaml")
    if not project_path.exists() and not project_file:
        found = _resolve("droughty_project.yaml", bases)
        if found is not None:
            project_path = found
    if project_path.exists():
        data.found_any = True
        artifacts.project_file = str(project_path)
        paths, overrides, ignored, issues = parse_project_file(project_path)
        data.paths = paths
        data.issues.extend(issues)
        artifacts.test_overrides = overrides
        artifacts.test_ignore_models = ignored

    schema_path: Path | None = None
    if schema_file:
        schema_path = root / schema_file
    elif data.paths.dbt_path and data.paths.dbt_tests_filename:
        schema_path = _resolve(
            f"{data.paths.dbt_path.rstrip('/')}/{data.paths.dbt_tests_filename}.yml", bases
        )
    if schema_path is not None and schema_path.exists():
        data.found_any = True
        artifacts.schema_file = str(schema_path)
        # When the schema was last changed comes from git history, attached in
        # model.build. The file's modification time is not used: on a CI
        # checkout every file was modified today, which would make the
        # staleness check pass for ever and the report change with the date.
        specs, descriptions, refs, issues = parse_generated_schema(schema_path)
        data.issues.extend(issues)
        artifacts.generated_tests = specs
        artifacts.generated_descriptions = descriptions
        artifacts.doc_refs = refs

    descriptions_path: Path | None = None
    if field_descriptions:
        descriptions_path = root / field_descriptions
    elif data.paths.field_description_path and data.paths.field_description_file_name:
        descriptions_path = _resolve(
            f"{data.paths.field_description_path.rstrip('/')}/"
            f"{data.paths.field_description_file_name}",
            bases,
        )
    if descriptions_path is not None and descriptions_path.exists():
        data.found_any = True
        defined, empty, issues = parse_field_descriptions(descriptions_path)
        data.issues.extend(issues)
        artifacts.doc_blocks_defined = defined
        artifacts.doc_blocks_empty = empty

    patterns = dbml_patterns
    if patterns is None and data.paths.dbml_path:
        patterns = [f"{data.paths.dbml_path.rstrip('/')}/*.dbml"]
    if patterns:
        dbml_files = [
            path for pattern in patterns for base in bases for path in sorted(base.glob(pattern))
        ]
        if dbml_files:
            data.found_any = True
            introspected = load_dbml(sorted(set(dbml_files)))
            artifacts.introspected = introspected.entities
            data.issues.extend(introspected.issues)

    return data


def missing_doc_blocks(artifacts: DroughtyArtifacts) -> list[str]:
    """Doc blocks referenced by the generated schema but never defined."""
    return sorted(set(artifacts.doc_refs) - set(artifacts.doc_blocks_defined))


def orphan_doc_blocks(artifacts: DroughtyArtifacts) -> list[str]:
    """Doc blocks defined and never referenced.

    Low severity on its own, but it is how a description file grows past the
    model it describes. The pilot has 360.
    """
    return sorted(set(artifacts.doc_blocks_defined) - set(artifacts.doc_refs))


def dropped_overrides(artifacts: DroughtyArtifacts) -> list[DroughtyTestSpec]:
    """Overrides declared in the config that never reached the generated schema.

    This is the check the pilot team currently does by hand after every
    regeneration, because Droughty has silently applied only the first override
    per model and dropped the rest.
    """
    if not artifacts.generated_tests:
        # The generated schema was not read. Reporting every override as
        # dropped would be a false alarm; the missing file is the finding.
        return []

    generated = {
        (spec.model, spec.column.lower(), spec.test_name) for spec in artifacts.generated_tests
    }
    generated_kinds = {
        (spec.model, spec.column.lower(), spec.kind) for spec in artifacts.generated_tests
    }
    missing: list[DroughtyTestSpec] = []
    for override in artifacts.test_overrides:
        exact = (override.model, override.column.lower(), override.test_name)
        by_kind = (override.model, override.column.lower(), override.kind)
        if exact not in generated and by_kind not in generated_kinds:
            missing.append(override)
    return missing
