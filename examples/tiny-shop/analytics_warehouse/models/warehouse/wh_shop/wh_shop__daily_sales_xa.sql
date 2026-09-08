{{
    config(
        description = """
        Daily order totals for the shop. Grain is one row per day.

        Reads `stg_shop__orders` directly rather than going through the
        integration layer, so Hunter reports lineage.staging_bypassed. It also
        carries no tests at all, so testing.no_tests_at_all fires.
        """
    )
}}

with s_orders as (

    select * from {{ ref('stg_shop__orders') }}

),

aggregated as (

    select

        -- Temporal
        order_placed_dt                     as daily_sales_dt,

        -- Metrics
        count(*)                            as daily_sales_order_count,
        sum(order_total_amount)             as daily_sales_total_amount

    from s_orders

    group by 1

),

final as (

    select

        -- Primary Key
        {{ dbt_utils.generate_surrogate_key(['daily_sales_dt']) }} as daily_sales_pk,

        -- Temporal
        daily_sales_dt,

        -- Metrics
        daily_sales_order_count,
        daily_sales_total_amount

    from aggregated

)

select * from final
