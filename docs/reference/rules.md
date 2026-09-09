# Every rule

Hunter has 77 rules across 7 areas. This page is generated from the rules themselves, so it cannot go stale.

Each rule can be switched off, reweighted or re-graded in a project's `hunter.yml`. Doing so needs a reason, and that reason is published on the conventions page of whatever the rule was run against.

## What the columns mean

| Column | Meaning |
|---|---|
| Rule | The identifier to use in `hunter.yml` and in the register |
| How serious | What Hunter calls it in plain words. Only the most serious can fail a build in gate mode |
| Points | What it deducts before weighting. Scaled up where more depends on the object, and scaled down for a partial gap |
| Needs | The data the rule cannot run without. A rule whose data is absent is skipped, and its area says so |

## What is checked automatically

Whether anything would notice if the data went wrong. A test that only checks a column is not empty does not count as checking a key.

| Rule | How serious | Points | Needs |
|---|---|---|---|
| `testing.declared_grain_untested` | Worth fixing | 1.2 | manifest, dbml |
| `testing.key_not_null_missing` | Needs attention | 1.5 | manifest |
| `testing.key_test_warns_only` | Worth fixing | 0.8 | manifest |
| `testing.key_uniqueness_missing` | Needs attention | 2 | manifest |
| `testing.no_tests_at_all` | Needs attention | 2 | manifest |
| `testing.only_weak_tests` | Worth fixing | 1 | manifest |
| `testing.relationship_test_missing` | Worth fixing | 1 | manifest |

### `testing.declared_grain_untested`

**Reports**: The declared grain of {subject} is not tested

**Says**: The design says {label} holds {grain}, and nothing checks that it does. If the grain is wrong, figures double-count with no test to catch it.

### `testing.key_not_null_missing`

**Reports**: Nothing tests that {key} is always populated on {subject}

**Says**: Rows with no key can appear in {label}. They drop out of joins silently, so figures come out low with no error to explain why.

### `testing.key_test_warns_only`

**Reports**: The key tests on {subject} are set to warn, so they never fail a build

**Says**: The uniqueness check on {label} reports a problem but lets the build carry on, so bad data reaches reports anyway. Someone has to be watching the log.

### `testing.key_uniqueness_missing`

**Reports**: Nothing tests that {key} is unique on {subject}

**Says**: Nothing checks that {label} holds one row per {grain}. If duplicates appear, every total built from it is overstated and nobody is told. {consumers}.

### `testing.no_tests_at_all`

**Reports**: {subject} has no tests of any kind

**Says**: Nothing at all checks {label}. Any problem in it reaches whoever reads the numbers before anyone who could fix it, and {consumers}.

### `testing.only_weak_tests`

**Reports**: {subject} has {phrase} but none of them prove a key

**Says**: The tests on {label} check that columns are not entirely empty. None of them check that it has one row per thing, or that its references resolve.

### `testing.relationship_test_missing`

**Reports**: {phrase} on {subject} have no relationship test: {columns}

**Says**: Nothing checks that these references in {label} point at rows that exist. Where they do not, joined figures come out low and the rows simply vanish.

## Does what was built match the design

Whether the tables that exist are the tables that were designed, with the columns, keys and relationships the design specifies.

| Rule | How serious | Points | Needs |
|---|---|---|---|
| `alignment.ambiguous_match` | Worth fixing | 0.8 | dbml |
| `alignment.approved_off_plan` | For information | 0 | manifest |
| `alignment.built_disabled` | Tidy up | 0.5 | manifest |
| `alignment.built_off_plan` | Worth fixing | 1.2 | manifest, dbml |
| `alignment.design_backlog` | For information | 0 | conceptual |
| `alignment.design_without_business_entity` | Tidy up | 0.4 | dbml, conceptual |
| `alignment.diagram_claim_stale` | Worth fixing | 0.6 | conceptual |
| `alignment.unmanaged_production_object` | Needs attention | 1.5 | manifest |
| `conformance.column_missing_from_design` | Tidy up | 0.5 | manifest |
| `conformance.column_missing_from_model` | Needs attention | 1.2 | manifest |
| `conformance.design_entity_suffix_missing` | Tidy up | 0.5 | dbml |
| `conformance.design_key_naming` | Tidy up | 0.4 | dbml |
| `conformance.design_no_primary_key` | Needs attention | 1.5 | dbml |
| `conformance.design_not_built` | Worth fixing | 1 | dbml |
| `conformance.relationship_key_missing` | Needs attention | 1.5 | dbml |
| `conformance.relationship_not_tested` | Worth fixing | 1 | manifest, dbml |
| `conformance.type_drift` | Worth fixing | 1 | manifest, dbml |
| `conformance.types_unavailable` | For information | 0 | manifest, dbml |
| `droughty.introspected_column_undesigned` | Tidy up | 0.4 | droughty, dbml |
| `register.approval_matches_no_model` | Worth fixing | 0.3 | nothing |
| `register.approval_review_overdue` | Worth fixing | 0.6 | nothing |
| `register.entry_matches_no_model` | Worth fixing | 0.3 | nothing |
| `register.review_overdue` | Worth fixing | 0.6 | nothing |

### `alignment.ambiguous_match`

**Reports**: {subject} could be either of {phrase}, so Hunter did not choose: {candidates}

**Says**: Hunter cannot tell which designed table {label} corresponds to, so its row in the reconciliation is incomplete. Adding an implements entry to the register settles it. Guessing would have produced a wrong row that reads as fact.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.
- Reports what Hunter could not check rather than what the repository got wrong, so it never counts as a gap.

### `alignment.approved_off_plan`

**Reports**: {subject} is built ahead of the design, with that approved

**Says**: {label} was accepted as an exception rather than added to the design. Recorded reason: {reason}


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.
- Deducts nothing. It is there to be read, not scored.

### `alignment.built_disabled`

**Reports**: {subject} is built but switched off

**Says**: The code for {label} exists and is not running, so nothing is being produced from it. Either it is waiting to be turned on, or it was left behind and should be removed.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `alignment.built_off_plan`

**Reports**: {subject} is built but was never designed

**Says**: {label} exists in production and appears on no design, so nothing records what it is for, what one row means or who owns it. If it should be there, add it to the design or record an approval in the register.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `alignment.design_backlog`

**Reports**: {phrase} on the business model have not been designed yet

**Says**: These are agreed with the business as things the warehouse should hold, and no design exists for them yet. This is the design backlog, not a list of faults. Examples: {examples}.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.
- Deducts nothing. It is there to be read, not scored.

### `alignment.design_without_business_entity`

**Reports**: {subject} is designed but appears on no business model

**Says**: {label} was designed without a matching entity on the conceptual model, so there is no record of which part of the business asked for it.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `alignment.diagram_claim_stale`

**Reports**: The business model shows {subject} as {claimed}, but it is {actual}

**Says**: The published picture of the data model is out of date for {label}. Anyone reading it is being told something that is not true, which is worse than not having the picture.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `alignment.unmanaged_production_object`

**Reports**: {subject} is in production and nothing here produces it

**Says**: Something outside this project is writing {label}. Nobody here manages it, nothing tests it, and a change to it would not be noticed.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `conformance.column_missing_from_design`

**Reports**: {subject} has {phrase} the design does not include: {columns}

**Says**: {label} holds columns nobody designed, so they are undocumented and their business meaning is not recorded anywhere.

### `conformance.column_missing_from_model`

**Reports**: {subject} is missing {phrase} that the design specifies: {columns}

**Says**: {label} was designed to hold these columns and does not. Anything that expected them, including a report built from the design, has nothing to read.

### `conformance.design_entity_suffix_missing`

**Reports**: The designed name {subject} declares no entity type

**Says**: The design does not say whether {label} is a fact, a dimension or an aggregate, so a reader cannot tell how it is meant to be used. Expected one of: {expected}.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `conformance.design_key_naming`

**Reports**: The design for {subject} has {phrase} named outside the key rules: {columns}

**Says**: Keys in the design of {label} are not named the way the standard says, so it is not obvious which columns identify a row and which point elsewhere.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `conformance.design_no_primary_key`

**Reports**: The design for {subject} declares no primary key

**Says**: Nothing in the design says what makes a row of {label} unique, so nobody can tell what one row means or check that duplicates have not crept in.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `conformance.design_not_built`

**Reports**: {subject} is designed but no model builds it

**Says**: {label} was designed and agreed, and nothing in the repository produces it yet. It is on the plan and not started.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `conformance.relationship_key_missing`

**Reports**: The designed link from {subject}.{column} points at {target}.{target_column}, which does not exist

**Says**: The design connects {label} to something that is not there. Either the design is out of date or the table it points at was never built as designed.

### `conformance.relationship_not_tested`

**Reports**: The designed link from {subject}.{column} to {target} has no test

**Says**: The design says every row of {label} points at a row of {target}, and nothing checks it. Where it does not hold, those rows drop out of joins and figures come out low with no error.

### `conformance.type_drift`

**Reports**: {subject} has {phrase} built with a different type than designed: {columns}

**Says**: These columns of {label} hold a different kind of value than the design says. Depending on the difference, figures may be rounded, truncated or compared wrongly.

### `conformance.types_unavailable`

**Reports**: Column types were not available, so designed and built types were not compared

**Says**: Hunter could not check whether columns are built with the types the design specifies, because the project has no catalogue file. Running 'dbt docs generate' alongside the build would let this run. Nothing here means the types are wrong; it means they were not checked.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.
- Reports what Hunter could not check rather than what the repository got wrong, so it never counts as a gap.
- Deducts nothing. It is there to be read, not scored.

### `droughty.introspected_column_undesigned`

**Reports**: {subject} holds {phrase} in the warehouse that the design does not include: {columns}

**Says**: The warehouse picture taken by Droughty shows columns on {label} that nobody designed, so their business meaning is not recorded.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `register.approval_matches_no_model`

**Reports**: {summary}

**Says**: {consequence}


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `register.approval_review_overdue`

**Reports**: {summary}

**Says**: {consequence}


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `register.entry_matches_no_model`

**Reports**: {summary}

**Says**: {consequence}


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `register.review_overdue`

**Reports**: {summary}

**Says**: {consequence}


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

## How the tables fit together

Whether the tables depend on each other in ways that are safe to change, and whether anything is being built that nobody reads.

| Rule | How serious | Points | Needs |
|---|---|---|---|
| `lineage.dead_model` | Worth fixing | 1 | manifest |
| `lineage.dependency_cycle` | Needs attention | 4 | manifest |
| `lineage.high_fanout` | Worth fixing | 1 | manifest |
| `lineage.model_rejoin` | Needs attention | 1.5 | manifest |
| `lineage.staging_bypassed` | Worth fixing | 1 | manifest |
| `lineage.temporary_model_exposed` | Needs attention | 1.5 | manifest |

### `lineage.dead_model`

**Reports**: {subject} is built and stored but nothing reads it

**Says**: {label} is rebuilt on every run and no model, report or dashboard uses the result. It costs money and delivers nothing until something consumes it.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `lineage.dependency_cycle`

**Reports**: {subject} is part of a dependency loop: {cycle}

**Says**: These models depend on each other in a circle, so there is no order in which they can be built. The project as described cannot run.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `lineage.high_fanout`

**Reports**: {phrase} read directly from {subject}, over the limit of {limit}

**Says**: Any change to {label} is a change to {count} other models at once, so in practice nobody can safely alter it.

### `lineage.model_rejoin`

**Reports**: {subject} reads {rejoined} by more than one path

**Says**: {label} brings in the same upstream data twice through different routes. If either path returns more than one row per key, figures double-count with nothing to signal it.

### `lineage.staging_bypassed`

**Reports**: {subject} skips the {skipped} layer to read {referenced}

**Says**: {label} reaches back past the layer that normally cleans and checks this data, so those checks do not apply to what it reads.

### `lineage.temporary_model_exposed`

**Reports**: {subject} is a working step but {consumer_kind} reads it directly

**Says**: {label} was built as a temporary step and was never meant to be relied on. Something outside the modelling layer now depends on it, so it cannot be changed or removed without breaking that. {detail}

## What is written down

Whether someone new could tell what each table is for, what one row of it means, and who to ask about it.

| Rule | How serious | Points | Needs |
|---|---|---|---|
| `documentation.column_description_missing` | Tidy up | 0.8 | manifest |
| `documentation.description_stale` | Tidy up | 0.5 | manifest, git |
| `documentation.design_column_notes_missing` | Tidy up | 0.8 | dbml |
| `documentation.design_grain_missing` | Worth fixing | 1 | dbml |
| `documentation.design_note_missing` | Worth fixing | 1 | dbml |
| `documentation.model_description_missing` | Worth fixing | 1 | manifest |
| `documentation.model_description_placeholder` | Worth fixing | 1 | manifest |
| `documentation.owner_missing` | Worth fixing | 0.8 | manifest |
| `droughty.description_empty` | Worth fixing | 0.6 | droughty |
| `droughty.description_orphaned` | Tidy up | 0.1 | droughty |
| `droughty.description_undefined` | Worth fixing | 0.6 | droughty |

### `documentation.column_description_missing`

**Reports**: {count} of {total} columns on {subject} have no description

**Says**: {label} has {phrase} with no description, so anyone building a report from it has to guess the meaning or ask whoever wrote it.

### `documentation.description_stale`

**Reports**: {subject} was changed {days} days after its description was last touched

**Says**: The description of {label} may no longer match what the table does. The code has moved on and the documentation has not.

### `documentation.design_column_notes_missing`

**Reports**: {phrase} of {total} designed columns on {subject} have no note

**Says**: The design of {label} leaves {phrase} unexplained, so the business meaning has to be worked out from the name.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `documentation.design_grain_missing`

**Reports**: The design for {subject} does not state its grain

**Says**: Nothing records what one row of {label} represents, so nobody can tell whether summing its figures double-counts.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `documentation.design_note_missing`

**Reports**: The design for {subject} has no note

**Says**: The design says what columns {label} should have but not what it is for or what one row represents. That is the part a non-technical reader needs.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `documentation.model_description_missing`

**Reports**: {subject} has no description

**Says**: Nobody reading the catalogue can tell what {label} is for or whether it is the right table to use. {consumers}.

### `documentation.model_description_placeholder`

**Reports**: {subject} has a placeholder description: {text!r}

**Says**: The description for {label} says {text!r}, which tells a reader nothing. It counts as documented in the catalogue while explaining nothing.

### `documentation.owner_missing`

**Reports**: {subject} names no owner

**Says**: There is nobody to ask about {label} and nobody to route a problem with it to. It is a persistent table, and {consumers}.

### `droughty.description_empty`

**Reports**: {phrase} are defined but say nothing: {blocks}

**Says**: These descriptions exist and are blank, so the column counts as documented in the catalogue while explaining nothing to a reader.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `droughty.description_orphaned`

**Reports**: {phrase} are defined and never used

**Says**: The description file has grown past the model it describes. These entries describe columns that no longer exist, so anyone reading the file to understand the data will be misled by them.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `droughty.description_undefined`

**Reports**: {phrase} referenced by the generated schema are not defined: {blocks}

**Says**: The schema points at descriptions that do not exist, so those columns show up in the catalogue with nothing written against them.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

## Do the reports still match the data

Whether the reporting layer still matches the data underneath it. This is what catches a renamed column before it breaks a dashboard.

| Rule | How serious | Points | Needs |
|---|---|---|---|
| `crosslayer.duplicate_measure` | Worth fixing | 1 | manifest, lookml |
| `crosslayer.explore_no_caching_policy` | Tidy up | 0.4 | lookml |
| `crosslayer.exposure_missing` | Tidy up | 0.4 | manifest, lookml |
| `crosslayer.field_references_missing_column` | Needs attention | 2 | manifest, lookml |
| `crosslayer.view_model_missing` | Needs attention | 2 | manifest, lookml |
| `crosslayer.view_table_unresolvable` | Tidy up | 0.3 | lookml |
| `droughty.generated_test_missing` | Worth fixing | 0.8 | manifest, droughty |
| `droughty.model_not_covered` | Worth fixing | 0.8 | manifest, droughty |
| `droughty.override_dropped` | Needs attention | 1.5 | droughty |
| `droughty.schema_stale` | Worth fixing | 1 | droughty |

### `crosslayer.duplicate_measure`

**Reports**: {subject} defines {phrase} that {model} already computes: {columns}

**Says**: The same figure is worked out in two places. When one is changed and the other is not, two reports show different numbers for the same thing and nobody can tell which is right.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `crosslayer.explore_no_caching_policy`

**Reports**: Explore {subject} has no caching policy

**Says**: Every query against this explore goes to the warehouse, so it costs more than it needs to and is slower for whoever is waiting.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `crosslayer.exposure_missing`

**Reports**: {subject} feeds {phrase} but declares no exposure

**Says**: Nothing in the project records that reports depend on {label}, so anyone changing it has no way to see what they would break.

### `crosslayer.field_references_missing_column`

**Reports**: {phrase} in view {subject} read columns {model} no longer produces: {columns}

**Says**: These report fields are broken now. Anyone opening a report that uses them gets an error or a blank, and the cause is a column that was renamed or removed in {model}.

### `crosslayer.view_model_missing`

**Reports**: View {subject} reads {table}, which no model produces

**Says**: This report view points at a table nothing in the project builds. Either the table is produced outside dbt, or the view is pointing at something that no longer exists.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `crosslayer.view_table_unresolvable`

**Reports**: View {subject} names its table in a way Hunter cannot resolve: {table!r}

**Says**: Hunter could not tell which table this report view reads, so its fields were not checked against the data. Nothing here says it is broken; it says it was not checked.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.
- Reports what Hunter could not check rather than what the repository got wrong, so it never counts as a gap.

### `droughty.generated_test_missing`

**Reports**: {phrase} in the generated schema for {subject} are not in the project: {tests}

**Says**: The generated schema says these tests should exist on {label}, and dbt does not have them. Either the generated file has not been applied, or something removed them by hand.

### `droughty.model_not_covered`

**Reports**: {subject} is not described in the generated schema

**Says**: {label} was skipped when the schema was generated, so it has neither the generated tests nor the generated descriptions the rest of the project has.

### `droughty.override_dropped`

**Reports**: {phrase} declared for {subject} never reached the generated schema: {tests}

**Says**: Someone wrote these tests into the Droughty config on purpose and the regeneration dropped them without saying so. {label} is being tested less than whoever configured it believes.

### `droughty.schema_stale`

**Reports**: The generated schema is {days} days old, over the {limit} day window

**Says**: Every comparison against the generated schema is being made against an out-of-date picture. Regenerating it would either clear these findings or show real ones.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

## Are the house rules followed

Whether the naming and the layering follow the agreed house rules, so anyone reading a query can tell what they are looking at.

| Rule | How serious | Points | Needs |
|---|---|---|---|
| `naming.date_column_suffix` | Tidy up | 0.4 | manifest |
| `naming.direct_source_reference` | Needs attention | 1.5 | manifest |
| `naming.entity_suffix_missing` | Worth fixing | 0.8 | manifest |
| `naming.layer_boundary_violation` | Needs attention | 1.5 | manifest |
| `naming.layer_prefix_wrong` | Tidy up | 0.6 | manifest |
| `naming.materialisation_not_permitted` | Worth fixing | 0.8 | manifest |
| `naming.model_outside_every_layer` | Worth fixing | 1 | manifest |
| `naming.primary_key_column_missing` | Needs attention | 1.5 | manifest |
| `register.ignore_expired` | Worth fixing | 0.6 | nothing |
| `register.ignore_names_unknown_rule` | Worth fixing | 0.3 | nothing |
| `structure.cte_name_invalid` | Tidy up | 0.3 | manifest |
| `structure.hardcoded_reference` | Needs attention | 1.5 | manifest |
| `structure.model_too_long` | Tidy up | 0.6 | manifest |
| `structure.select_star_from_source` | Tidy up | 0.3 | manifest |
| `structure.too_many_joins` | Worth fixing | 0.8 | manifest |

### `naming.date_column_suffix`

**Reports**: {phrase} on {subject} do not end in {date!r} or {ts!r}

**Says**: A reader cannot tell from the name whether these columns hold a date or a point in time, which is how time-zone errors get into reports: {columns}.

### `naming.direct_source_reference`

**Reports**: {subject} ({layer}) reads directly from {phrase}

**Says**: {label} reads raw source data with no staging step in between, so a change at the source lands straight in it. Sources read: {sources}.

### `naming.entity_suffix_missing`

**Reports**: {subject} is in the {layer} layer but its name declares no entity type

**Says**: The name does not say whether {label} is a fact, a dimension or an aggregate, so nobody can tell how it is meant to be joined or summed. Expected one of: {expected}.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `naming.layer_boundary_violation`

**Reports**: {subject} ({layer}) reads from {referenced} ({referenced_layer}), which is not permitted

**Says**: {label} skips the layers in between, so a change upstream reaches it with nothing to catch the problem first. The {layer} layer may only read from: {permitted}.

### `naming.layer_prefix_wrong`

**Reports**: {subject} sits in the {layer} layer but does not start with {prefix!r}

**Says**: The name does not say which layer {label} belongs to, so anyone reading a query cannot tell whether they are using a finished table or a working step.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `naming.materialisation_not_permitted`

**Reports**: {subject} is materialised as {materialisation!r}, which the {layer} layer does not permit

**Says**: {label} is built in a way its layer does not allow, so it either costs more to run than intended or does not persist when it should. Permitted here: {permitted}.

### `naming.model_outside_every_layer`

**Reports**: {subject} is at {path} which belongs to no declared layer

**Says**: No conventions are being applied to {label} at all, because Hunter cannot tell which layer it is meant to be in. It is unchecked rather than correct.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `naming.primary_key_column_missing`

**Reports**: {subject} has no column ending in {suffix!r}

**Says**: {label} has no identifiable key column, so nothing can check it has one row per thing, and joins to it cannot be verified.

### `register.ignore_expired`

**Reports**: {summary}

**Says**: {consequence}


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `register.ignore_names_unknown_rule`

**Reports**: {summary}

**Says**: {consequence}


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `structure.cte_name_invalid`

**Reports**: {phrase} in {subject} do not match the naming pattern: {names}

**Says**: The intermediate steps inside {label} are named inconsistently, which makes the query harder to follow than it needs to be.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `structure.hardcoded_reference`

**Reports**: {subject} names the table {reference!r} directly on line {line}

**Says**: Because {label} does not go through dbt to reach this table, the dependency is invisible: it does not appear in the lineage, it is not built in the right order, and nothing warns you if the table it points at changes.

### `structure.model_too_long`

**Reports**: {subject} is {lines} lines, over the {limit} line ceiling

**Says**: {label} is long enough that reviewing a change to it is hard, so mistakes get through. It is a candidate for splitting into steps.


- Not weighted by what depends on the object: this is about the repository rather than one table's reach.

### `structure.select_star_from_source`

**Reports**: {subject} selects every column from {target} on line {line}

**Says**: A column added at the source appears in {label} without anyone deciding to take it, and a renamed one disappears. Reports built on it change shape with no change made here.

### `structure.too_many_joins`

**Reports**: {subject} has {joins} joins, over the {limit} join ceiling

**Says**: With {joins} joins in one query, a single wrong join condition in {label} can quietly multiply rows and inflate every figure built on it.

## Are the tables the shape they claim

Whether a table named as something you count behaves like something you count. Getting this wrong is how figures get double counted.

| Rule | How serious | Points | Needs |
|---|---|---|---|
| `entity.declared_type_mismatch` | Needs attention | 2 | manifest |
| `entity.dimension_with_measures` | Worth fixing | 1 | manifest |
| `entity.fact_without_measures` | Worth fixing | 1 | manifest |
| `entity.surrogate_key_missing` | Needs attention | 1.5 | manifest |
| `entity.type_unclear` | Tidy up | 0.5 | manifest |

### `entity.declared_type_mismatch`

**Reports**: {subject} is named as {declared_article} {declared} but behaves like {inferred_article} {inferred}

**Says**: {label} is used as though it were {declared_article} {declared}, but its columns say it is {inferred_article} {inferred}. Joining or summing it as the name suggests will give the wrong answer. Evidence: {evidence_text}.


- Reported with a confidence of at most 0.8. Below the configured floor it becomes a suggestion and is left out of the score.

### `entity.dimension_with_measures`

**Reports**: {subject} is named as a dimension but carries {phrase}

**Says**: {label} is named as a lookup table but holds figures. Anyone joining it and summing those figures will multiply them by however many rows the join returns. Columns: {columns}.

### `entity.fact_without_measures`

**Reports**: {subject} is named as a fact but has no numeric columns to add up

**Says**: {label} is named as something you would total, and there is nothing in it to total. Either it is really a dimension or a bridge, or the measures are missing.

### `entity.surrogate_key_missing`

**Reports**: {subject} is {declared_article} {declared} with no surrogate key column

**Says**: {label} has no single column identifying a row, so nothing can prove it has one row per thing and joins to it cannot be checked.

### `entity.type_unclear`

**Reports**: {subject} is named as {declared_article} {declared}, and its shape neither clearly agrees nor disagrees

**Says**: Hunter could not tell from its columns whether {label} really is {declared_article} {declared}. Worth a human look rather than a change. Evidence: {evidence_text}.


- Reported with a confidence of at most 0.4. Below the configured floor it becomes a suggestion and is left out of the score.

## What it costs to run

What the warehouse spends running this, and whether any of that spend produces something nobody uses.

No rules yet. This area needs warehouse access, which is not read at this version, so it is excluded from the score and its weight shared across the others.

---

_Generated by `scripts/build_docs_pages.py`. Do not edit by hand._
