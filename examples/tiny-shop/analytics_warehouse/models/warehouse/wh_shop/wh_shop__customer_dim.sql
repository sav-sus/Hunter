-- Deliberately carries no config block, so Hunter reports
-- documentation.model_description_missing and documentation.owner_missing.
-- Its key is tested for uniqueness but not for being populated, so
-- testing.key_not_null_missing fires too.

with s_customers as (

    select * from {{ ref('stg_shop__customers') }}

),

final as (

    select

        -- Primary Key
        {{ dbt_utils.generate_surrogate_key(['customer_natural_key']) }} as customer_pk,

        -- Natural Keys
        customer_natural_key,

        -- Attributes
        customer_name,

        -- Temporal
        customer_joined_dt

    from s_customers

)

select * from final
