include: "/analytics_warehouse/lookml/base/_base.layer.lkml"

# ----------------------------------------------------------- staging dimensions for order fact

view: +wh_shop__order_fact {
  view_label: "Order"
  sql_table_name: {{ _user_attributes['gcp_project_id'] }}.{{ _user_attributes['gcp_dataset_name'] }}.`wh_shop__order_fact` ;;

  # Identifiers & Keys
  dimension: order_natural_key {
    label: "Order Reference"
    group_label: "      Identifiers & Keys"
    hidden: no
  }

  # Order Attributes
  dimension: order_channel_name {
    label: "Order Channel"
    group_label: "     Order Attributes"
  }

  # Metrics
  dimension: order_total_amount {
    label: "Order Value"
    group_label: "    Metrics"
    value_format_name: decimal_2
  }

  # Dates
  dimension_group: order_placed {
    label: "Order Placed"
    group_label: "   Dates"
  }
}

# ----------------------------------------------------------- staging dimensions for customer dim

view: +wh_shop__customer_dim {
  view_label: "Customer"
  sql_table_name: {{ _user_attributes['gcp_project_id'] }}.{{ _user_attributes['gcp_dataset_name'] }}.`wh_shop__customer_dim` ;;

  # Identifiers & Keys
  dimension: customer_natural_key {
    label: "Customer Reference"
    group_label: "      Identifiers & Keys"
    hidden: no
  }

  # Personal Attributes
  dimension: customer_name {
    label: "Customer Name"
    group_label: "     Personal Attributes"
  }

  # Dates
  dimension_group: customer_joined {
    label: "Customer Joined"
    group_label: "   Dates"
  }
}

# ----------------------------------------------------------- staging dimensions for daily sales

view: +wh_shop__daily_sales_xa {
  view_label: "Daily Sales"
  sql_table_name: {{ _user_attributes['gcp_project_id'] }}.{{ _user_attributes['gcp_dataset_name'] }}.`wh_shop__daily_sales_xa` ;;

  # Metrics
  dimension: daily_sales_order_count {
    label: "Orders"
    group_label: "    Metrics"
  }

  dimension: daily_sales_total_amount {
    label: "Order Value"
    group_label: "    Metrics"
    value_format_name: decimal_2
  }

  # Dates
  dimension_group: daily_sales {
    label: "Day"
    group_label: "   Dates"
  }
}
