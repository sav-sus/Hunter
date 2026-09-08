#!/usr/bin/env python3
"""Build the tiny-shop example's dbt manifest.

The manifest is generated rather than hand-typed, and the SQL it carries is read
from the real files on disk. That matters: the files and the manifest cannot
drift apart, so the example stays a project someone could plausibly have
written rather than a fixture that only looks like one.

The layout mirrors the Rittman Analytics standard: an `analytics_warehouse`
directory holding `models/`, `lookml/` and `docs/`, with design documents under
`docs/data_model_design/` and the introspected picture under `docs/db_docs/`.

Run it after changing any model:

    python examples/tiny-shop/build.py

Names are invented and resemble no client's.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).parent
PROJECT_DIR = HERE / "analytics_warehouse"
MODELS = PROJECT_DIR / "models"
PROJECT = "tiny_shop"
SCHEMA_VERSION = "https://schemas.getdbt.com/dbt/manifest/v12.json"


@dataclass
class Spec:
    """One model, and what it is in the example to demonstrate."""

    name: str
    path: str
    materialized: str
    demonstrates: str
    columns: dict[str, str] = field(default_factory=dict)
    depends_models: list[str] = field(default_factory=list)
    depends_sources: list[str] = field(default_factory=list)
    owner: str | None = None
    description: str | None = None
    enabled: bool = True

    @property
    def sql(self) -> str:
        """The model's SQL, read from the file that defines it."""
        target = PROJECT_DIR / self.path
        if not target.exists():
            raise FileNotFoundError(
                f"{self.name} has no SQL file at {target}. Every model in the "
                "example is a real file, so the manifest and the files cannot "
                "disagree."
            )
        return target.read_text(encoding="utf-8")

    @property
    def schema_file(self) -> str:
        return str(Path(self.path).parent / "_source.yml")


# ---------------------------------------------------------------------------
# The models. Each says what it is here to demonstrate.
# ---------------------------------------------------------------------------

SPECS: list[Spec] = [
    Spec(
        name="stg_shop__orders",
        path="models/staging/stg_shop/stg_shop__orders.sql",
        materialized="view",
        demonstrates="taking every column from a raw source",
        description=(
            "Orders as the shop platform exports them. Grain is one row per order. "
            "order_id is used as the natural key; total is the order value before "
            "returns."
        ),
        columns={
            "order_natural_key": "The order reference from the shop platform.",
            "customer_natural_key": "The customer who placed the order.",
            "order_total_amount": "Order value before returns.",
            "order_placed_dt": "Date the order was placed.",
        },
        depends_sources=["shop_source.orders"],
    ),
    Spec(
        name="stg_shop__customers",
        path="models/staging/stg_shop/stg_shop__customers.sql",
        materialized="view",
        demonstrates="nothing. The control",
        description=(
            "Customers as the shop platform exports them. Grain is one row per "
            "customer. joined_at is the first order date rather than the account "
            "creation date."
        ),
        columns={
            "customer_natural_key": "The customer reference from the shop platform.",
            "customer_name": "Customer name.",
            "customer_joined_dt": "Date of the customer's first order.",
        },
        depends_sources=["shop_source.customers"],
    ),
    Spec(
        name="int_shop__orders",
        path="models/integration/int_shop/int_shop__orders.sql",
        materialized="view",
        demonstrates="a working step, declared temporary in the register",
        description=(
            "Orders joined to the customer who placed them. A working step on the "
            "way to the order fact, not a table to report from. Grain is one row "
            "per order."
        ),
        columns={
            "order_natural_key": "The order reference.",
            "customer_natural_key": "The customer reference.",
            "order_placed_dt": "Date the order was placed.",
            "order_total_amount": "Order value before returns.",
        },
        depends_models=["stg_shop__orders", "stg_shop__customers"],
    ),
    Spec(
        name="wh_shop__order_fact",
        path="models/warehouse/wh_shop/wh_shop__order_fact.sql",
        materialized="table",
        demonstrates="nothing. Described, owned, keyed and tested",
        description=(
            "Warehouse order fact. Built from int_shop__orders, which joins the "
            "shop platform's orders to the customer who placed them. Carries the "
            "order value before returns; returns are held separately."
        ),
        owner="commerce",
        columns={
            "order_pk": "Surrogate key for the order.",
            "customer_fk": "The customer who placed it.",
            "order_natural_key": "The order reference from the shop platform.",
            "order_total_amount": "Order value before returns.",
            "order_placed_dt": "Date the order was placed.",
        },
        depends_models=["int_shop__orders"],
    ),
    Spec(
        name="wh_shop__customer_dim",
        path="models/warehouse/wh_shop/wh_shop__customer_dim.sql",
        materialized="table",
        demonstrates=(
            "no description, no owner, and a key checked for uniqueness but not for being populated"
        ),
        description=None,
        columns={
            "customer_pk": "Surrogate key for the customer.",
            "customer_natural_key": "The customer reference.",
            "customer_name": "Customer name.",
            "customer_joined_dt": "Date of the customer's first order.",
        },
        depends_models=["stg_shop__customers"],
    ),
    Spec(
        name="wh_shop__daily_sales_xa",
        path="models/warehouse/wh_shop/wh_shop__daily_sales_xa.sql",
        materialized="table",
        demonstrates="no tests at all, and reading staging directly",
        description=(
            "Daily order totals for the shop. Grain is one row per day. Reads "
            "staging directly rather than going through the integration layer."
        ),
        owner="commerce",
        columns={
            "daily_sales_pk": "Surrogate key for the day.",
            "daily_sales_order_count": "Orders placed that day.",
            "daily_sales_total_amount": "Order value that day.",
            "daily_sales_dt": "The day summarised.",
        },
        depends_models=["stg_shop__orders"],
    ),
    Spec(
        name="wh_shop__product_dim",
        path="models/warehouse/wh_shop/wh_shop__product_dim.sql",
        materialized="table",
        demonstrates="a dimension carrying a figure, which is how a join multiplies a total",
        description=(
            "Warehouse product dimension. Grain is one row per product. Carries "
            "the current list price."
        ),
        owner="commerce",
        columns={
            "product_pk": "Surrogate key for the product.",
            "product_natural_key": "The product reference.",
            "product_name": "Product name.",
            "product_category_name": "Category the product sits in.",
            "product_list_price_amount": "Current list price.",
        },
        depends_models=["int_shop__orders"],
    ),
    Spec(
        name="wh_shop__legacy_fact",
        path="models/warehouse/wh_shop/wh_shop__legacy_fact.sql",
        materialized="table",
        demonstrates=(
            "built with no design, read by nothing, and naming a table directly "
            "instead of going through dbt"
        ),
        description=("Kept from the previous warehouse while reports move across."),
        owner="commerce",
        columns={
            "legacy_pk": "Surrogate key.",
            "legacy_amount": "A value carried over from the previous warehouse.",
        },
        depends_models=["int_shop__orders"],
    ),
    Spec(
        name="wh_shop__forecast_fact",
        path="models/warehouse/wh_shop/wh_shop__forecast_fact.sql",
        materialized="table",
        demonstrates="built and switched off, which is not the same as not built",
        description=(
            "Demand forecast by product and week. Grain is one row per product per "
            "week. Switched off by a project variable."
        ),
        owner="commerce",
        columns={
            "forecast_pk": "Surrogate key for the product and week.",
            "product_fk": "The product forecast.",
            "forecast_units": "Units expected to sell that week.",
            "forecast_week_dt": "Monday of the week forecast.",
        },
        depends_models=["wh_shop__product_dim"],
        enabled=False,
    ),
]

#: From an installed package. Reported and never scored, because it is not this
#: team's code to change.
VENDORED = Spec(
    name="package_helper",
    path="models/staging/stg_shop/stg_shop__customers.sql",
    materialized="view",
    demonstrates="code from an installed package, reported and never scored",
    description="A helper table an installed package builds.",
)

TESTS = [
    ("wh_shop__order_fact", "unique", "order_pk", "error", {}),
    ("wh_shop__order_fact", "not_null", "order_pk", "error", {}),
    (
        "wh_shop__order_fact",
        "relationships",
        "customer_fk",
        "error",
        {"to": "ref('wh_shop__customer_dim')", "field": "customer_pk"},
    ),
    # Uniqueness only. The missing not-null is deliberate.
    ("wh_shop__customer_dim", "unique", "customer_pk", "error", {}),
    # Weak-only coverage, to prove at_least_one is never credited as key cover.
    ("wh_shop__product_dim", "at_least_one", "product_list_price_amount", "error", {}),
]

SOURCES = [
    (
        "orders",
        "Orders as the shop platform records them. One row per order.",
    ),
    (
        "customers",
        "Customers as the shop platform records them. One row per customer.",
    ),
]


def node(spec: Spec, *, package: str = PROJECT) -> dict:
    meta = {"owner": spec.owner} if spec.owner else {}
    return {
        "name": spec.name,
        "unique_id": f"model.{package}.{spec.name}",
        "resource_type": "model",
        "package_name": package,
        "original_file_path": spec.path,
        "path": spec.path,
        "schema": "analytics_warehouse",
        "database": "pj-tiny-shop-warehouse-dev",
        "alias": spec.name,
        "relation_name": (f"`pj-tiny-shop-warehouse-dev`.`analytics_warehouse`.`{spec.name}`"),
        "description": spec.description or "",
        "columns": {
            name: {"name": name, "description": text, "meta": {}, "tags": []}
            for name, text in spec.columns.items()
        },
        "tags": [],
        "meta": meta,
        "config": {
            "materialized": spec.materialized,
            "meta": meta,
            "enabled": spec.enabled,
        },
        "depends_on": {
            "nodes": [f"model.{PROJECT}.{item}" for item in spec.depends_models]
            + [f"source.{PROJECT}.{item}" for item in spec.depends_sources]
        },
        "raw_code": spec.sql,
        "patch_path": f"{PROJECT}://{spec.schema_file}",
    }


def test_node(model: str, kind: str, column: str, severity: str, kwargs: dict) -> dict:
    return {
        "name": f"{kind}_{model}_{column}",
        "unique_id": f"test.{PROJECT}.{kind}_{model}_{column}",
        "resource_type": "test",
        "package_name": PROJECT,
        "original_file_path": "models/droughty_schema.yml",
        "attached_node": f"model.{PROJECT}.{model}",
        "column_name": column,
        "config": {"severity": severity},
        "test_metadata": {"name": kind, "kwargs": kwargs},
        "depends_on": {"nodes": [f"model.{PROJECT}.{model}"]},
    }


def source_node(name: str, description: str) -> dict:
    return {
        "name": name,
        "unique_id": f"source.{PROJECT}.shop_source.{name}",
        "resource_type": "source",
        "source_name": "shop_source",
        "schema": "shop",
        "database": "pj-tiny-shop-ingestion-dev",
        "description": description,
        "columns": {},
        "relation_name": f"`pj-tiny-shop-ingestion-dev`.`shop`.`{name}`",
    }


def build_manifest() -> dict:
    enabled = [spec for spec in SPECS if spec.enabled]
    disabled = [spec for spec in SPECS if not spec.enabled]

    nodes = {item["unique_id"]: item for item in (node(spec) for spec in enabled)}
    nodes[f"model.some_package.{VENDORED.name}"] = node(VENDORED, package="some_package")
    for entry in TESTS:
        item = test_node(*entry)
        nodes[item["unique_id"]] = item

    return {
        "metadata": {
            "dbt_schema_version": SCHEMA_VERSION,
            "dbt_version": "1.10.3",
            "project_name": PROJECT,
            "generated_at": "2026-09-08T00:00:00Z",
        },
        "nodes": nodes,
        "sources": {
            item["unique_id"]: item for item in (source_node(name, text) for name, text in SOURCES)
        },
        "exposures": {},
        "metrics": {},
        "macros": {},
        "disabled": {f"model.{PROJECT}.{spec.name}": [node(spec)] for spec in disabled},
        "parent_map": {},
        "child_map": {},
    }


def main() -> None:
    target = PROJECT_DIR / "target"
    target.mkdir(parents=True, exist_ok=True)
    path = target / "manifest.json"
    path.write_text(json.dumps(build_manifest(), indent=2, sort_keys=True) + "\n")

    print(f"wrote {path.relative_to(HERE.parent.parent)}")
    print(f"{len([s for s in SPECS if s.enabled])} models, 1 disabled, 1 vendored")
    print(f"{len(TESTS)} tests, {len(SOURCES)} sources")


if __name__ == "__main__":
    main()
