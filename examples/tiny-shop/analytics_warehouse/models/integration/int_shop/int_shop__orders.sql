{{
    config(
        description = 'Orders joined to the customer who placed them. A working step on the way to
                    the order fact, not a table to report from. Grain is one row per order.',
    )
}}

with s_orders as (

    select * from {{ ref('stg_shop__orders') }}

),

s_customers as (

    select * from {{ ref('stg_shop__customers') }}

),

joined as (

    select

        -- Keys
        s_orders.order_natural_key,
        s_orders.customer_natural_key,

        -- Temporal
        s_orders.order_placed_dt,

        -- Metrics
        s_orders.order_total_amount

    from s_orders

    left join s_customers
        on s_customers.customer_natural_key = s_orders.customer_natural_key

),

final as (

    select * from joined

)

select * from final
