{{
    config(
        description = """
        Kept from the previous warehouse while reports move across.

        Three deliberate problems. It appears on no design, so Hunter reports
        alignment.built_off_plan. Nothing reads it, so lineage.dead_model fires.
        And it names a table directly instead of going through dbt, so
        structure.hardcoded_reference fires and the dependency is invisible to
        the lineage graph.
        """
    )
}}

with s_legacy as (

    select * from `warehouse`.`old_shop`.`legacy_orders`

),

final as (

    select

        -- Primary Key
        {{ dbt_utils.generate_surrogate_key(['legacy_natural_key']) }} as legacy_pk,

        -- Metrics
        legacy_amount

    from s_legacy

)

select * from final
