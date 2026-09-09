# Configuration

<p class="lede">Two files. Hunter ships with the Rittman Analytics standard and
no opinions of its own beyond it, so every layer name, convention, threshold and
weight is declared rather than built in.</p>

<div class="cards">
  <div>
    <span class="tag">Rarely changes</span>
    <b>.hunter/hunter.yml</b>
    <p>What correct looks like: layers, naming, thresholds, weights, which rules
    are on. Owned by the engagement lead.</p>
  </div>
  <a href="../register/">
    <span class="tag">Changes constantly</span>
    <b>.hunter/register.yml</b>
    <p>What your team decided about particular tables: what is temporary, what
    is approved, who owns what.</p>
  </a>
</div>

## Where the files go

Both in `.hunter/` at the **repository root**. `hunter init` writes them there.

```
your-repo/
  .hunter/
    hunter.yml        <- here
    register.yml      <- and here
  analytics_warehouse/
    dbt_project.yml
    models/  lookml/  docs/  target/
  manifest.lkml
```

<div class="key" markdown>
**Not beside `dbt_project.yml`.** Every path in `hunter.yml` is resolved from
the repository root, so a copy inside `analytics_warehouse/` would have to say
`dbt_project_dir: analytics_warehouse` while living in that directory. The root
is also the only place that can see both the dbt project and anything outside
it.
</div>

Worked copies of both, commented option by option, are in the example project:
[`hunter.yml`](https://github.com/sav-sus/Hunter/blob/main/examples/tiny-shop/.hunter/hunter.yml)
and
[`register.yml`](https://github.com/sav-sus/Hunter/blob/main/examples/tiny-shop/.hunter/register.yml).

## Five levels

Each overrides the one above.

| Level | Where | Owned by | Changes |
|---|---|---|---|
| Built-in defaults | Shipped in the package | Whoever maintains Hunter | With a release |
| House standard | `ra-house-1.yml`, version-pinned | Rittman Analytics delivery leadership | With a release, and a project opts in |
| Project | `.hunter/hunter.yml` | The engagement lead | Rarely |
| Register | `.hunter/register.yml` | Whoever is doing the work | Constantly |
| Per model | `meta.hunter` in a schema file | The model's author | With the model |

Hunter records where every resolved value came from. Not as a debugging aid:
every difference from the standard is published on the report's rules page with
the reason given, so the report shows how far the repository sits from the
standard.

## The minimum

This is all most repositories need. `hunter init` writes it with your paths
filled in.

```yaml
extends: ra-house@1      # pinned, so the standard changing does not move your score

paths:
  dbt_project_dir: analytics_warehouse   # from the repository root
  manifest: target/manifest.json         # from dbt_project_dir
  dbml:
    - docs/data_model_design/*.dbml
  conceptual_diagram: docs/data_model_design/conceptual_model.mermaid
  logical_diagram: docs/data_model_design/logical_model.mermaid
  lookml:
    - lookml/**/*.lkml
  droughty_dbml:
    - docs/db_docs/*.dbml

pull_request:
  mode: advisory         # advisory, ratchet or gate
```

Unknown keys are errors. A typo must not silently switch off a rule.

## Turning a rule off, or changing what it costs

Needs a reason, and the reason is published.

```yaml
rules:
  structure.select_star_from_source:
    enabled: false
    reason: staging deliberately takes every column and reshapes downstream

  testing.relationship_test_missing:
    points: 2.0
    reason: unresolved joins have caused two reporting incidents this year

  documentation.owner_missing:
    severity: low
    reason: ownership is tracked in the service catalogue, not in dbt meta
```

`hunter rules` lists every rule id. There are two places to silence something,
for two different purposes:

| Where | Means | Behaviour |
|---|---|---|
| `hunter.yml` | "This rule does not apply to how we work" | The rule never runs |
| [The register](register.md) | "This is true, and we are not fixing it yet" | Still appears on the report, with its reason, and comes back on its expiry date |

## Everything else

The standard already sets all of this. These are the blocks to reach for when a
repository needs to differ.

### Layers Hunter finds on its own

The standard declares staging, integration, warehouse, seeds, reverse ETL and
AI. A directory under `models/` that none of them claims becomes a layer named
after the directory, with a prefix where every model in it shares one. The
report marks it *found, not declared*, and the "what was not checked" page
names it.

A found layer carries no rules: no required descriptions, owners or tests, and
no place in the pipeline order. Declare it here to say what it should look like.
Until then, nothing needs editing for its tables to appear on the dashboard.

??? note "Branding: names and the logo on the report"

    ```yaml
    branding:
      site_name: Repository health
      client_name: Tiny Shop            # shown before the site name
      logo_url: https://<organisation>.github.io/<repository>/assets/rittman-analytics.png
      site_url: https://<organisation>.github.io/<repository>/
    ```

    `site_url` is where the built site is published. When set, the pull request
    comment links to the live dashboard as well as to the run that produced
    the comment. See [where the comment's link goes](ci.md#where-the-comments-link-goes).

    `logo_url` puts the logo at the top of the pull request comment and the
    sync summaries. It is off by default: GitHub only renders images it can
    fetch, and a private repository's file URL shows as a broken image. See
    [how the checks are named](ci.md#how-the-checks-are-named-and-the-logo).

??? note "Layers: what is allowed in each stage"

    ```yaml
    layers:
      - name: warehouse
        paths: ["models/warehouse/**", "models/wh_*/**"]
        prefix: wh_
        materialisations: [table, incremental]
        persistence: permanent
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

    Layers merge on their name, so overriding one keeps the others.

    | Field | What it does |
    |---|---|
    | `paths` | Glob patterns that place a model in this layer |
    | `prefix` | Required name prefix. Omit for no requirement |
    | `materialisations` | Permitted materialisations. Empty means any |
    | `persistence` | `temporary` or `permanent`. Feeds the classification. `verified` is a register word, not a layer one |
    | `pipeline_stage` | Position in the flow. Reading two stages below is a bypass. 0 means outside the flow |
    | `may_reference` | Layers this one may read. Empty means any |
    | `may_reference_sources` | Whether it may read a raw source directly |
    | `requires_*` | What is expected of a model in this layer |
    | `expected_entity_kinds` | Which entity types belong here. Drives the suffix check |
    | `in_alignment` | Whether this layer holds modelled entities that belong in the reconciliation |

    **Two are easy to get wrong.** `pipeline_stage` is not the order layers
    appear in the file: an earlier version of Hunter inferred it from
    declaration order and produced "skips the seeds layer to read a warehouse
    table". And `in_alignment` should be false for working layers, or every
    staging model gets reported as built off-plan.

??? note "Entities: what a suffix claims"

    Hunter compares the claim against how the table behaves.

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

    Shipped: `_fact`, `_dim`, `_xa` for aggregates, `_bridge`, `_snapshot`.
    Entities merge on `kind`, so changing one suffix keeps the rest.

??? note "Column naming: how Hunter works out what a column is for"

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

    These do more than name checking. Entity inference and key-test checking
    both depend on them, so getting them wrong weakens several rules at once.

??? note "Thresholds: structure, lineage, documentation, testing, inference"

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

??? note "Weights: how much each area can move the total"

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
      exposure_weighting: true
      fail_under: null           # gate mode fails below this
      fail_on_regression: false  # ratchet mode
      min_confidence_to_score: 0.7
    ```

    They must total 100 and every area must have one. Both are checked when the
    configuration loads, so a partial list is an error rather than a silent
    reweighting. See [the score](scoring.md).

??? note "Per-model overrides, next to the model itself"

    ```yaml
    models:
      - name: wh_commerce__legacy_fact
        meta:
          hunter:
            owner: commerce
    ```

## Checking what resolved

`hunter score` writes the resolved ruleset into `report.json` under
`conventions`: every rule, whether it ran, and every difference from the
standard. The report's rules page is the readable version.

Any number on the report traces back to the rule that produced it, which is
what makes the score survive being challenged.
