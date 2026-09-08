# Rittman Hunter

Repository intelligence for analytics repositories containing dbt and LookML.

Hunter reads a repository and answers four questions a team lead cannot answer
today without reading the whole thing by hand:

1. What is in here, and which parts are working steps rather than finished
   tables?
2. Who built each part, and what did each merged pull request add or cost?
3. Is the modelling right: are facts facts, are dimensions dimensions, is
   anything undocumented or untested?
4. Do the layers agree: the business model, the design, the repository, the
   reporting layer and production?

It produces a score out of 100 with a grade per area, a list of what needs
doing, and a site readable by an engineer and by someone who has never opened a
SQL file.

## What it needs

A dbt `manifest.json` and nothing else. Everything beyond that adds an area to
the score rather than being a prerequisite, and anything absent is reported as
not checked rather than counted as passing.

| Source | Adds |
|---|---|
| `manifest.json` | Models, columns, tests, lineage. Required |
| DBML design files | Does what was built match what was designed |
| A conceptual Mermaid diagram | Does the design match what the business asked for |
| LookML | Will a column rename break a report |
| Committed Droughty output | Are the generated tests and descriptions still applied |
| Git history | Who wrote what, and what changed in a window |
| BigQuery metadata | What is actually deployed, and what it costs. Not yet built |

No warehouse credential is needed for any of the above except the last.

## Getting started

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

## Commands

| Command | What it does |
|---|---|
| `hunter score` | Score the repository and write `report.json` |
| `hunter align` | What was designed against what exists, on its own |
| `hunter check --pr 1184` | Build the pull request comment for a change |
| `hunter explain wh_sales__order_fact` | Everything known about one table |
| `hunter showcase --days 14` | What changed in a window, and what it cost |
| `hunter docs build` | Generate and build the site |
| `hunter diagram --level conceptual` | Print one Mermaid diagram |
| `hunter baseline` | Record the starting score |
| `hunter rules` | List every rule Hunter can report |

Every command is a thin wrapper over one pipeline, and the GitHub Action calls
these commands and nothing else. A run in CI and a run on a laptop give the same
answer by construction rather than by discipline.

## The two files a repository needs

`.hunter/hunter.yml` says what correct looks like: the layers, the naming, the
weights. It extends a version-pinned house ruleset, and every difference from
that ruleset is published on the site with the reason given for it.

`.hunter/register.yml` records what the team has decided about particular
tables: that one is temporary on purpose, that an off-plan build is accepted,
who owns what, what one row means. Plain information needs no reason. An
exception or an approval needs one, and a silenced rule needs an end date as
well, so nothing goes quiet for good.

Nothing in the register hides a finding. An approved exception still appears on
the site with its reason and its review date.

## How the score works

Each area's score is the share of its checks that passed, weighted by how much
depends on the table in question. A missing test on a table feeding twelve
report fields costs more than the same gap on one nothing reads.

Areas with nothing to measure are excluded and their weight shared across the
rest, with the reason stated. A repository with no warehouse access is still
scored out of 100 rather than out of 93.

| Score | What it means |
|---|---|
| 85 to 100 | Well maintained. Safe to build on |
| 70 to 84 | Sound, with known gaps |
| 55 to 69 | Workable but accumulating risk |
| 40 to 54 | Fragile. Changes are likely to break things |
| 0 to 39 | Unmanaged. Treat findings as a remediation backlog |

The number is always the headline and the reading always sits beneath it, never
in place of it.

Alongside the score, Hunter reports **systemic gaps**: rules that failed on
every table they were applied to. "No table in the warehouse layer names an
owner, 63 of 63" is one decision nobody has taken rather than 63 defects, and a
weighted mean buries it. Those are listed above the number.

## Every finding says what breaks

Not "high severity: relationships test missing", but:

> Nothing checks that these references in daily store performance point at rows
> that exist. Where they do not, joined figures come out low and the rows simply
> vanish.

Every such line is a template held with the rule and filled from that finding's
own evidence. Nothing is generated, so every sentence traces back to a
deterministic check.

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

`fetch-depth: 0` matters: attribution and showcase windows need full history,
and the default shallow checkout has none.

Advisory mode never fails a build, and it is the default. A tool that fails
builds in its first week gets switched off in its second.

## What it will not do

Hunter never modifies code, never opens a commit or a pull request, and never
writes to a warehouse. Where warehouse access is granted it is read-only, and
it reads metadata and aggregate counts: no row-level data is read, stored or
published.

## Developing

```bash
uv sync --all-extras
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

The fixture at `tests/fixtures/tiny-project` is eight tables with one
deliberate flaw per finding class. Its score is pinned in
`tests/golden/tiny-project.json`, so a change to the arithmetic shows up as a
diff on a committed file rather than as a surprise in someone's report. After an
intended change:

```bash
uv run python -m tests.regenerate_golden
```

and the diff is part of the review.

`scripts/check_no_client_content.py` fails on client-identifying strings in
tracked files. Hunter is developed by running it against real client
repositories, so that rule is enforced rather than remembered.

## Licence

Proprietary. See [LICENSE](LICENSE). Not open source.
