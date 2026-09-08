# Everything that needs doing

34 open findings, 1 suggestions Hunter is not confident enough to count, and 1 silenced with a recorded reason.

## By how serious it is

| How serious | Count |
|---|---|
| Needs attention | 9 |
| Worth fixing | 16 |
| Tidy up | 7 |
| For information | 2 |


## By area of concern

### Are the tables the shape they claim

| How serious | What is wrong | Why it matters | Where |
|---|---|---|---|
| Worth fixing | wh_shop__product_dim is named as a dimension but carries 1 numeric column | products is named as a lookup table but holds figures. Anyone joining it and summing those figures will multiply them by however many rows the join returns. Columns: product_list_price_amount. | models/warehouse/wh_shop/wh_shop__product_dim.sql |


### Do the reports still match the data

| How serious | What is wrong | Why it matters | Where |
|---|---|---|---|
| Needs attention | 1 report field in view wh_shop__order_fact read columns wh_shop__order_fact no longer produces: order_channel_name -> order_channel_name | These report fields are broken now. Anyone opening a report that uses them gets an error or a blank, and the cause is a column that was renamed or removed in wh_shop__order_fact. | lookml/shop.layer.lkml |
| Tidy up | wh_shop__order_fact feeds 1 report view but declares no exposure | Nothing in the project records that reports depend on orders, so anyone changing it has no way to see what they would break. | models/warehouse/wh_shop/wh_shop__order_fact.sql |
| Tidy up | wh_shop__customer_dim feeds 1 report view but declares no exposure | Nothing in the project records that reports depend on customers, so anyone changing it has no way to see what they would break. | models/warehouse/wh_shop/wh_shop__customer_dim.sql |


### Does what was built match the design

| How serious | What is wrong | Why it matters | Where |
|---|---|---|---|
| Needs attention | wh_shop__daily_sales_xa is missing 1 column that the design specifies: daily_sales_returned_amount | daily sales was designed to hold these columns and does not. Anything that expected them, including a report built from the design, has nothing to read. | models/warehouse/wh_shop/wh_shop__daily_sales_xa.sql |
| Tidy up | wh_shop__product_dim has 1 column the design does not include: product_list_price_amount | products holds columns nobody designed, so they are undocumented and their business meaning is not recorded anywhere. | models/warehouse/wh_shop/wh_shop__product_dim.sql |


### How the code is written

| How serious | What is wrong | Why it matters | Where |
|---|---|---|---|
| Needs attention | wh_shop__legacy_fact names the table '`warehouse`' directly on line 2 | Because legacy does not go through dbt to reach this table, the dependency is invisible: it does not appear in the lineage, it is not built in the right order, and nothing warns you if the table it points at changes. | models/warehouse/wh_shop/wh_shop__legacy_fact.sql:2 |
| Tidy up | stg_shop__orders selects every column from a raw source on line 1 | A column added at the source appears in stg_shop__orders without anyone deciding to take it, and a renamed one disappears. Reports built on it change shape with no change made here. | models/staging/stg_shop/stg_shop__orders.sql:1 |


### How the layers fit together

| How serious | What is wrong | Why it matters | Where |
|---|---|---|---|
| Worth fixing | wh_shop__customer_dim skips the integration layer to read stg_shop__customers | customers reaches back past the layer that normally cleans and checks this data, so those checks do not apply to what it reads. | models/warehouse/wh_shop/wh_shop__customer_dim.sql |
| Worth fixing | wh_shop__daily_sales_xa skips the integration layer to read stg_shop__orders | daily sales reaches back past the layer that normally cleans and checks this data, so those checks do not apply to what it reads. | models/warehouse/wh_shop/wh_shop__daily_sales_xa.sql |


### Reporting setup

| How serious | What is wrong | Why it matters | Where |
|---|---|---|---|
| Tidy up | Explore shop_orders has no caching policy | Every query against this explore goes to the warehouse, so it costs more than it needs to and is slower for whoever is waiting. | lookml/shop.layer.lkml |


### What is documented

| How serious | What is wrong | Why it matters | Where |
|---|---|---|---|
| Worth fixing | wh_shop__daily_sales_xa is not described in the generated schema | daily sales was skipped when the schema was generated, so it has neither the generated tests nor the generated descriptions the rest of the project has. | models/warehouse/wh_shop/wh_shop__daily_sales_xa.sql |
| Worth fixing | wh_shop__legacy_fact is not described in the generated schema | legacy was skipped when the schema was generated, so it has neither the generated tests nor the generated descriptions the rest of the project has. | models/warehouse/wh_shop/wh_shop__legacy_fact.sql |
| Tidy up | 1 description are defined and never used | The description file has grown past the model it describes. These entries describe columns that no longer exist, so anyone reading the file to understand the data will be misled by them. | field_descriptions |


### What is not used

| How serious | What is wrong | Why it matters | Where |
|---|---|---|---|
| Worth fixing | wh_shop__daily_sales_xa is built and stored but nothing reads it | daily sales is rebuilt on every run and no model, report or dashboard uses the result. It costs money and delivers nothing until something consumes it. | models/warehouse/wh_shop/wh_shop__daily_sales_xa.sql |
| Worth fixing | wh_shop__legacy_fact is built and stored but nothing reads it | legacy is rebuilt on every run and no model, report or dashboard uses the result. It costs money and delivers nothing until something consumes it. | models/warehouse/wh_shop/wh_shop__legacy_fact.sql |
| Worth fixing | wh_shop__product_dim is built and stored but nothing reads it | products is rebuilt on every run and no model, report or dashboard uses the result. It costs money and delivers nothing until something consumes it. | models/warehouse/wh_shop/wh_shop__product_dim.sql |


### What is still to come

| How serious | What is wrong | Why it matters | Where |
|---|---|---|---|
| For information | 1 business entity on the business model have not been designed yet | These are agreed with the business as things the warehouse should hold, and no design exists for them yet. This is the design backlog, not a list of faults. Examples: returns. | conceptual model |


### What is tested

| How serious | What is wrong | Why it matters | Where |
|---|---|---|---|
| Needs attention | 1 test declared for wh_shop__customer_dim never reached the generated schema: customer_pk: not_null | Someone wrote these tests into the Droughty config on purpose and the regeneration dropped them without saying so. customers is being tested less than whoever configured it believes. | models/warehouse/wh_shop/wh_shop__customer_dim.sql |
| Needs attention | Nothing tests that customer_pk is always populated on wh_shop__customer_dim | Rows with no key can appear in customers. They drop out of joins silently, so figures come out low with no error to explain why. | models/warehouse/wh_shop/wh_shop__customer_dim.sql |
| Needs attention | Nothing tests that product_pk is unique on wh_shop__product_dim | Nothing checks that products holds one row per one row per product. it holds last year's categories too. If duplicates appear, every total built from it is overstated and nobody is told. nothing downstream depends on it. | models/warehouse/wh_shop/wh_shop__product_dim.sql |
| Needs attention | wh_shop__daily_sales_xa has no tests of any kind | Nothing at all checks daily sales. Any problem in it reaches whoever reads the numbers before anyone who could fix it, and nothing downstream depends on it. | models/warehouse/wh_shop/wh_shop__daily_sales_xa.sql |
| Needs attention | wh_shop__legacy_fact has no tests of any kind | Nothing at all checks legacy. Any problem in it reaches whoever reads the numbers before anyone who could fix it, and nothing downstream depends on it. | models/warehouse/wh_shop/wh_shop__legacy_fact.sql |
| Needs attention | Nothing tests that product_pk is always populated on wh_shop__product_dim | Rows with no key can appear in products. They drop out of joins silently, so figures come out low with no error to explain why. | models/warehouse/wh_shop/wh_shop__product_dim.sql |
| Worth fixing | wh_shop__product_dim has 1 test but none of them prove a key | The tests on products check that columns are not entirely empty. None of them check that it has one row per thing, or that its references resolve. | models/warehouse/wh_shop/wh_shop__product_dim.sql |
| Worth fixing | 2 tests in the generated schema for wh_shop__product_dim are not in the project: product_pk: not_null; product_pk: unique | The generated schema says these tests should exist on products, and dbt does not have them. Either the generated file has not been applied, or something removed them by hand. | models/warehouse/wh_shop/wh_shop__product_dim.sql |
| Worth fixing | 1 test in the generated schema for wh_shop__order_fact are not in the project: customer_fk: at_least_one | The generated schema says these tests should exist on orders, and dbt does not have them. Either the generated file has not been applied, or something removed them by hand. | models/warehouse/wh_shop/wh_shop__order_fact.sql |


### What one row means

| How serious | What is wrong | Why it matters | Where |
|---|---|---|---|
| Worth fixing | The declared grain of wh_shop__product_dim is not tested | The design says products holds one row per product. it holds last year's categories too, and nothing checks that it does. If the grain is wrong, figures double-count with no test to catch it. | models/warehouse/wh_shop/wh_shop__product_dim.sql |


### What was designed against what exists

| How serious | What is wrong | Why it matters | Where |
|---|---|---|---|
| Worth fixing | wh_shop__legacy_fact is built but was never designed | legacy exists in production and appears on no design, so nothing records what it is for, what one row means or who owns it. If it should be there, add it to the design or record an approval in the register. | wh_shop__legacy_fact |
| Worth fixing | wh_shop__supplier_dim is designed but no model builds it | suppliers was designed and agreed, and nothing in the repository produces it yet. It is on the plan and not started. | models/_model/shop.dbml |
| Tidy up | wh_shop__forecast_fact is built but switched off | The code for forecasts exists and is not running, so nothing is being produced from it. Either it is waiting to be turned on, or it was left behind and should be removed. | models/_model/shop.dbml |


### What was not checked

| How serious | What is wrong | Why it matters | Where |
|---|---|---|---|
| For information | Column types were not available, so designed and built types were not compared | Hunter could not check whether columns are built with the types the design specifies, because the project has no catalogue file. Running 'dbt docs generate' alongside the build would let this run. Nothing here means the types are wrong; it means they were not checked. | project |


### Where the numbers are worked out

| How serious | What is wrong | Why it matters | Where |
|---|---|---|---|
| Worth fixing | wh_shop__order_fact defines 1 figure that wh_shop__order_fact already computes: order_total_amount | The same figure is worked out in two places. When one is changed and the other is not, two reports show different numbers for the same thing and nobody can tell which is right. | lookml/shop.layer.lkml |


### Who owns what

| How serious | What is wrong | Why it matters | Where |
|---|---|---|---|
| Worth fixing | wh_shop__customer_dim names no owner | There is nobody to ask about customers and nobody to route a problem with it to. It is a persistent table, and 2 report fields depend on it. | models/warehouse/wh_shop/wh_shop__customer_dim.sql |


## Suggestions, not counted

Hunter is not confident enough about these to let them affect the score. They are worth a human look rather than a change.

| How serious | What is wrong | Why it matters | Where |
|---|---|---|---|
| Tidy up (suggestion) | wh_shop__customer_dim is named as a dimension, and its shape neither clearly agrees nor disagrees | Hunter could not tell from its columns whether customers really is a dimension. Worth a human look rather than a change. Evidence: 0 foreign keys, 0 columns to add up, 1 descriptive column, a date grain (judged from names, since column types were not available). | models/warehouse/wh_shop/wh_shop__customer_dim.sql |


## Silenced, with a reason

These are real findings that somebody has agreed to leave for now. They come back automatically on their expiry date.

| What is wrong | Where | Reason recorded | Comes back on |
|---|---|---|---|
| wh_shop__customer_dim has no description | wh_shop__customer_dim | the description is being written as part of the customer rework | 2027-01-31 |



_Findings computed as at 2026-09-08._


---

_Generated by Rittman Hunter, from Rittman Analytics._
