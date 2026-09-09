# Commands

<p class="lede">Thirteen commands. Every one is a thin wrapper over the same
pipeline, and the Rittman Analytics Actions call these and nothing else, so CI
and your laptop give the same answer.</p>

| Command | What it does |
|---|---|
| [`score`](#hunter-score) | Score the repository, write `report.json` |
| [`dashboard`](#hunter-dashboard) | The report as one self-contained HTML file |
| [`docs build`](#hunter-docs-build) | The dashboard plus every detail page behind it |
| [`sync`](#hunter-sync) | Has one layer drifted from another. Three checks |
| [`align`](#hunter-align) | What was designed against what exists |
| [`explain`](#hunter-explain) | Everything known about one table |
| [`check`](#hunter-check) | Build the pull request comment for a change |
| [`showcase`](#hunter-showcase) | What changed in a window, and what it cost |
| [`diagram`](#hunter-diagram) | Print one Mermaid diagram |
| [`baseline`](#hunter-baseline) | Record where the repository starts |
| [`init`](#hunter-init) | Set up a repository |
| [`rules`](#hunter-rules) | List every rule |
| [`version`](#hunter-version) | The three versions stamped on every report |

Every command takes the repository as its first argument, defaulting to the
current directory.

| Common option | What it does |
|---|---|
| `--config`, `-c` | Path to `hunter.yml`. Found automatically if omitted |
| `--manifest`, `-m` | Path to `manifest.json`, if not where the ruleset says |
| `--out`, `-o` | Where to write the output |

| Exit code | Meaning |
|---|---|
| 0 | The run completed. In advisory mode this is always the answer |
| 1 | The run completed and the score failed the configured gate |
| 2 | The run could not complete: a missing manifest, an invalid ruleset |

<div class="key" markdown>
**The difference between 1 and 2 matters in CI.** A 2 is a setup problem. A 1
is the tool doing its job.
</div>

## `hunter score`

```bash
hunter score
hunter score . --manifest ../target/manifest.json
hunter score . --out reports/today.json --quiet
```

Prints the score, a line per area, any systemic gaps and the finding counts.

| Option | What it does |
|---|---|
| `--house` | Which Rittman Analytics standard to measure against, e.g. `ra-house@1` |
| `--quiet`, `-q` | Write the report and print nothing |
| `--no-git` | Skip history. Faster, but nothing is attributed |

## `hunter dashboard`

```bash
hunter dashboard
hunter dashboard . --out /tmp/report.html
```

The whole report in one screen and one file. The stylesheet, every chart and
the logo are inlined, so it needs nothing installed and nothing beside it.

The one exception is the diagram library, which is fetched from a CDN at a
pinned version. Where it does not arrive, the diagram source is shown as text
with a note saying why, and nothing else on the page depends on it.

[See one](example/dashboard.md), or read what is on it.

## `hunter docs build`

```bash
hunter docs build
hunter docs build . --out /tmp/site
hunter docs build . --markdown-only
```

Twelve pages plus one per table, with `dashboard.html` as the front door.

| Option | What it does |
|---|---|
| `--markdown-only` | Write the pages and stop, without running MkDocs |

Needs the `site` extra for the build step. The markdown and the dashboard are
written either way.

## `hunter sync`

```bash
hunter sync                  # all three
hunter sync lookml           # one
hunter sync modelling --fail-on any
hunter sync --out out/sync.json --summary out/sync.md
```

Three drift checks, each a slice of the same rules the score runs.

| Check | The question |
|---|---|
| `lookml` | Does the reporting layer still match the tables? |
| `droughty` | Has the generated schema been applied, and is it current? |
| `modelling` | Does what exists match what was designed and asked for? |

| Option | What it does |
|---|---|
| `--fail-on` | `never` (default), `high` or `any`. A skipped check never fails |
| `--out`, `-o` | Write the result as JSON |
| `--summary` | Write a Markdown summary, for a CI step summary |
| `--root`, `-r` | The repository to read. Default the current directory |

A check whose sources are missing reports "skipped", never "passed". Each has
its own GitHub Action: [the three sync checks](sync-checks.md).

## `hunter align`

```bash
hunter align
hunter align . --domain commerce
```

```
    56  Designed and delivered        Working as intended.
     6  Built, switched off           The code exists but is switched off...
     8  Built off-plan                Delivered but never designed...
    10  Designed, not started         On the plan, no work done yet.
    71  On the business model only    Agreed with the business...

  Business model designed: 33.6% (36 of 107)
  Design built:            77.8% (56 of 72)
```

Then a line per entity with its state and the table behind it.

## `hunter explain`

```bash
hunter explain wh_master__customer_dim
```

What it is, what one row means, who owns it, how it behaves against what its
name claims, its columns and tests, what depends on it, a diagram of its blast
radius, and every finding against it. Name it wrong and Hunter suggests near
matches.

## `hunter check`

```bash
hunter check --pr 1184
hunter check . --base origin/main --previous-report before.json
```

Writes the comment body to a file. Posting is the Action's job.

| Option | What it does |
|---|---|
| `--pr` | The pull request number, for the footer |
| `--base` | What the change is measured against. Default `origin/main` |
| `--previous-report` | A `report.json` from before the change, for a true before-and-after |

Without a previous report the comment lists findings on the files the change
touched, which is a superset of what the change introduced. It says so rather
than presenting the two as the same thing.

## `hunter showcase`

```bash
hunter showcase --days 14
```

Merged pull requests, tables added, changed and removed, reporting changes,
design changes, tickets referenced, and the debt sitting on the tables that
window touched.

That last section is always present. A report listing only what was delivered
is marketing rather than reporting.

## `hunter diagram`

```bash
hunter diagram --level conceptual
hunter diagram --level blast --model wh_commerce__order_fact
```

| Level | What it draws |
|---|---|
| `conceptual` | Business entities, coloured by their real state |
| `logical` | Designed entities, attributes grouped by what they are for |
| `physical` | Built tables, with real types and how they are built |
| `lineage` | The graph, collapsed by layer and area. Add `--domain` for detail |
| `blast` | What a change to one table reaches. Needs `--model` |

## `hunter baseline`

```bash
hunter baseline
hunter baseline . --note "Recorded at the start of the engagement"
```

Writes `.hunter/baseline.json`. Commit it, so later runs measure movement
rather than absolutes.

## `hunter init`

```bash
hunter init
hunter init . --force
```

Detects the layout and says what it could not find. Where a manifest is
present, it also scores the repository and fills the register with the tables it
would flag, each with a blank reason.

Writes three files: `.hunter/hunter.yml`, `.hunter/register.yml` and
`.github/workflows/hunter.yml`. The workflow runs the score and the three sync
checks on every pull request, and publishes the dashboard to GitHub Pages on
every push to main. See [Run it on every pull request](ci.md).

| Option | What it does |
|---|---|
| `--manifest-source parse\|committed\|artifact` | How CI gets dbt's manifest. Kept in `hunter.yml` under `ci`, so a rerun keeps it |
| `--manifest-path` | For `committed`: where the manifest is kept. Default `.hunter/ci-manifest.json.gz` |
| `--manifest-workflow`, `--manifest-artifact` | For `artifact`: the dbt workflow file and the artifact it uploads |
| `--force` | Overwrite edited files, keeping each as `<name>.bak` |

Rerunning init refreshes files that are exactly as it last wrote them, and
refuses to touch edited ones without `--force`, naming each and what would be
lost. Every generated file starts with a fingerprint line that makes this
cheap to tell.


## `hunter rules`

```bash
hunter rules
```

```
alignment.built_disabled          low      0.5  Does what was built match the design
alignment.built_off_plan          medium   1.2  Does what was built match the design
...
77 rules.
```

Full reference, with the consequence line for each: [Every rule](reference/rules.md).

## `hunter version`

```bash
hunter version
```

```json
{ "hunter": "0.1.0", "house_ruleset": "1", "score_model": "1" }
```

The score model version is what lets a later run tell real change from movement
caused by upgrading Hunter.
