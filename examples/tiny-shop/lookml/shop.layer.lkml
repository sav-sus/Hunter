view: wh_shop__order_fact {
  sql_table_name: wh_shop__order_fact ;;

  dimension: order_pk {
    primary_key: yes
    hidden: yes
    type: string
    sql: ${TABLE}.order_pk ;;
    description: "Surrogate key for the order."
  }
  dimension: customer_fk {
    hidden: yes
    type: string
    sql: ${TABLE}.customer_fk ;;
    description: "The customer who placed it."
  }
  dimension_group: order_placed {
    type: time
    timeframes: [date, week, month]
    sql: ${TABLE}.order_placed_dt ;;
    description: "When the order was placed."
  }
  dimension: order_channel_name {
    type: string
    sql: ${TABLE}.order_channel_name ;;
    description: "The channel the order came through."
  }
}

view: +wh_shop__order_fact {
  measure: order_count {
    type: count
    description: "Orders placed."
  }
  measure: order_total_amount {
    type: sum
    sql: ${TABLE}.order_total_amount ;;
    description: "Order value before returns."
  }
}

view: wh_shop__customer_dim {
  sql_table_name: wh_shop__customer_dim ;;

  dimension: customer_pk {
    primary_key: yes
    hidden: yes
    type: string
    sql: ${TABLE}.customer_pk ;;
    description: "Surrogate key for the customer."
  }
  dimension: customer_name {
    type: string
    sql: ${TABLE}.customer_name ;;
    description: "Customer name."
  }
}

explore: shop_orders {
  view_name: wh_shop__order_fact
  label: "Shop orders"
  description: "Orders, with the customer who placed them."

  join: wh_shop__customer_dim {
    relationship: many_to_one
    type: left_outer
    sql_on: ${wh_shop__order_fact.customer_fk} = ${wh_shop__customer_dim.customer_pk} ;;
  }
}
