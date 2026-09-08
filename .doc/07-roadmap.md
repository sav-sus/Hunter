# Roadmap

## Built: M0

Complete. Version 0.1.0.dev0, unreleased.

| Capability | State |
|---|---|
| Configuration across five levels, with the divergence report | Built |
| The authored register, with expiry and staleness reporting | Built |
| dbt manifest reading, including disabled models and the optional catalogue | Built |
| DBML design reading, with dialect normalisation and per-table recovery | Built |
| Conceptual and logical Mermaid diagram reading | Built |
| LookML reading, with refinements folded in | Built |
| Committed Droughty output comparison | Built |
| Git attribution and commit windows | Built |
| The dependency graph, with exposure weighting | Built |
| The five-point alignment chain, eleven states | Built |
| 77 rules across 7 areas | Built |
| Score, weight renormalisation, systemic gaps, baseline | Built |
| `report.json` | Built |
| Three model levels drawn, plus graph and blast radius | Built |
| Twelve site pages, MkDocs Material | Built |
| Plain-language layer and glossary | Built |
| Pull request comment, with a true diff given a previous report | Built |
| Window report | Built |
| Command line: 11 commands | Built |
| Composite GitHub Action | Built, not published |
| `hunter init` scaffolding, pre-filled | Built |

## Next: M1, one to two weeks

Ordered by what unblocks the most.

| Item | Why it is next | Depends on |
|---|---|---|
| Publish the Action and the package | Nothing can be installed anywhere until this is done | The visibility and ownership decisions in [09](09-risks-and-open-items.md) |
| Site hosting | The site exists and has nowhere to live | The same decisions |
| Live Droughty against the warehouse | Completes the comparison the file-based half starts | A read-only credential |
| Debt register with ageing | Findings have a first-seen date already; this turns it into "open for 40 days" | Score history, below |
| Score history and trend | Answers "are we getting anywhere" with a line rather than a number | Somewhere to keep past reports |
| The opportunity list | Distinct from the debt list: designed entities not yet built, tables ready to promote, missing conformed dimensions | Nothing. Buildable now |
| Window report to Slack and Confluence | The report exists; this is delivery of it | Credentials for both |

The opportunity list is the one item with no dependency. It is worth doing
first because it changes the tool's tone: a list of what to build next reads
differently from a list of what is wrong.

## M2, three to four weeks

Everything here needs read-only warehouse access, and together it turns on the
eighth area of the score.

| Item | What it adds |
|---|---|
| BigQuery metadata reading | Row counts, partitioning, table expiration, and what is actually deployed |
| Production drift | Objects in the warehouse with no producing model, and models never deployed. Two of the eleven alignment states currently unreachable |
| Cost and run activity | Spend per table, what actually runs, and tables that cost money with no consumer |
| The performance and cost area | Currently skipped with its weight redistributed. This is what makes it score |
| Scheduled refresh | Warehouse-derived panels read static data written by a scheduled run |
| Client theme and report mode | Internal shows candid findings and commercial notes; client suppresses internal-only classes |

Warehouse access also strengthens what is already built. Entity inference caps
its confidence at 0.65 without column types and uniqueness ratios; with them it
reaches 0.85 and more of its judgements count towards the score.

## M3, five to eight weeks

| Item | Notes |
|---|---|
| SCD2 validation | Overlapping or gapped validity windows, exactly one current record per business key. Needs warehouse access |
| Unused reporting fields | Fields defined and never queried. Needs Looker usage data |
| Design bootstrapper | Draft a DBML design for a repository that has none, for a human to correct |
| Fix suggestions | The change that would close a finding, as a suggestion. Never applied |
| Written narrative for the window report | Themes and prose. Constrained to introduce no fact absent from the computed set |

The narrative is the only place a language model is planned, and the constraint
is the point: it translates computed findings and never adds one.

## M4, later

| Item | Why it waits |
|---|---|
| Pull requests in flight, and projected merge state | Needs a manifest per branch, which is a build per branch |
| Collision detection between open pull requests | Depends on the above |
| Multi-repository rollup | Needs a shared store, which the current isolation model rules out by design |
| Snowflake support | One file in `ingest/`, once there is a client who needs it |

## What would change the order

**A client asks for cost.** M2 moves ahead of M1. The credential conversation
becomes the first task rather than the third.

**A client will not grant warehouse access.** M2 largely disappears. The
performance area stays skipped, which the score already handles, and the
opportunity list and history work become more valuable because they are all
that is left to add.

**A second engagement starts.** Multi-repository rollup moves from M4 forward,
and the isolation model needs revisiting, which is a design decision rather than
a task.
