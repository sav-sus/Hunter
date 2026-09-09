# The rules this was measured against

Measured against **ra-house@1**, house ruleset version 1. Every rule and every weight is listed here, so any number on this site can be traced back to the rule that produced it.

## How the areas are weighted

| Area | Weight | Used this run | Why |
|---|---|---|---|
| What is checked automatically | 18 | 19.355 | - |
| Does what was built match the design | 15 | 16.129 | - |
| How the tables fit together | 13 | 13.978 | - |
| What is written down | 13 | 13.978 | - |
| Do the reports still match the data | 13 | 13.978 | - |
| Are the house rules followed | 13 | 13.978 | - |
| Are the tables the shape they claim | 8 | 8.602 | - |
| What it costs to run | 7 | not measured | No rule for this dimension could run, because the data it needs was not available. |


## The layers

A layer marked *found* was discovered in the models directory and is not in the
ruleset. Its models are grouped and reported, and held to no layer rules until
the layer is declared.

| Layer | Declared | Prefix | Stage | Temporary or permanent | May read | Holds entities |
|---|---|---|---|---|---|---|
| staging | yes | stg_ | 1 | temporary | seeds | no |
| integration | yes | int_ | 2 | temporary | staging, integration, seeds | no |
| warehouse | yes | wh_ | 3 | permanent | staging, integration, warehouse, seeds | yes |
| seeds | yes | - | outside the flow | permanent | anything | no |
| reverse_etl | yes | - | 4 | permanent | warehouse, integration | yes |
| ai | yes | - | 4 | permanent | warehouse, integration | yes |


## Entity naming

| Kind | Name ends with | Needs a key | Needs a uniqueness check |
|---|---|---|---|
| fact | _fact | yes | yes |
| dimension | _dim | yes | yes |
| aggregate | _xa | yes | yes |
| bridge | _bridge | yes | yes |
| snapshot | _snapshot | yes | yes |


## Where this project departs from the house standard

FR7d makes this a first-class output: on a client engagement it shows how far the repository sits from the standard, which is itself a finding.

| Setting | Change | House says | This project says | Reason given |
|---|---|---|---|---|
| rules.structure.model_too_long.enabled | disabled | True | False | this example has no long models, so the rule adds nothing here |


## Every rule

| Rule | Area | How serious | Points | Ran this time | Needs |
|---|---|---|---|---|---|
| `alignment.ambiguous_match` | Does what was built match the design | Worth fixing | 0.8 | yes | dbml |
| `alignment.approved_off_plan` | Does what was built match the design | For information | 0 | yes | manifest |
| `alignment.built_disabled` | Does what was built match the design | Tidy up | 0.5 | yes | manifest |
| `alignment.built_off_plan` | Does what was built match the design | Worth fixing | 1.2 | yes | manifest, dbml |
| `alignment.design_backlog` | Does what was built match the design | For information | 0 | no | conceptual |
| `alignment.design_without_business_entity` | Does what was built match the design | Tidy up | 0.4 | yes | dbml, conceptual |
| `alignment.diagram_claim_stale` | Does what was built match the design | Worth fixing | 0.6 | yes | conceptual |
| `alignment.unmanaged_production_object` | Does what was built match the design | Needs attention | 1.5 | yes | manifest |
| `conformance.column_missing_from_design` | Does what was built match the design | Tidy up | 0.5 | yes | manifest |
| `conformance.column_missing_from_model` | Does what was built match the design | Needs attention | 1.2 | yes | manifest |
| `conformance.design_entity_suffix_missing` | Does what was built match the design | Tidy up | 0.5 | yes | dbml |
| `conformance.design_key_naming` | Does what was built match the design | Tidy up | 0.4 | yes | dbml |
| `conformance.design_no_primary_key` | Does what was built match the design | Needs attention | 1.5 | yes | dbml |
| `conformance.design_not_built` | Does what was built match the design | Worth fixing | 1 | yes | dbml |
| `conformance.relationship_key_missing` | Does what was built match the design | Needs attention | 1.5 | yes | dbml |
| `conformance.relationship_not_tested` | Does what was built match the design | Worth fixing | 1 | yes | manifest, dbml |
| `conformance.type_drift` | Does what was built match the design | Worth fixing | 1 | no | manifest, dbml |
| `conformance.types_unavailable` | Does what was built match the design | For information | 0 | no | manifest, dbml |
| `crosslayer.duplicate_measure` | Do the reports still match the data | Worth fixing | 1 | yes | manifest, lookml |
| `crosslayer.explore_no_caching_policy` | Do the reports still match the data | Tidy up | 0.4 | yes | lookml |
| `crosslayer.exposure_missing` | Do the reports still match the data | Tidy up | 0.4 | yes | manifest, lookml |
| `crosslayer.field_references_missing_column` | Do the reports still match the data | Needs attention | 2 | yes | manifest, lookml |
| `crosslayer.view_model_missing` | Do the reports still match the data | Needs attention | 2 | yes | manifest, lookml |
| `crosslayer.view_table_unresolvable` | Do the reports still match the data | Tidy up | 0.3 | no | lookml |
| `documentation.column_description_missing` | What is written down | Tidy up | 0.8 | yes | manifest |
| `documentation.description_stale` | What is written down | Tidy up | 0.5 | no | manifest, git |
| `documentation.design_column_notes_missing` | What is written down | Tidy up | 0.8 | yes | dbml |
| `documentation.design_grain_missing` | What is written down | Worth fixing | 1 | yes | dbml |
| `documentation.design_note_missing` | What is written down | Worth fixing | 1 | yes | dbml |
| `documentation.model_description_missing` | What is written down | Worth fixing | 1 | yes | manifest |
| `documentation.model_description_placeholder` | What is written down | Worth fixing | 1 | yes | manifest |
| `documentation.owner_missing` | What is written down | Worth fixing | 0.8 | yes | manifest |
| `droughty.description_empty` | What is written down | Worth fixing | 0.6 | yes | droughty |
| `droughty.description_orphaned` | What is written down | Tidy up | 0.1 | yes | droughty |
| `droughty.description_undefined` | What is written down | Worth fixing | 0.6 | yes | droughty |
| `droughty.generated_test_missing` | Do the reports still match the data | Worth fixing | 0.8 | yes | manifest, droughty |
| `droughty.introspected_column_undesigned` | Does what was built match the design | Tidy up | 0.4 | yes | droughty, dbml |
| `droughty.model_not_covered` | Do the reports still match the data | Worth fixing | 0.8 | yes | manifest, droughty |
| `droughty.override_dropped` | Do the reports still match the data | Needs attention | 1.5 | yes | droughty |
| `droughty.schema_stale` | Do the reports still match the data | Worth fixing | 1 | yes | droughty |
| `entity.declared_type_mismatch` | Are the tables the shape they claim | Needs attention | 2 | yes | manifest |
| `entity.dimension_with_measures` | Are the tables the shape they claim | Worth fixing | 1 | yes | manifest |
| `entity.fact_without_measures` | Are the tables the shape they claim | Worth fixing | 1 | yes | manifest |
| `entity.surrogate_key_missing` | Are the tables the shape they claim | Needs attention | 1.5 | yes | manifest |
| `entity.type_unclear` | Are the tables the shape they claim | Tidy up | 0.5 | no | manifest |
| `lineage.dead_model` | How the tables fit together | Worth fixing | 1 | yes | manifest |
| `lineage.dependency_cycle` | How the tables fit together | Needs attention | 4 | no | manifest |
| `lineage.high_fanout` | How the tables fit together | Worth fixing | 1 | yes | manifest |
| `lineage.model_rejoin` | How the tables fit together | Needs attention | 1.5 | yes | manifest |
| `lineage.staging_bypassed` | How the tables fit together | Worth fixing | 1 | yes | manifest |
| `lineage.temporary_model_exposed` | How the tables fit together | Needs attention | 1.5 | yes | manifest |
| `naming.date_column_suffix` | Are the house rules followed | Tidy up | 0.4 | yes | manifest |
| `naming.direct_source_reference` | Are the house rules followed | Needs attention | 1.5 | yes | manifest |
| `naming.entity_suffix_missing` | Are the house rules followed | Worth fixing | 0.8 | yes | manifest |
| `naming.layer_boundary_violation` | Are the house rules followed | Needs attention | 1.5 | yes | manifest |
| `naming.layer_prefix_wrong` | Are the house rules followed | Tidy up | 0.6 | yes | manifest |
| `naming.materialisation_not_permitted` | Are the house rules followed | Worth fixing | 0.8 | yes | manifest |
| `naming.model_outside_every_layer` | Are the house rules followed | Worth fixing | 1 | no | manifest |
| `naming.primary_key_column_missing` | Are the house rules followed | Needs attention | 1.5 | yes | manifest |
| `register.approval_matches_no_model` | Does what was built match the design | Worth fixing | 0.3 | no | nothing |
| `register.approval_review_overdue` | Does what was built match the design | Worth fixing | 0.6 | no | nothing |
| `register.entry_matches_no_model` | Does what was built match the design | Worth fixing | 0.3 | no | nothing |
| `register.ignore_expired` | Are the house rules followed | Worth fixing | 0.6 | no | nothing |
| `register.ignore_names_unknown_rule` | Are the house rules followed | Worth fixing | 0.3 | no | nothing |
| `register.review_overdue` | Does what was built match the design | Worth fixing | 0.6 | no | nothing |
| `structure.cte_name_invalid` | Are the house rules followed | Tidy up | 0.3 | yes | manifest |
| `structure.hardcoded_reference` | Are the house rules followed | Needs attention | 1.5 | yes | manifest |
| `structure.select_star_from_source` | Are the house rules followed | Tidy up | 0.3 | yes | manifest |
| `structure.too_many_joins` | Are the house rules followed | Worth fixing | 0.8 | yes | manifest |
| `testing.declared_grain_untested` | What is checked automatically | Worth fixing | 1.2 | yes | manifest, dbml |
| `testing.key_not_null_missing` | What is checked automatically | Needs attention | 1.5 | yes | manifest |
| `testing.key_test_warns_only` | What is checked automatically | Worth fixing | 0.8 | yes | manifest |
| `testing.key_uniqueness_missing` | What is checked automatically | Needs attention | 2 | yes | manifest |
| `testing.no_tests_at_all` | What is checked automatically | Needs attention | 2 | yes | manifest |
| `testing.only_weak_tests` | What is checked automatically | Worth fixing | 1 | yes | manifest |
| `testing.relationship_test_missing` | What is checked automatically | Worth fixing | 1 | yes | manifest |


## Rules switched off for this project

| Rule | Reason given |
|---|---|
| `structure.model_too_long` | this example has no long models, so the rule adds nothing here |



_Ruleset resolved as at 2026-09-08._


---

_Generated by Rittman Hunter, from Rittman Analytics._
