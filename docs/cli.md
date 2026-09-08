# Commands

`hunter` is the only entry point. Every command is a thin wrapper over one
pipeline, and the Rittman Analytics GitHub Action calls these and nothing else, so a run in CI and a run on your laptop give the same answer.

## Common options

| Option | What it does |
|---|---|
| `--config`, `-c` | Path to `hunter.yml`. Found automatically if omitted |
| `--manifest`, `-m` | Path to `manifest.json`, if not where the ruleset says |
| `--out`, `-o` | Where to write the output |

Every command takes the repository as its first argument, defaulting to the
current directory.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | The run completed. In advisory mode this is always the answer |
| 1 | The run completed and the score failed the configured gate |
| 2 | The run could not complete: a missing manifest, an invalid ruleset |

The distinction between 1 and 2 matters in CI. A 2 is a setup problem; a 1 is
the tool doing its job.

---

## `hunter score`

Score the repository and write `report.json`.

```bash
hunter score
hunter score . --manifest ../target/manifest.json
hunter score . --out reports/today.json --quiet
```

| Option | What it does |
|---|---|
| `--house` | Which Rittman Analytics house standard to measure against, e.g. `ra-house@1` |
| `--quiet`, `-q` | Write the report and print nothing |
| `--no-git` | Skip history. Faster, but nothing is attributed |

Prints the score, a line per area, any systemic gaps, and the finding counts.

---

## `hunter align`

What was designed against what exists, on its own.

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

---

## `hunter explain`

Everything Hunter knows about one table.

```bash
hunter explain wh_shop__customer_dim
```

Covers what it is, what one row means, who owns it, what it is named as against
how it behaves, its columns and their tests, what depends on it, a diagram of
its blast radius, and every finding against it.

Name it wrong and Hunter suggests near matches.

---

## `hunter check`

Build the pull request comment for a change.

```bash
hunter check --pr 1184
hunter check . --base origin/main --previous-report before.json
```

| Option | What it does |
|---|---|
| `--pr` | The pull request number, for the footer |
| `--base` | The branch this change is measured against. Default `origin/main` |
| `--previous-report` | A `report.json` from before the change, for a true before-and-after |

Without a previous report, the comment lists findings on the files the change
touched, which is a superset of what the change introduced. It says so in the
comment rather than presenting the two as the same thing.

Writes the body to a file. Posting is the Action's job, not this command's.

---

## `hunter showcase`

What changed in a window, and what it cost.

```bash
hunter showcase --days 14
```

Reports merged pull requests, tables added, changed and removed, reporting
changes, design changes, tickets referenced, and the debt sitting on the tables
that window touched.

That last section is always present. A report listing only what was delivered
is marketing rather than reporting.

---

## `hunter dashboard`

Write the report as one self-contained HTML file.

```bash
hunter dashboard
hunter dashboard . --out /tmp/report.html
```

| Option | What it does |
|---|---|
| `--out`, `-o` | Where to write. Default `out/dashboard.html` |

The stylesheet, every chart and the logo are inlined, so the file opens with no
network and nothing beside it: from a build artifact, a shared drive or an email
attachment. About 75 KB. Needs nothing installed beyond Hunter itself, and in
particular not the `site` extra.

Every chart is SVG generated in Python rather than drawn by a charting library.
That is what keeps the file self-contained, and it keeps two runs of one commit
byte-identical.

Nine bands, each answering one question:

| Band | The question |
|---|---|
| The number | How healthy is this repository |
| Needs a decision | What has nobody decided, as opposed to not fixed |
| Where the ground is being lost | Which area is costing the most points |
| How much of the plan is real | How much of the business model exists |
| Every entity | Where each table stands, in one of eleven states |
| Every rule at once | Is this a few bad tables or a habit |
| What everything else is built on | Which tables are load-bearing and unchecked |
| Do these first | What to fix, ranked by what closing it recovers |
| What this is not based on | What Hunter could not read |

---

## `hunter docs build`

Generate the site and build it. This is the dashboard plus every detail page
behind it, with search and navigation.

```bash
hunter docs build
hunter docs build . --out /tmp/site
hunter docs build . --markdown-only
```

| Option | What it does |
|---|---|
| `--out`, `-o` | Where to write. Default `out/site` |
| `--markdown-only` | Write the pages and stop, without running MkDocs |

Twelve pages plus one per table, and `dashboard.html` as the front door. Needs
the `site` extra installed for the build step; the markdown and the dashboard
are written either way.

---

## `hunter diagram`

Print one Mermaid diagram.

```bash
hunter diagram --level conceptual
hunter diagram --level logical --domain commerce
hunter diagram --level lineage
hunter diagram --level blast --model wh_shop__order_fact
```

| Level | What it draws |
|---|---|
| `conceptual` | Business entities, coloured by their real state |
| `logical` | Designed entities, attributes grouped by what they are for |
| `physical` | Built tables, with real types and how they are built |
| `lineage` | The graph, collapsed by layer and area. Add `--domain` for detail |
| `blast` | What a change to one table reaches. Needs `--model` |

---

## `hunter baseline`

Record where the repository starts.

```bash
hunter baseline
hunter baseline . --note "Recorded at the start of the engagement"
```

Writes `.hunter/baseline.json`. Commit it, so later runs measure movement
rather than absolutes.

---

## `hunter init`

Write a starting ruleset and register.

```bash
hunter init
hunter init . --force
```

Detects the layout and says what it could not find. Where a manifest is
present, it also scores the repository and fills the register with the tables it
would flag, each with a blank reason.

Refuses to overwrite existing files without `--force`. Overwriting a ruleset
somebody has tuned would be worse than refusing.

---

## `hunter rules`

Every rule Hunter can report.

```bash
hunter rules
```

```
alignment.built_disabled                    low      0.5  Does what was built match the design
alignment.built_off_plan                    medium   1.2  Does what was built match the design
...
77 rules.
```

Full reference with the consequence line for each: [Every rule](reference/rules.md).

---

## `hunter version`

The three versions stamped on every report.

```bash
hunter version
```

```json
{
  "hunter": "0.1.0",
  "house_ruleset": "1",
  "score_model": "1"
}
```

The score model version is what lets a later run tell real change from a change
caused by upgrading Hunter.
