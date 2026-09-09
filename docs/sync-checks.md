# Check the layers agree

<p class="lede">Three small CI checks, each answering one question about
whether one layer has drifted from another. Separate from the score, and
separate from each other.</p>

<div class="cards">
  <div>
    <span class="tag">crosslayer rules</span>
    <b>LookML sync</b>
    <p><em>Does the reporting layer still match the tables?</em><br>
    A field reading a column that no longer exists breaks in a client's
    dashboard, not in the pull request that removed it.</p>
  </div>
  <div>
    <span class="tag">droughty rules</span>
    <b>Droughty sync</b>
    <p><em>Has the generated schema been applied, and is it current?</em><br>
    A generated test that never reached dbt is a test everyone believes is
    running. Nothing is checking what they think is checked.</p>
  </div>
  <div>
    <span class="tag">alignment + conformance rules</span>
    <b>Modelling sync</b>
    <p><em>Does what exists match what was designed and asked for?</em><br>
    A table built with no design has no agreed grain and no owner. A design
    nobody built is a promise the business is still waiting on.</p>
  </div>
</div>

## Why three, and not one

| | |
|---|---|
| **They fail for different reasons** | A renamed column is an analytics engineer's morning. An undesigned table is a conversation with whoever owns the design |
| **They become available at different times** | A repository with no DBML can run LookML sync on day one. Modelling sync has nothing to read yet |
| **Small gates get adopted** | A team will make one specific check required long before it accepts a whole score as one. One large gate gets an exemption |

<div class="key" markdown>
**A sync check and the score can never disagree.** Each check is a slice of
the same rules the score already runs, reading the same findings. Nothing here
computes a second opinion.
</div>

## What each one reads

A check whose sources are missing reports **skipped**, never **passed**.
Adding the source turns the check on; it is not a breaking change.

| Check | Needs | Rules | Sharper with |
|---|---|---|---|
| LookML sync | `manifest.json`, LookML files | 6 `crosslayer.*` | |
| Droughty sync | `manifest.json`, committed Droughty output | 8 `droughty.*` | |
| Modelling sync | `manifest.json`, DBML design files | 8 `alignment.*`, 10 `conformance.*` | A business model diagram |

That is 32 of the 77 rules. The rest belong to the score rather than to drift
between layers.

## In CI

The workflow `hunter init` writes already runs all three on every pull request,
alongside the score. See [Run it on every pull request](ci.md). Each check is
also its own composite action, so a repository that wants one without the
others can add just that one.

```yaml
name: Layer sync

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read
  pull-requests: write

jobs:
  lookml:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: sav-sus/Hunter/actions/lookml-sync@v0.1.0
        with:
          fail-on: high

  droughty:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: sav-sus/Hunter/actions/droughty-sync@v0.1.0

  modelling:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: sav-sus/Hunter/actions/modelling-sync@v0.1.0
```

Three separate jobs on purpose. One drifted check then does not hide the other
two, and each shows as its own line in the pull request.

<div class="key" markdown>
**Start every one on `fail-on: never`.** It reports and never fails. A check
that fails builds in its first week gets switched off in its second, and then
none of the rest of this matters.
</div>

| `fail-on` | Behaviour |
|---|---|
| `never` | Reports only. The default |
| `high` | Fails on a high-severity drift, such as a report field reading a column that no longer exists |
| `any` | Fails on any drift, including tidy-ups |

### Inputs

The same seven on all three.

| Input | Default | What it does |
|---|---|---|
| `fail-on` | `never` | `never`, `high` or `any` |
| `working-directory` | `.` | The repository root to read |
| `config` | | Path to `hunter.yml`. Found automatically if omitted |
| `manifest` | | Path to `manifest.json`, if not where the ruleset says |
| `comment` | `true` | Post or update a pull request comment |
| `hunter-version` | `0.1.0` | Which Hunter version to install. Never use `@main` |
| `python-version` | `3.12` | Which Python to run under |

### Outputs

| Output | What it is |
|---|---|
| `verdict` | `in sync`, `drifted`, `skipped` or `nothing to compare` |
| `checked` | How many checks ran |
| `failed` | How many of them failed |
| `result` | Path to the JSON result |

Each action writes a step summary, posts one comment per check edited in place,
and uploads its JSON and Markdown as an artifact.

## On the command line

```bash
hunter sync                  # all three
hunter sync lookml           # one
hunter sync modelling --fail-on any
hunter sync --out out/sync.json --summary out/sync.md
```

```
  LookML sync: drifted
  Does the reporting layer still match the tables?
  Drifted. 5 of 14 checks failed.

    --    3 of 6   Every built table has a LookML view
           wh_commerce__forecast_fact, wh_commerce__legacy_fact, wh_master__product_dim
    ok    3 of 3   Every LookML view points at a table that exists
    --    2 of 3   Every LookML field points at a real column
           wh_commerce__order_fact
```

The statements come before the findings on purpose. "3 of 6 tables have a view"
is what a reader wants first; the rule names are how they fix it.

??? note "The JSON result"

    One entry per check, carrying the same version stamp every Hunter report
    does: a result compared against one from a different Hunter version is not
    a comparison.

    ```json
    {
      "checks": [
        {
          "key": "lookml",
          "title": "LookML sync",
          "verdict": "drifted",
          "headline": "Drifted. 5 of 14 checks failed.",
          "ran": true,
          "checked": 14,
          "passed": 9,
          "failed": 5,
          "in_sync_percent": 64.3,
          "by_severity": { "high": 1, "low": 4 },
          "statements": [
            {
              "statement": "Every built table has a LookML view",
              "held": 3,
              "of": 6,
              "let_down_by": ["wh_commerce__forecast_fact"]
            }
          ],
          "findings": [{ "rule": "crosslayer.field_references_missing_column" }]
        }
      ]
    }
    ```

## Where they show up in the report

The dashboard groups the same statements under the same headings, so the
report and the CI check cannot tell you different things.

| Sync check | Dashboard section |
|---|---|
| LookML sync | Warehouse to Looker |
| Droughty sync | Droughty |
| Modelling sync | Design to build |

[See it on the example dashboard](example/dashboard.md).

## What they do not do

These check drift between layers. They are not the score, and they are not a
substitute for it: naming, testing, documentation, lineage and entity modelling
all sit outside them.

Run [the full action](ci.md) as well, on `advisory`, and let these three be the
checks that can fail.
