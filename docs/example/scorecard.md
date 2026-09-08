# The score, broken down

# 87.1 / 100

!!! abstract "Well maintained. Safe to build on"
    Grade A.

!!! warning "Some areas were not measured"
    1 of 8 areas could not be measured with the information available. Their weight has been shared across the rest, so the score is still out of 100. They are not counted as passing.

## Each area

| Area | Score | Grade | Share of the total | Findings |
|---|---|---|---|---|
| What is checked automatically | 78.2 | B | 19.355% | 7 |
| Does what was built match the design | 96 | A | 16.129% | 7 |
| How the tables fit together | 86.3 | A | 13.978% | 5 |
| What is written down | 95.8 | A | 13.978% | 3 |
| Do the reports still match the data | 64.3 | C | 13.978% | 10 |
| Are the house rules followed | 98.5 | A | 13.978% | 2 |
| Are the tables the shape they claim | 96.4 | A | 8.602% | 2 |
| What it costs to run | not measured | - | - | 0 |


### What is checked automatically

Whether anything would notice if the data went wrong. A test that only checks a column is not empty does not count as checking a key.

Scored **78.2**, grade B. 12.94 of 54.63 possible points were lost across 7 findings.

### Does what was built match the design

Whether the tables that exist are the tables that were designed, with the columns, keys and relationships the design specifies.

Scored **96**, grade A. 3.04 of 69.73 possible points were lost across 7 findings.

### How the tables fit together

Whether the tables depend on each other in ways that are safe to change, and whether anything is being built that nobody reads.

Scored **86.3**, grade A. 6.16 of 65.03 possible points were lost across 5 findings.

### What is written down

Whether someone new could tell what each table is for, what one row of it means, and who to ask about it.

Scored **95.8**, grade A. 1.83 of 51.25 possible points were lost across 3 findings.

### Do the reports still match the data

Whether the reporting layer still matches the data underneath it. This is what catches a renamed column before it breaks a dashboard.

Scored **64.3**, grade C. 14.3 of 35.7 possible points were lost across 10 findings.

### Are the house rules followed

Whether the naming and the layering follow the agreed house rules, so anyone reading a query can tell what they are looking at.

Scored **98.5**, grade A. 2.19 of 111.29 possible points were lost across 2 findings.

### Are the tables the shape they claim

Whether a table named as something you count behaves like something you count. Getting this wrong is how figures get double counted.

Scored **96.4**, grade A. 0.2 of 31.7 possible points were lost across 2 findings.

### What it costs to run

What the warehouse spends running this, and whether any of that spend produces something nobody uses.

Not measured. No rule for this dimension could run, because the data it needs was not available.

## What to fix first

Ranked by how much the score would recover, most serious first.

| How serious | Cases | Points to recover | What is wrong |
|---|---|---|---|
| Needs attention | 1 | 5.2 | These report fields are broken now. Anyone opening a report that uses them gets an error or a blank, and the cause is a column that was renamed or removed in wh_shop__order_fact. |
| Needs attention | 2 | 4.7 | Rows with no key can appear in customers. They drop out of joins silently, so figures come out low with no error to explain why. |
| Needs attention | 2 | 4.0 | Nothing at all checks daily sales. Any problem in it reaches whoever reads the numbers before anyone who could fix it, and nothing downstream depends on it. |
| Needs attention | 1 | 3.2 | Someone wrote these tests into the Droughty config on purpose and the regeneration dropped them without saying so. customers is being tested less than whoever configured it believes. |
| Needs attention | 1 | 2.0 | Nothing checks that products holds one row per one row per product. it holds last year's categories too. If duplicates appear, every total built from it is overstated and nobody is told. nothing downstream depends on it. |
| Needs attention | 1 | 1.5 | Because legacy does not go through dbt to reach this table, the dependency is invisible: it does not appear in the lineage, it is not built in the right order, and nothing warns you if the table it points at changes. |
| Needs attention | 1 | 0.2 | daily sales was designed to hold these columns and does not. Anything that expected them, including a report built from the design, has nothing to read. |
| Worth fixing | 2 | 3.2 | customers reaches back past the layer that normally cleans and checks this data, so those checks do not apply to what it reads. |
| Worth fixing | 3 | 3.0 | daily sales is rebuilt on every run and no model, report or dashboard uses the result. It costs money and delivers nothing until something consumes it. |
| Worth fixing | 1 | 1.7 | There is nobody to ask about customers and nobody to route a problem with it to. It is a persistent table, and 2 report fields depend on it. |


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
