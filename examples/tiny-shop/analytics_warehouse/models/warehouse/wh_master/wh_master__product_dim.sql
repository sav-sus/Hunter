{{
    config(
        description = """
        Warehouse product dimension. Grain is one row per product.

        Deliberately carries `product_list_price_amount`, a figure on a
        dimension, so Hunter reports entity.dimension_with_measures. Summing it
        across a join multiplies it by however many rows the join returns.
        """
    )
}}

with s_orders as (

    select * from {{ ref('int_shop__orders') }}

),

final as (

    select

        -- Primary Key
        {{ dbt_utils.generate_surrogate_key(['product_natural_key']) }} as product_pk,

        -- Natural Keys
        product_natural_key,

        -- Attributes
        product_name,
        product_category_name,

        -- Metrics
        product_list_price_amount

    from s_orders

)

select * from final
