#!/usr/bin/env python3
"""Build the tiny-project fixture.

Eight models with deliberate flaws, one per finding class that matters, plus a
design, a business model, a reporting layer and generated schema output. Small
enough to read in one sitting and check by hand.

The manifest is generated rather than hand-typed so the intent stays visible:
each model below says what it is meant to demonstrate. Run this script to
rewrite it after changing anything here.

Names are invented and resemble no client's.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent
PROJECT = "tiny_shop"

SCHEMA = "https://schemas.getdbt.com/dbt/manifest/v12.json"


def column(name: str, description: str | None = None) -> dict:
    return {"name": name, "description": description or "", "meta": {}, "tags": []}


def model(
    name: str,
    *,
    path: str,
    materialized: str,
    description: str = "",
    columns: list[dict] | None = None,
    depends_models: list[str] | None = None,
    depends_sources: list[str] | None = None,
    raw_code: str = "select 1\n",
    meta: dict | None = None,
    schema_file: str | None = None,
) -> dict:
    return {
        "name": name,
        "unique_id": f"model.{PROJECT}.{name}",
        "resource_type": "model",
        "package_name": PROJECT,
        "original_file_path": path,
        "path": path,
        "schema": "tiny_shop",
        "database": "warehouse",
        "alias": name,
        "relation_name": f"`warehouse`.`tiny_shop`.`{name}`",
        "description": description,
        "columns": {item["name"]: item for item in (columns or [])},
        "tags": [],
        "meta": meta or {},
        "config": {"materialized": materialized, "meta": meta or {}},
        "depends_on": {
            "nodes": [f"model.{PROJECT}.{item}" for item in (depends_models or [])]
            + [f"source.{PROJECT}.{item}" for item in (depends_sources or [])]
        },
        "raw_code": raw_code,
        "patch_path": f"{PROJECT}://{schema_file}" if schema_file else None,
    }


def test_node(
    model_name: str, kind: str, column_name: str | None = None, *, severity: str = "error", **kwargs
) -> dict:
    suffix = column_name or "model"
    return {
        "name": f"{kind}_{model_name}_{suffix}",
        "unique_id": f"test.{PROJECT}.{kind}_{model_name}_{suffix}",
        "resource_type": "test",
        "package_name": PROJECT,
        "original_file_path": "models/schema.yml",
        "attached_node": f"model.{PROJECT}.{model_name}",
        "column_name": column_name,
        "config": {"severity": severity},
        "test_metadata": {"name": kind, "kwargs": kwargs},
        "depends_on": {"nodes": [f"model.{PROJECT}.{model_name}"]},
    }


# --- The eight models, each demonstrating something -------------------------

MODELS = [
    # 1. Staging, clean apart from taking every column from the source. That is
    #    ordinary style and scores low, so it proves the rule is a nudge.
    model(
        "stg_shop__orders",
        path="models/staging/stg_shop/stg_shop__orders.sql",
        materialized="view",
        columns=[
            column("order_natural_key", "The order reference from the shop system."),
            column("order_placed_dt", "Date the order was placed."),
            column("order_total_amount", "Order value before returns."),
            column("customer_natural_key", "The customer reference."),
        ],
        depends_sources=["shop.orders"],
        raw_code="select * from {{ source('shop', 'orders') }}\n",
        schema_file="models/staging/stg_shop/schema.yml",
    ),
    # 2. Staging, entirely clean.
    model(
        "stg_shop__customers",
        path="models/staging/stg_shop/stg_shop__customers.sql",
        materialized="view",
        columns=[
            column("customer_natural_key", "The customer reference from the shop."),
            column("customer_name", "Customer name."),
            column("customer_joined_dt", "Date the customer first ordered."),
        ],
        depends_sources=["shop.customers"],
        raw_code=(
            "select\n"
            "  customer_id as customer_natural_key,\n"
            "  name as customer_name,\n"
            "  joined_at as customer_joined_dt\n"
            "from {{ source('shop', 'customers') }}\n"
        ),
        schema_file="models/staging/stg_shop/schema.yml",
    ),
    # 3. Integration, clean.
    model(
        "int_shop__orders",
        path="models/integration/int_shop/int_shop__orders.sql",
        materialized="view",
        columns=[
            column("order_natural_key", "The order reference."),
            column("customer_natural_key", "The customer reference."),
            column("order_placed_dt", "Date the order was placed."),
            column("order_total_amount", "Order value before returns."),
        ],
        depends_models=["stg_shop__orders", "stg_shop__customers"],
        raw_code=(
            "with orders as (\n"
            "  select * from {{ ref('stg_shop__orders') }}\n"
            "),\n"
            "customers as (\n"
            "  select * from {{ ref('stg_shop__customers') }}\n"
            ")\n"
            "select\n"
            "  orders.order_natural_key,\n"
            "  orders.customer_natural_key,\n"
            "  orders.order_placed_dt,\n"
            "  orders.order_total_amount\n"
            "from orders\n"
            "left join customers on customers.customer_natural_key "
            "= orders.customer_natural_key\n"
        ),
        schema_file="models/integration/int_shop/schema.yml",
    ),
    # 4. Warehouse fact, fully correct. The control.
    model(
        "wh_shop__order_fact",
        path="models/warehouse/wh_shop/wh_shop__order_fact.sql",
        materialized="table",
        description="One row per order placed in the shop, owned by the commerce team.",
        meta={"owner": "commerce"},
        columns=[
            column("order_pk", "Surrogate key for the order."),
            column("customer_fk", "The customer who placed it."),
            column("order_natural_key", "The order reference from the shop system."),
            column("order_placed_dt", "Date the order was placed."),
            column("order_total_amount", "Order value before returns."),
        ],
        depends_models=["int_shop__orders"],
        raw_code="select 1 as order_pk from {{ ref('int_shop__orders') }}\n",
        schema_file="models/warehouse/wh_shop/schema.yml",
    ),
    # 5. Warehouse dimension with no description, no owner, and a key that is
    #    checked for uniqueness but not for being populated.
    model(
        "wh_shop__customer_dim",
        path="models/warehouse/wh_shop/wh_shop__customer_dim.sql",
        materialized="table",
        columns=[
            column("customer_pk", "Surrogate key for the customer."),
            column("customer_natural_key", "The customer reference."),
            column("customer_name", "Customer name."),
            column("customer_joined_dt", "Date the customer first ordered."),
        ],
        depends_models=["stg_shop__customers"],
        raw_code="select 1 as customer_pk from {{ ref('stg_shop__customers') }}\n",
        schema_file="models/warehouse/wh_shop/schema.yml",
    ),
    # 6. Warehouse aggregate with no tests at all, reading staging directly and
    #    so skipping integration.
    model(
        "wh_shop__daily_sales_xa",
        path="models/warehouse/wh_shop/wh_shop__daily_sales_xa.sql",
        materialized="table",
        description="One row per day, holding order totals for the shop.",
        meta={"owner": "commerce"},
        columns=[
            column("daily_sales_pk", "Surrogate key for the day."),
            column("daily_sales_dt", "The day summarised."),
            column("daily_sales_order_count", "Orders placed that day."),
            column("daily_sales_total_amount", "Order value that day."),
        ],
        depends_models=["stg_shop__orders"],
        raw_code="select 1 as daily_sales_pk from {{ ref('stg_shop__orders') }}\n",
        schema_file="models/warehouse/wh_shop/schema.yml",
    ),
    # 7. Warehouse fact built without a design, with no tests, that nothing
    #    reads. Off-plan and dead at once.
    model(
        "wh_shop__legacy_fact",
        path="models/warehouse/wh_shop/wh_shop__legacy_fact.sql",
        materialized="table",
        description="Kept from the previous warehouse while reports move across.",
        meta={"owner": "commerce"},
        columns=[
            column("legacy_pk", "Surrogate key."),
            column("legacy_amount", "A value carried over."),
        ],
        depends_models=["int_shop__orders"],
        raw_code=("select 1 as legacy_pk\nfrom `warehouse`.`old_shop`.`legacy_orders`\n"),
        schema_file="models/warehouse/wh_shop/schema.yml",
    ),
    # 8. Warehouse dimension carrying a figure, which is how a join multiplies
    #    a total without anyone noticing.
    model(
        "wh_shop__product_dim",
        path="models/warehouse/wh_shop/wh_shop__product_dim.sql",
        materialized="table",
        description="One row per product sold in the shop, owned by the commerce team.",
        meta={"owner": "commerce"},
        columns=[
            column("product_pk", "Surrogate key for the product."),
            column("product_natural_key", "The product reference."),
            column("product_name", "Product name."),
            column("product_category_name", "Category the product sits in."),
            column("product_list_price_amount", "Current list price."),
        ],
        depends_models=["int_shop__orders"],
        raw_code="select 1 as product_pk from {{ ref('int_shop__orders') }}\n",
        schema_file="models/warehouse/wh_shop/schema.yml",
    ),
]

DISABLED = [
    # Built and switched off, so the reconciliation must not call it unstarted.
    model(
        "wh_shop__forecast_fact",
        path="models/warehouse/wh_shop/wh_shop__forecast_fact.sql",
        materialized="table",
        description="One row per product per week, holding the demand forecast.",
        meta={"owner": "commerce"},
        columns=[
            column("forecast_pk", "Surrogate key."),
            column("product_fk", "The product forecast."),
            column("forecast_week_dt", "Week forecast."),
            column("forecast_units", "Units expected."),
        ],
        depends_models=["wh_shop__product_dim"],
        schema_file="models/warehouse/wh_shop/schema.yml",
    )
]

VENDORED = [
    # From an installed package, so reported and never scored.
    {
        **model(
            "package_helper",
            path="models/package_helper.sql",
            materialized="view",
        ),
        "package_name": "some_package",
        "unique_id": "model.some_package.package_helper",
    }
]

TESTS = [
    test_node("wh_shop__order_fact", "unique", "order_pk"),
    test_node("wh_shop__order_fact", "not_null", "order_pk"),
    test_node(
        "wh_shop__order_fact",
        "relationships",
        "customer_fk",
        to="ref('wh_shop__customer_dim')",
        field="customer_pk",
    ),
    # Uniqueness only: the not-null gap is deliberate.
    test_node("wh_shop__customer_dim", "unique", "customer_pk"),
    # Weak-only coverage: proves at_least_one is never credited as key cover.
    test_node("wh_shop__product_dim", "at_least_one", "product_list_price_amount"),
]

SOURCES = [
    {
        "name": "orders",
        "unique_id": f"source.{PROJECT}.shop.orders",
        "resource_type": "source",
        "source_name": "shop",
        "schema": "raw_shop",
        "database": "warehouse",
        "description": "Orders as the shop system records them.",
        "columns": {},
        "relation_name": "`warehouse`.`raw_shop`.`orders`",
    },
    {
        "name": "customers",
        "unique_id": f"source.{PROJECT}.shop.customers",
        "resource_type": "source",
        "source_name": "shop",
        "schema": "raw_shop",
        "database": "warehouse",
        "description": "Customers as the shop system records them.",
        "columns": {},
        "relation_name": "`warehouse`.`raw_shop`.`customers`",
    },
]


def build_manifest() -> dict:
    nodes = {item["unique_id"]: item for item in MODELS + VENDORED + TESTS}
    disabled = {item["unique_id"]: [item] for item in DISABLED}
    return {
        "metadata": {
            "dbt_schema_version": SCHEMA,
            "dbt_version": "1.10.3",
            "project_name": PROJECT,
            "generated_at": "2026-09-08T00:00:00Z",
        },
        "nodes": nodes,
        "sources": {item["unique_id"]: item for item in SOURCES},
        "exposures": {},
        "metrics": {},
        "macros": {},
        "disabled": disabled,
        "parent_map": {},
        "child_map": {},
    }


def main() -> None:
    target = HERE / "target"
    target.mkdir(parents=True, exist_ok=True)
    path = target / "manifest.json"
    path.write_text(json.dumps(build_manifest(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
