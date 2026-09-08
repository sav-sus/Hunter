# Rittman Hunter

**Point it at an analytics repository and it tells you what state the repository
is in.**

Hunter reads dbt, LookML, your data model design and your git history, then
reports on them. It changes nothing: no commits, no pull requests, no writes to
your warehouse.

```
89.6 / 100    Well maintained. Safe to build on

 90.4  A  What is checked automatically            38 findings
 87.3  A  Does what was built match the design    190 findings
 92.6  A  How the tables fit together              53 findings
 77.2  B  What is written down                    135 findings
 86.7  A  Do the reports still match the data     183 findings
 98.3  A  Are the house rules followed             48 findings
 98.3  A  Are the tables the shape they claim       7 findings
    -  -  What it costs to run                  not measured

Missing everywhere it was checked:
  63 of 63  Who owns what
  54 of 54  Do the reports still match the data
```

Two seconds on a 280-model repository. No warehouse credential needed.

That is the terminal output. The report itself is a dashboard: the score, what
nobody has decided, where the points are going, how much of the plan is real,
which tables everything is built on, and what to fix first, in one screen.

```bash
hunter dashboard          # one self-contained HTML file, ~75 KB
```

Every chart is SVG generated in Python, so the file carries its own stylesheet,
charts and logo. It opens with no network and nothing beside it, and two runs of
one commit produce identical bytes.

| | |
|---|---|
| **See the dashboard** | [`docs/example/dashboard.html`](docs/example/dashboard.html), regenerated on every change |
| **Documentation, published** | https://rittman-hunter.readthedocs.io |
| **Documentation, in this checkout** | [`docs-html/index.html`](docs-html/index.html), built HTML. Source in [`docs/`](docs) |
| **See real output** | [`docs/example/`](docs/example/index.md), regenerated on every change |
| **Try it in a minute** | [Below](#try-it-in-a-minute) |
| **Why it is built this way** | [`.doc/`](.doc/README.md), the product record |
| **A worked example project** | [`examples/tiny-shop/`](examples/tiny-shop/README.md) |
| **Licence** | Proprietary, Rittman Analytics. Not open source |

Rittman Hunter is a Rittman Analytics product.

## The problem

Eight things nobody can answer today without reading a whole repository by
hand.

| | |
|---|---|
| People merge pull requests without seeing the debt they create | Found weeks later during unrelated work |
| A lead cannot see across a repository once the team grows | Review depends on one person reading every change |
| Working steps are not distinguished from finished tables | Intermediate tables end up feeding reports |
| Nothing attributes a table or a gap to whoever made it | Nobody can be asked to fix anything |
| Modelling correctness is unchecked | Grain errors and double counting, found days later |
| dbt and the reporting layer drift apart | A renamed column breaks a dashboard, and the client finds it |
| Nothing shows what a repository costs to run | Money spent on tables nothing reads |
| Nothing measures whether quality improves | "Are we getting anywhere" has no evidence behind it |

Most of these sit at the joins: between the design and the repository, between
the repository and the reporting layer, and between one sprint and the next.
Existing dbt tools work inside dbt and stop there. Hunter wraps them as inputs
where it can and spends its own effort on the joins.

Full statement: [`.doc/01-the-problem.md`](.doc/01-the-problem.md).

## What it does about it

**A score out of 100**, with a grade per area, every deduction traceable to a
rule, an object and a line. The number is the headline; the reading of it sits
beneath, never in place of it.

**A reconciliation**, one row per entity, showing whether the business asked for
it, whether it was designed, whether it was built, and whether it is live. A
non-technical reader can act on this page without opening a file.

**A list of what needs doing**, ranked by how much the score would recover, each
item saying what breaks if it is left.

**A dashboard**, one screen, in Rittman Analytics colours. Nine bands, each
answering one question, every figure traceable to a rule and a finding. Behind
it sit twelve detail pages, readable by an engineer and by someone who has never
seen SQL.

**A pull request comment**, short, specific to the change, with what it reaches.

### Every finding says what breaks

Not this:

> high severity: relationships test missing

This:

> Nothing checks that these references in daily store performance point at rows
> that exist. Where they do not, joined figures come out low and the rows simply
> vanish.

Those lines are templates filled from each finding's own evidence. Nothing is
written by a language model, so every sentence has a deterministic check behind
it.

### It says what it did not check

A score is only as good as what went into it. An area Hunter could not measure
is excluded, its weight shared across the rest, and named on a page of its own.
It never scores an unmeasured area as zero, and never quietly scores out of less
than 100.

### It reports systemic gaps above the number

"No table names an owner, 63 of 63" is one decision nobody has taken, not 63
separate defects. A weighted mean buries that, so it is listed separately, above
the score.

## Try it in a minute

```bash
git clone https://github.com/sav-sus/Hunter
cd Hunter
uv sync --all-extras

uv run hunter score examples/tiny-shop
uv run hunter align examples/tiny-shop
uv run hunter explain wh_shop__customer_dim examples/tiny-shop
uv run hunter docs build examples/tiny-shop --out /tmp/example-site
open /tmp/example-site/_built/index.html
```

[`examples/tiny-shop`](examples/tiny-shop) is a working project laid out the way
a Rittman Analytics engagement lays one out: nine tables with one deliberate
flaw each, a design, a business model, a layered LookML project and generated
schema output. It scores 88.2 and exercises 28 of Hunter's 77 rules.

## On your own repository

```bash
uv tool install "rittman-hunter[site] @ git+https://github.com/sav-sus/Hunter@v0.1.0"

cd your-analytics-repo
hunter init          # detect the layout, write .hunter/hunter.yml and register.yml
hunter score         # score it, write out/report.json
hunter baseline      # record where it starts, so it only has to improve
hunter docs build    # build the site
```

`hunter init` fills the register with the tables Hunter would flag, each with a
blank reason. Filling in reasons against a list works; being handed an empty
file and asked to document your exceptions does not.

Full guide: [Installing](https://rittman-hunter.readthedocs.io/en/latest/install/)
and [First run](https://rittman-hunter.readthedocs.io/en/latest/quickstart/).

## What it reads

A dbt `manifest.json` is required. Everything else adds an area to the score
rather than being a prerequisite.

| Source | What it adds | Needs a credential |
|---|---|---|
| `manifest.json` | Tables, columns, tests, lineage | No |
| DBML design files | Does what was built match what was designed | No |
| A conceptual Mermaid diagram | Does the design match what the business asked for | No |
| LookML | Will a renamed column break a report | No |
| Committed Droughty output | Are the generated tests and descriptions still applied | No |
| Git history | Who wrote what, and what changed in a window | No |
| `catalog.json` | Column types, which sharpen two checks | No |
| BigQuery metadata | What is deployed, and what it costs | Yes. Not built |

## Commands

| Command | What it does |
|---|---|
| `hunter score` | Score the repository, write `report.json` |
| `hunter align` | What was designed against what exists |
| `hunter check --pr 1184` | Build the pull request comment for a change |
| `hunter explain <table>` | Everything known about one table |
| `hunter showcase --days 14` | What changed in a window, and what it cost |
| `hunter dashboard` | Write the dashboard as one self-contained HTML file |
| `hunter docs build` | Generate and build the site, dashboard included |
| `hunter diagram --level conceptual` | Print one Mermaid diagram |
| `hunter baseline` | Record the starting score |
| `hunter init` | Set up a repository |
| `hunter rules` | List every rule |

Every command is a thin wrapper over one pipeline, and the GitHub Action calls
these and nothing else. A run in CI and a run on a laptop give the same answer
by construction rather than by discipline.

## In CI

```yaml
name: Hunter
on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read
  pull-requests: write

jobs:
  hunter:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: sav-sus/Hunter@v0.1.0
        with:
          mode: advisory
          publish: ${{ github.event_name == 'push' }}
```

`fetch-depth: 0` matters: attribution and window reports need full history, and
the default shallow checkout has none.

Advisory mode never fails a build, and it is the default. A tool that fails
builds in its first week gets switched off in its second.

## Two files in your repository

**`.hunter/hunter.yml`** says what correct looks like: layers, naming, weights.
It extends a version-pinned house standard, and every difference is published on
the site with the reason given for it.

**`.hunter/register.yml`** records what the team has decided about particular
tables: that one is temporary on purpose, that an off-plan build is accepted, who
owns what, what one row means. Plain information needs no reason. An exception or
an approval needs one, and a silenced rule needs an end date, so nothing goes
quiet for good.

Nothing in the register hides a finding. An approved exception still appears on
the site with its reason and its review date.

## Where things are

| Path | What it is |
|---|---|
| [`src/hunter/`](src/hunter) | The package. 48 modules |
| [`src/hunter/brand.py`](src/hunter/brand.py) | The Rittman Analytics palette, from the published design tokens |
| [`examples/tiny-shop/`](examples/tiny-shop) | A working example project |
| [`docs/`](docs) | The published documentation |
| [`.doc/`](.doc/README.md) | Why it is built this way: problem, decisions, roadmap, what is not built |
| [`tests/`](tests) | 544 tests, including a golden file pinning the example's score |
| [`action.yml`](action.yml) | The composite GitHub Action |

## What it will never do

Hunter never modifies code, never opens a commit or a pull request, and never
writes to a warehouse. Where warehouse access is granted it is read-only and
scoped to metadata and job history. No row-level data is read, stored or
published.

Those are licence terms, not only design intent.

## State

| | |
|---|---|
| Version | 0.1.0.dev0, unreleased |
| Milestone | M0 complete, plus four additions |
| Rules | 77 across 7 scored areas |
| Tests | 544 |
| Run time | 2 seconds on 280 models |

Roadmap: [`.doc/07-roadmap.md`](.doc/07-roadmap.md).
What is not built and why: [`.doc/08-not-built.md`](.doc/08-not-built.md).

## Developing

```bash
uv sync --all-extras
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

The example's score is pinned in `tests/golden/tiny-shop.json`, so a change to
the arithmetic shows up as a diff on a committed file rather than as a surprise
in somebody's report. After an intended change:

```bash
uv run python -m tests.regenerate_golden      # the pinned report
uv run python scripts/build_docs_pages.py     # the rules reference and example
uv run python scripts/build_docs_site.py      # the browsable HTML
```

and all three diffs are part of the review.

`scripts/check_no_client_content.py` fails on client-identifying strings in
tracked files. Hunter is developed by running it against real client
repositories, so that rule is enforced rather than remembered.

Full guide: [Contributing](https://rittman-hunter.readthedocs.io/en/latest/contributing/).

## Licence

Proprietary, all rights reserved. See [LICENSE](LICENSE). Not open source.
