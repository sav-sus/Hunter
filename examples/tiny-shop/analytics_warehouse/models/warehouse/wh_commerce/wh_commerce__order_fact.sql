{{
    config(
        description = """
        Warehouse order fact. Built from `int_shop__orders`, which joins the shop
        platform's orders to the customer who placed them. Carries the order value
        before returns; returns are held separately.
        """
    )
}}

-- The control. Described, owned, keyed and tested, so Hunter reports nothing
-- against it.
with s_orders as (

    select * from {{ ref('int_shop__orders') }}

),

final as (

    select

        -- Primary Key
        {{ dbt_utils.generate_surrogate_key(['order_natural_key']) }}   as order_pk,

        -- Foreign Keys
        {{ dbt_utils.generate_surrogate_key(['customer_natural_key']) }} as customer_fk,

        -- Natural Keys
        order_natural_key,

        -- Metrics
        order_total_amount,

        -- Temporal
        order_placed_dt

    from s_orders

)

select * from final
