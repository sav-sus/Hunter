# Configuration

Hunter ships with the Rittman Analytics house standard and no opinions of its
own beyond it. Every layer name, naming
convention, threshold and weight is declared, which is what makes it portable
between repositories that disagree with each other.

## Five levels

Each overrides the one above.

| Level | File | Owned by | Changes |
|---|---|---|---|
| Built-in defaults | Shipped in the package | Whoever maintains Hunter | With a release |
| House standard | `ra-house-1.yml`, version-pinned | Rittman Analytics delivery leadership | With a release, and a project has to opt in |
| Project | `.hunter/hunter.yml` | The engagement lead | Rarely |
| Register | `.hunter/register.yml` | Whoever is doing the work | Constantly |
| Per model | `meta.hunter` in a schema file | The model's author | With the model |

Hunter records where every resolved value came from. That is not a debugging
aid: any difference from the house standard is published on the conventions page
with the reason given for it, so on a client engagement the report shows how far
the repository sits from the standard.

## `.hunter/hunter.yml`

`hunter init` writes a starting version with your paths already filled in. This
is the full shape.

```yaml
# Which house standard, and which version of it. Pinning means the standard
# changing does not move your score until you decide it should.
extends: ra-house@1

paths:
  dbt_project_dir: analytics_warehouse   # relative to the repository root
  manifest: target/manifest.json         # relative to dbt_project_dir
  dbml:
    - docs/data_model_design/*.dbml
  conceptual_diagram: docs/data_model_design/conceptual_model.mermaid
  logical_diagram: docs/data_model_design/logical_model.mermaid
  lookml:
    - lookml/**/*.lkml
  droughty_dbml:
    - docs/db_docs/*.dbml
  register_file: .hunter/register.yml
  baseline: .hunter/baseline.json
  output_dir: out

# Layers merge on their name, so overriding one keeps the others.
layers:
  - name: staging
    paths: ["models/staging/**", "models/base/**"]
    prefix: stg_

pull_request:
  mode: advisory            # advisory, ratchet or gate
  new_violations_only: true
  max_findings_shown: 20

scoring:
  exposure_weighting: true
  fail_under: null          # gate mode fails below this
  fail_on_regression: false # ratchet mode
  min_confidence_to_score: 0.7

# Switching a rule off or changing its weight needs a reason, and the reason is
# published. That is the point of asking for it.
rules:
  structure.select_star_from_source:
    enabled: false
    reason: staging deliberately takes every column and reshapes downstream
  testing.relationship_test_missing:
    points: 2.0
    reason: unresolved joins have caused two reporting incidents this year
```

Unknown keys are errors. A typo must not silently switch off a rule.

## Layers

A layer says what is allowed in it.

```yaml
layers:
  - name: warehouse
    paths: ["models/warehouse/**", "models/wh_*/**"]
    prefix: wh_
    materialisations: [table, incremental]
    persistence: persistent
    pipeline_stage: 3
    may_reference: [staging, integration, warehouse, seeds]
    may_reference_sources: false
    requires_model_description: true
    requires_column_descriptions: true
    requires_owner: true
    requires_key_tests: true
    expected_entity_kinds: [fact, dimension, aggregate, bridge, snapshot]
    in_alignment: true
```

| Field | What it does |
|---|---|
| `paths` | Glob patterns that place a model in this layer |
| `prefix` | Required name prefix. Omit for no requirement |
| `materialisations` | Permitted materialisations. Empty means any |
| `persistence` | `temporary` or `persistent`. Feeds the classification |
| `pipeline_stage` | Position in the flow. Reading two stages below is a bypass. 0 means outside the flow |
| `may_reference` | Layers this one may read. Empty means any |
| `may_reference_sources` | Whether it may read a raw source directly |
| `requires_*` | What is expected of a model in this layer |
| `expected_entity_kinds` | Which entity types belong here. Drives the suffix check |
| `in_alignment` | Whether this layer holds modelled entities that belong in the reconciliation |

Two are easy to get wrong.

**`pipeline_stage` is not the order layers appear in the file.** An earlier
version of Hunter inferred it from declaration order and produced "skips the
seeds layer to read a warehouse table". Declare it.

**`in_alignment` should be false for working layers.** Setting it true for
staging would report every staging model as built off-plan.

## Entities

A suffix declares what a table is. Hunter compares that claim against how the
table behaves.

```yaml
entities:
  - kind: fact
    suffix: _fact
    requires_surrogate_key: true
    requires_unique_test: true
    requires_not_null_key_test: true
    expects_measures: true
    expects_date_grain: true
    expects_foreign_keys: true
    min_descriptive_attributes: 0
```

Shipped: `_fact`, `_dim`, `_xa` for aggregates, `_bridge`, `_snapshot`. Entities
merge on `kind`, so changing one suffix keeps the rest.

## Column naming

```yaml
column_naming:
  primary_key_suffix: _pk
  foreign_key_suffix: _fk
  natural_key_suffix: _natural_key
  date_suffix: _dt
  timestamp_suffix: _ts
  boolean_prefixes: [is_, has_]
  boolean_suffixes: [_flag]
```

These do more than name checking. Hunter uses them to work out what each column
is for, which is how entity inference and key-test checking work at all.

## Thresholds

```yaml
structure:
  max_model_lines: 400
  max_joins: 7
  forbid_select_star: true
  forbid_hardcoded_refs: true
  cte_name_pattern: "^[a-z][a-z0-9_]*$"

lineage:
  max_fanout: 12
  flag_dead_models: true
  flag_direct_source_joins_outside_staging: true
  flag_staging_bypass: true
  flag_model_rejoins: true

documentation:
  min_description_words: 3         # tables
  min_column_description_words: 1  # columns. "Order date" is a useful one
  stale_after_days: 180
  require_owner_in_meta: true
  owner_meta_keys: [owner, team]

testing:
  key_test_names: [unique, not_null]
  relationship_test_names: [relationships]
  weak_test_names: [at_least_one, dbt_utils.at_least_one]
  require_relationship_test_per_foreign_key: true
  require_unique_test_on_declared_grain: true

entity_inference:
  min_confidence_to_score: 0.7
  fact_min_foreign_keys: 2
  fact_min_measures: 1
  dimension_max_foreign_keys: 1
  dimension_min_attributes: 3
  aggregate_min_measures: 2
```

## Weights

```yaml
scoring:
  weights:
    testing: 18
    model_conformance: 15
    lineage_health: 13
    documentation: 13
    cross_layer_sync: 13
    conventions_structure: 13
    entity_modelling: 8
    performance_cost: 7
```

They must total 100 and every area must have one. Both are checked when the
configuration loads, so a partial list is an error rather than a silent
reweighting.

Any change from the house standard appears on the conventions page. See
[How the score works](scoring.md).

## Silencing a rule

Two places, for two purposes.

**In `hunter.yml`, for a whole repository.** "This rule does not apply to how we
work." It needs a reason, and the reason is published.

```yaml
rules:
  structure.select_star_from_source:
    enabled: false
    reason: staging deliberately takes every column and reshapes downstream
```

**In the register, for particular tables and with an end date.** "This is true,
and we are not fixing it yet."

```yaml
ignores:
  - rule: documentation.model_description_missing
    models: ['stg_legacy__*']
    reason: legacy staging, scheduled for removal this quarter
    expires: 2027-01-31
```

The difference matters. A rule disabled in `hunter.yml` never runs. A finding
silenced in the register still appears on the site, with its reason, and comes
back automatically on its expiry date. See [The register](register.md).

## Per-model overrides

For silencing one rule next to the model it concerns, rather than in a central
file:

```yaml
models:
  - name: wh_shop__legacy_fact
    meta:
      hunter:
        owner: commerce
```

## Checking what resolved

`hunter score` writes the resolved ruleset into `report.json` under
`conventions`, including every rule, whether it ran, and every difference from
the house standard. The site's conventions page is the readable version.

Any number on the site can be traced back to the rule that produced it. That is
what makes the score survive being challenged.
