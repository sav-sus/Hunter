# Do the layers still agree

Three comparisons: the reporting layer against the tables underneath it, the generated schema against the project, and the designed model against what was built.

## Reporting layer against the data

| Measure | Count |
|---|---|
| Report views read | 3 |
| Explores read | 2 |
| Views matched to a table | 3 |
| Views Hunter could not match | 0 |
| Views built on their own query, not checked | 0 |


## Generated schema against the project

| Measure | Count |
|---|---|
| Tests the generated schema declares | 9 |
| Tables it covers | 3 |
| Hand-written overrides in the config | 4 |
| Tables deliberately excluded | 1 |
| Descriptions defined | 8 |
| Descriptions referenced | 7 |
| Last generated | 2026-09-08 |


## Findings

| How serious | What is wrong | Why it matters | Where |
|---|---|---|---|
| Needs attention | 1 report field in view wh_commerce__order_fact read columns wh_commerce__order_fact no longer produces: order_channel_name -> order_channel_name | These report fields are broken now. Anyone opening a report that uses them gets an error or a blank, and the cause is a column that was renamed or removed in wh_commerce__order_fact. | analytics_warehouse/lookml/base/_base.layer.lkml |
| Needs attention | 1 test declared for wh_master__customer_dim never reached the generated schema: customer_pk: not_null | Someone wrote these tests into the Droughty config on purpose and the regeneration dropped them without saying so. customers is being tested less than whoever configured it believes. | models/warehouse/wh_master/wh_master__customer_dim.sql |
| Worth fixing | wh_commerce__daily_sales_xa is not described in the generated schema | daily sales was skipped when the schema was generated, so it has neither the generated tests nor the generated descriptions the rest of the project has. | models/warehouse/wh_commerce/wh_commerce__daily_sales_xa.sql |
| Worth fixing | 3 tests in the generated schema for wh_commerce__order_fact are not in the project: customer_fk: at_least_one; order_natural_key: at_least_one; order_total_amount: at_least_one | The generated schema says these tests should exist on orders, and dbt does not have them. Either the generated file has not been applied, or something removed them by hand. | models/warehouse/wh_commerce/wh_commerce__order_fact.sql |
| Worth fixing | 1 test in the generated schema for wh_master__customer_dim are not in the project: customer_name: at_least_one | The generated schema says these tests should exist on customers, and dbt does not have them. Either the generated file has not been applied, or something removed them by hand. | models/warehouse/wh_master/wh_master__customer_dim.sql |
| Worth fixing | 2 tests in the generated schema for wh_master__product_dim are not in the project: product_pk: not_null; product_pk: unique | The generated schema says these tests should exist on products, and dbt does not have them. Either the generated file has not been applied, or something removed them by hand. | models/warehouse/wh_master/wh_master__product_dim.sql |
| Tidy up | wh_commerce__order_fact feeds 1 report view but declares no exposure | Nothing in the project records that reports depend on orders, so anyone changing it has no way to see what they would break. | models/warehouse/wh_commerce/wh_commerce__order_fact.sql |
| Tidy up | wh_commerce__daily_sales_xa feeds 1 report view but declares no exposure | Nothing in the project records that reports depend on daily sales, so anyone changing it has no way to see what they would break. | models/warehouse/wh_commerce/wh_commerce__daily_sales_xa.sql |
| Tidy up | wh_master__customer_dim feeds 1 report view but declares no exposure | Nothing in the project records that reports depend on customers, so anyone changing it has no way to see what they would break. | models/warehouse/wh_master/wh_master__customer_dim.sql |
| Tidy up | Explore shop_analytics has no caching policy | Every query against this explore goes to the warehouse, so it costs more than it needs to and is slower for whoever is waiting. | analytics_warehouse/lookml/int/int_explore_shop.explore.lkml |
| Tidy up | 1 description are defined and never used | The description file has grown past the model it describes. These entries describe columns that no longer exist, so anyone reading the file to understand the data will be misled by them. | field_descriptions |
| Tidy up | wh_master__product_dim holds 1 column in the warehouse that the design does not include: product_list_price_amount | The warehouse picture taken by Droughty shows columns on products that nobody designed, so their business meaning is not recorded. | analytics_warehouse/docs/data_model_design/physical_model.dbml |
| Tidy up | wh_commerce__order_fact holds 1 column in the warehouse that the design does not include: order_channel_name | The warehouse picture taken by Droughty shows columns on orders that nobody designed, so their business meaning is not recorded. | analytics_warehouse/docs/data_model_design/physical_model.dbml |


_Layers compared as at 2026-09-08._


---

_Generated by Rittman Hunter, from Rittman Analytics._
