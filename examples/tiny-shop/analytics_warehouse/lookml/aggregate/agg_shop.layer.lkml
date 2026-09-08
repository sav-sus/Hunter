include: "/analytics_warehouse/lookml/base/_aggregate.layer.lkml"

view: +wh_shop__order_fact {
# ----------------------------------- Hidden metrics
  measure: count_of_order_pk { hidden: yes }

# ----------------------------------- Published metrics
  measure: order_count {
    label: "Orders"
    description: "Orders placed."
    type: count_distinct
    sql: ${order_pk} ;;
    drill_fields: [order_natural_key, order_placed_date, order_total_amount]
  }

  measure: order_value {
    label: "Order Value"
    description: "Order value before returns."
    type: sum
    sql: ${order_total_amount} ;;
    value_format_name: decimal_2
  }

  measure: average_order_value {
    label: "Average Order Value"
    description: "Order value before returns, divided by orders placed."
    type: number
    sql: safe_divide(${order_value}, ${order_count}) ;;
    value_format_name: decimal_2
  }
}

view: +wh_shop__customer_dim {
# ----------------------------------- Hidden metrics
  measure: count_of_customer_pk { hidden: yes }

# ----------------------------------- Published metrics
  measure: customer_count {
    label: "Customers"
    description: "Customers who have ordered at least once."
    type: count_distinct
    sql: ${customer_pk} ;;
  }
}

view: +wh_shop__daily_sales_xa {
# ----------------------------------- Hidden metrics
  measure: count_of_daily_sales_pk { hidden: yes }
  measure: sum_of_daily_sales_order_count { hidden: yes }

# ----------------------------------- Published metrics
  #
  # Deliberately duplicates a figure the warehouse already computes:
  # daily_sales_total_amount is a column, and this measure sums it under the
  # same name. Hunter reports crosslayer.duplicate_measure, because when one is
  # changed and the other is not, two reports show different numbers.
  measure: daily_sales_total_amount {
    label: "Daily Order Value"
    type: sum
    sql: ${TABLE}.daily_sales_total_amount ;;
    value_format_name: decimal_2
  }
}
