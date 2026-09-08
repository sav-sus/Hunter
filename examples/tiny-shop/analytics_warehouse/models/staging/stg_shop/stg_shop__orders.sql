{{
    config(
        description = 'Orders as the shop platform exports them. Grain is one row per order.
                    order_id is used as the natural key; total is the order value before returns.',
    )
}}

-- Deliberately takes every column from the source rather than naming them, so
-- Hunter reports structure.select_star_from_source. A column added at the
-- source arrives here without anyone deciding to take it.
with s_shop_orders as (

    select * from {{ source('shop_source', 'orders') }}

),

final as (

    select * from s_shop_orders

)

select * from final
