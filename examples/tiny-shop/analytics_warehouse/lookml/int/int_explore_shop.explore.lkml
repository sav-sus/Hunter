include: "../base/_base.layer.lkml"
include: "../base/_aggregate.layer.lkml"
include: "../staging/*"
include: "../aggregate/*"

# ========================================================================================================
# Shop Analytics Explore
# ========================================================================================================
# Orders, the customer who placed them, and daily totals.

explore: shop_analytics {
  label: "  Shop Orders"
  group_label: "       Shop Explores"
  description: "Analyse orders at a transaction level, with the customer who placed them.
  Use this when you need order-level detail rather than a daily total."
  tags: [
    "entity:shop",
    "domain:shop",
    "contains:orders",
    "contains:customers",
    "analytics_warehouse",
  ]
  view_name: wh_shop__order_fact
  view_label: "Order"

  # No persist_with, so Hunter reports crosslayer.explore_no_caching_policy.
  # Every query against this explore goes to the warehouse.

  join: wh_shop__customer_dim {
    view_label: "Customer"
    relationship: many_to_one
    type: left_outer
    sql_on: ${wh_shop__order_fact.customer_fk} = ${wh_shop__customer_dim.customer_pk} ;;
  }
}

# ========================================================================================================
# Daily Sales Explore
# ========================================================================================================

explore: shop_daily_sales {
  label: "  Shop Daily Sales"
  group_label: "       Shop Explores"
  description: "Daily order totals. Use this for trend reporting rather than order-level detail."
  persist_with: daily_datagroup
  tags: [
    "entity:shop",
    "domain:shop",
    "contains:daily_sales",
    "analytics_warehouse",
  ]
  view_name: wh_shop__daily_sales_xa
  view_label: "Daily Sales"
}
