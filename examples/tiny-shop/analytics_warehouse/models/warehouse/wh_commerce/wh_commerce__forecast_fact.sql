{{
    config(
        enabled = var('include_forecast_models', false),
        description = """
        Demand forecast by product and week. Grain is one row per product per week.

        Switched off by a project variable, so it sits in the manifest's disabled
        section rather than its nodes. Hunter reports it as built and switched
        off, which is not the same as not built.
        """
    )
}}

with s_products as (

    select * from {{ ref('wh_master__product_dim') }}

),

final as (

    select

        -- Primary Key
        {{ dbt_utils.generate_surrogate_key(['product_pk', 'forecast_week_dt']) }} as forecast_pk,

        -- Foreign Keys
        product_pk                          as product_fk,

        -- Temporal
        forecast_week_dt,

        -- Metrics
        forecast_units

    from s_products

)

select * from final
