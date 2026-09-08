# Rittman Hunter

Point it at an analytics repository and it tells you what state the repository
is in.

Hunter reads dbt, LookML, your data model design and your git history, then
reports on them. It changes nothing: no commits, no pull requests, no writes to
your warehouse.

```
89.5 / 100    Well maintained. Safe to build on

 90.4  A  What is checked automatically            38 findings
 87.3  A  Does what was built match the design    190 findings
 92.6  A  How the tables fit together              53 findings
 77.2  B  What is written down                    135 findings
 86.7  A  Do the reports still match the data     183 findings
 97.1  A  Are the house rules followed            155 findings
 98.3  A  Are the tables the shape they claim       7 findings
    -  -  What it costs to run                  not measured

Missing everywhere it was checked:
  63 of 63  Who owns what
  54 of 54  Do the reports still match the data
```

Two seconds on a 280-model repository. No warehouse credential needed.

[Install it](install.md){ .md-button .md-button--primary }
[See it working](example/index.md){ .md-button }

## The four questions it answers

Each is something nobody can answer today without reading the whole repository
by hand.

**What is in here, and which parts are working steps rather than finished
tables?** Hunter classifies every table as temporary or permanent, and records
which signal decided, so the answer can be argued with rather than just
accepted.

**Who built each part?** Every table is attributed to the commit, author and
pull request that created it. Findings are routed to whoever can close them and
reported by team, never as a ranking of people.

**Is the modelling right?** Hunter works out what each table behaves like from
the shape of its columns, then compares that against what its name claims. A
table named as something you total that has nothing to total is worth knowing
about.

**Do the layers agree?** The business model, the design, the repository and the
reporting layer. Every reporting field is mapped to the column it reads, so a
renamed column shows up as a broken field in the same pull request rather than
in a client's report.

## What makes it different

**Every finding says what breaks.** Not "high severity: relationships test
missing", but:

> Nothing checks that these references in daily store performance point at rows
> that exist. Where they do not, joined figures come out low and the rows simply
> vanish.

Those lines are templates filled from each finding's own evidence. Nothing is
written by a language model, so every sentence has a deterministic check behind
it.

**It says what it did not check.** A score is only as good as what went into it.
Areas Hunter could not measure are excluded, their weight shared across the
rest, and named on a page of their own. It never scores an unmeasured area as
zero, and it never quietly scores out of less than 100.

**It has no opinions of its own.** Layer names, naming conventions, entity
suffixes and weights are all declared in configuration. It ships with a house
standard, and any difference from that standard is published with the reason
given for it.

**It reports systemic gaps above the number.** "No table names an owner, 63 of
63" is one decision nobody has taken, not 63 separate defects. A weighted mean
buries that, so it is listed separately, above the score.

## What it reads

A dbt `manifest.json` and nothing else is required. Everything beyond that adds
an area to the score rather than being a prerequisite.

| Source | What it adds | Needs a credential |
|---|---|---|
| `manifest.json` | Tables, columns, tests, lineage | No |
| DBML design files | Does what was built match what was designed | No |
| A conceptual Mermaid diagram | Does the design match what the business asked for | No |
| LookML | Will a renamed column break a report | No |
| Committed Droughty output | Are the generated tests and descriptions still applied | No |
| Git history | Who wrote what, and what changed in a window | No |
| BigQuery metadata | What is deployed, and what it costs | Yes. Not built yet |

## Where to go next

| If you want to | Read |
|---|---|
| Install it and run it | [Installing](install.md), then [Getting started](quickstart.md) |
| See real output before installing anything | [See it working](example/index.md) |
| Understand the ideas behind it | [Concepts](concepts.md) |
| Configure it for your repository | [Configuration](configuration.md) and [The register](register.md) |
| Understand the number | [How the score works](scoring.md) |
| Look up a rule | [Every rule](reference/rules.md) |
| Run it in CI | [In CI](ci.md) |
| Know why it was built this way | [The product record](https://github.com/sav-sus/Hunter/tree/main/.doc) |

## Licence

Proprietary. Not open source. See
[LICENSE](https://github.com/sav-sus/Hunter/blob/main/LICENSE).
