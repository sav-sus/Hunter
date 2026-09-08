{{
    config(
        description = 'Customers as the shop platform exports them. Grain is one row per customer.
                    joined_at is the first order date rather than the account creation date.',
    )
}}

with s_shop_customers as (

    select * from {{ source('shop_source', 'customers') }}

),

rename_and_cast as (

    select

        -- Keys
        cast(customer_id as {{ dbt.type_string() }})   as customer_natural_key,

        -- Attributes
        cast(name as {{ dbt.type_string() }})          as customer_name,

        -- Temporal
        cast(joined_at as {{ ra_type_date() }})        as customer_joined_dt

    from s_shop_customers

),

final as (

    select * from rename_and_cast

)

select * from final
