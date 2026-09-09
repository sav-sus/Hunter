# The score, broken down

# 88.2 / 100

!!! abstract "Well maintained. Safe to build on"
    Grade A.

!!! warning "Some areas were not measured"
    1 of 8 areas could not be measured with the information available. Their weight has been shared across the rest, so the score is still out of 100. They are not counted as passing.

## Each area

| Area | Score | Grade | Share of the total | Findings |
|---|---|---|---|---|
| What is checked automatically | 76.9 | B | 19.355% | 7 |
| Does what was built match the design | 95.6 | A | 16.129% | 9 |
| How the tables fit together | 88.1 | A | 13.978% | 4 |
| What is written down | 96.1 | A | 13.978% | 3 |
| Do the reports still match the data | 72.2 | B | 13.978% | 10 |
| Are the house rules followed | 98.5 | A | 13.978% | 3 |
| Are the tables the shape they claim | 96.4 | A | 8.602% | 2 |
| What it costs to run | not measured | - | - | 0 |


### What is checked automatically

Whether anything would notice if the data went wrong. A test that only checks a column is not empty does not count as checking a key.

Scored **76.9**, grade B. 16.9 of 64.58 possible points were lost across 7 findings.

### Does what was built match the design

Whether the tables that exist are the tables that were designed, with the columns, keys and relationships the design specifies.

Scored **95.6**, grade A. 3.59 of 76.21 possible points were lost across 9 findings.

### How the tables fit together

Whether the tables depend on each other in ways that are safe to change, and whether anything is being built that nobody reads.

Scored **88.1**, grade A. 7.25 of 73.45 possible points were lost across 4 findings.

### What is written down

Whether someone new could tell what each table is for, what one row of it means, and who to ask about it.

Scored **96.1**, grade A. 2.17 of 59.91 possible points were lost across 3 findings.

### Do the reports still match the data

Whether the reporting layer still matches the data underneath it. This is what catches a renamed column before it breaks a dashboard.

Scored **72.2**, grade B. 18.7 of 51.1 possible points were lost across 10 findings.

### Are the house rules followed

Whether the naming and the layering follow the agreed house rules, so anyone reading a query can tell what they are looking at.

Scored **98.5**, grade A. 2.49 of 133.34 possible points were lost across 3 findings.

### Are the tables the shape they claim

Whether a table named as something you count behaves like something you count. Getting this wrong is how figures get double counted.

Scored **96.4**, grade A. 0.2 of 40.43 possible points were lost across 2 findings.

### What it costs to run

What the warehouse spends running this, and whether any of that spend produces something nobody uses.

Not measured. No rule for this dimension could run, because the data it needs was not available.

## What to fix first

Ranked by how much the score would recover, most serious first.

| How serious | Cases | Points to recover | What is wrong |
|---|---|---|---|
| Needs attention | 2 | 7.3 | Nothing at all checks daily sales. Any problem in it reaches whoever reads the numbers before anyone who could fix it, and 7 report fields depend on it. |
| Needs attention | 1 | 5.8 | These report fields are broken now. Anyone opening a report that uses them gets an error or a blank, and the cause is a column that was renamed or removed in wh_commerce__order_fact. |
| Needs attention | 2 | 5.4 | Rows with no key can appear in customers. They drop out of joins silently, so figures come out low with no error to explain why. |
| Needs attention | 1 | 3.9 | Someone wrote these tests into the Droughty config on purpose and the regeneration dropped them without saying so. customers is being tested less than whoever configured it believes. |
| Needs attention | 1 | 2.0 | Nothing checks that products holds one row per one row per product. If duplicates appear, every total built from it is overstated and nobody is told. nothing downstream depends on it. |
| Needs attention | 1 | 1.5 | Because legacy does not go through dbt to reach this table, the dependency is invisible: it does not appear in the lineage, it is not built in the right order, and nothing warns you if the table it points at changes. |
| Needs attention | 1 | 0.6 | daily sales was designed to hold these columns and does not. Anything that expected them, including a report built from the design, has nothing to read. |
| Worth fixing | 2 | 5.2 | daily sales reaches back past the layer that normally cleans and checks this data, so those checks do not apply to what it reads. |
| Worth fixing | 3 | 3.2 | The generated schema says these tests should exist on orders, and dbt does not have them. Either the generated file has not been applied, or something removed them by hand. |
| Worth fixing | 1 | 2.1 | daily sales was skipped when the schema was generated, so it has neither the generated tests nor the generated descriptions the rest of the project has. |


## How much is covered

| Measure | Share | Counts |
|---|---|---|
| How much of the business model is designed | 85.7% | 6 of 7 |
| How much of the design is built | 66.7% | 4 of 6 |
| Tables with a description | 80% | 4 of 5 |
| Tables with every column described | 100% | 5 of 5 |
| Tables with their key checked | 40% | 2 of 5 |


_Score computed as at 2026-09-08._


---

_Generated by Rittman Hunter, from Rittman Analytics._
