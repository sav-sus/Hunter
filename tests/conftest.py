"""Builders for check tests.

A check reads a ``CheckContext`` and returns findings, so a test needs a small
project, a config, a register and an alignment. These helpers assemble one
without a repository on disk.
"""

from __future__ import annotations

import datetime as dt

import pytest

from hunter.checks.base import CheckContext
from hunter.config import resolve
from hunter.config.register import Register
from hunter.config.schema import HunterConfig
from hunter.ingest.dbml import DbmlData
from hunter.ingest.diagrams import ConceptualData, LogicalData
from hunter.ingest.droughty import DroughtyData
from hunter.ingest.lookml import LookmlData
from hunter.ingest.manifest import ManifestData
from hunter.model.align import build_alignment
from hunter.model.build import build_project
from hunter.model.entities import (
    Column,
    ConceptualEntity,
    DbtTest,
    DesignedColumn,
    DesignedEntity,
    DesignedRef,
    Exposure,
    Model,
)

TODAY = dt.date(2026, 9, 8)

ALL_AVAILABLE = frozenset({"manifest", "dbml", "conceptual", "lookml", "droughty", "git"})


@pytest.fixture
def config() -> HunterConfig:
    return resolve().config


def column(name: str, *, description: str | None = None, data_type: str | None = None) -> Column:
    return Column(name=name, description=description, data_type=data_type)


def model(
    name: str,
    *,
    layer: str = "warehouse",
    columns: list[Column] | None = None,
    deps: list[str] | None = None,
    sources: list[str] | None = None,
    description: str | None = None,
    materialised: str = "table",
    sql: str = "",
    owner: str | None = None,
    package: str = "my_project",
    vendored: bool = False,
    resource_type: str = "model",
) -> Model:
    """A model whose path places it in the named layer."""
    paths = {
        "staging": f"models/staging/stg_x/{name}.sql",
        "integration": f"models/integration/int_x/{name}.sql",
        "warehouse": f"models/warehouse/wh_x/{name}.sql",
        "reverse_etl": f"models/reverse_etl/{name}.sql",
        "seeds": f"seeds/{name}.csv",
        "none": f"elsewhere/{name}.sql",
    }
    return Model(
        name=name,
        unique_id=f"model.my_project.{name}",
        path=paths[layer],
        resource_type=resource_type,
        columns=columns or [],
        depends_on_models=deps or [],
        depends_on_sources=sources or [],
        description=description,
        materialisation=materialised,
        raw_code=sql,
        meta={"owner": owner} if owner else {},
        owner=owner,
        package=package,
        vendored=vendored,
    )


def designed(
    name: str,
    *,
    columns: list[DesignedColumn] | None = None,
    note: str | None = "A designed thing.",
    grain: str | None = "one row per thing",
    domain: str | None = None,
) -> DesignedEntity:
    return DesignedEntity(
        name=name,
        columns=columns or [DesignedColumn(name="thing_pk", is_primary_key=True, note="The key.")],
        note=note,
        grain_note=grain,
        domain=domain,
        source_file="models/_model/design.dbml",
    )


def dbt_test(
    model_name: str,
    kind: str,
    *,
    column: str | None = None,
    severity: str = "error",
    to_model: str | None = None,
) -> DbtTest:
    return DbtTest(
        unique_id=f"test.my_project.{model_name}_{kind}_{column or 'model'}",
        name=kind,
        kind=kind,
        tests_model=model_name,
        column=column,
        severity=severity,
        to_model=to_model,
    )


def build_context(
    config: HunterConfig,
    *,
    models: list[Model] | None = None,
    disabled: list[Model] | None = None,
    tests: list[DbtTest] | None = None,
    exposures: list[Exposure] | None = None,
    design: list[DesignedEntity] | None = None,
    design_refs: list[DesignedRef] | None = None,
    concepts: list[ConceptualEntity] | None = None,
    logical: LogicalData | None = None,
    lookml: LookmlData | None = None,
    droughty: DroughtyData | None = None,
    register: Register | None = None,
    available: frozenset[str] = ALL_AVAILABLE,
    as_of: dt.date = TODAY,
) -> CheckContext:
    """Assemble a context for one check to run against."""
    manifest = ManifestData()
    manifest.project_name = "my_project"
    for item in models or []:
        manifest.models[item.name] = item
    for item in disabled or []:
        item.enabled = False
        manifest.disabled_models[item.name] = item
    manifest.tests = tests or []
    manifest.exposures = exposures or []

    dbml = DbmlData()
    for item in design or []:
        dbml.entities[item.name] = item
    dbml.refs = design_refs or []

    conceptual = ConceptualData()
    for item in concepts or []:
        conceptual.entities[item.name] = item

    reg = register or Register()
    project, graph = build_project(
        config=config,
        register=reg,
        manifest=manifest,
        dbml=dbml if design else None,
        conceptual=conceptual if concepts else None,
        logical=logical,
        lookml=lookml,
        droughty=droughty,
    )
    alignment = build_alignment(project, config, reg, logical=logical)
    return CheckContext(
        project=project,
        graph=graph,
        config=config,
        register=reg,
        alignment=alignment,
        as_of=as_of,
        available=available,
    )


def rules_fired(findings) -> set[str]:
    return {finding.rule for finding in findings}


def finding_for(findings, rule_id: str):
    return next((finding for finding in findings if finding.rule == rule_id), None)


def score_of(context: CheckContext, findings) -> float:
    """The dimension score these findings and denominators imply."""
    lost = sum(finding.effective_points for finding in findings)
    available = sum(entry.points_available for entry in context.examined.values())
    if available <= 0:
        return 100.0
    return round(100.0 * (1 - lost / available), 1)
