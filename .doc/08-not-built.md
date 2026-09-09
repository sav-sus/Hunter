# What is not built

Everything here is absent on purpose. Each entry says what it would take.

Some entries are Rittman Analytics decisions rather than technical limits, and
those are marked.

## Needs warehouse access

The largest group. Nothing in it can be built without a read-only credential,
and the decision to ship without one is in [05-decisions.md](05-decisions.md).

| Absent | What Hunter does instead | To build it |
|---|---|---|
| What is actually deployed | Reports the warehouse column as "not checked" rather than guessing | Read `INFORMATION_SCHEMA.TABLES` |
| Cost and spend per table | The whole area is excluded and its weight redistributed | Read `INFORMATION_SCHEMA.JOBS_BY_PROJECT`, matched on dbt invocation labels |
| Which tables actually run, and how often | Nothing | The same job history |
| Partitioning and clustering checks | Nothing | `INFORMATION_SCHEMA.PARTITIONS` |
| Row counts and observed grain | Compares the declared grain against whether anything tests it, not against the data | Count distinct on the declared grain columns |
| Uniqueness ratios for entity inference | Infers from column shape alone and caps confidence at 0.65 rather than 0.85 | The same |
| Table expiration as a persistence signal | Starts the precedence chain one step down, at `materialized: ephemeral` | `INFORMATION_SCHEMA.TABLES` |
| Live Droughty regeneration | Compares the committed output instead, which needs no credential | Run Droughty in CI and diff its output |
| Two of the eleven alignment states | They exist and are unreachable: live without code, and untracked table | Any of the above |

Two of the eleven alignment states being unreachable is worth restating. Hunter
can already report a table that exists in production with nothing producing it.
It has never had the information to find one.

## Deliberately out of scope

| Absent | Why |
|---|---|
| Any write to a warehouse | A licence term, not a gap |
| Automatic fix commits | The same. Hunter never modifies code, opens a commit or opens a pull request |
| Column-level lineage | A large piece of work for a benefit the table-level graph mostly delivers |
| Warehouses other than BigQuery | One file in `ingest/` when there is a client who needs one |
| Semantic layers other than LookML | The same |
| Multi-repository rollup | The isolation model rules it out by design: one instance per repository, no shared store, no cross-client aggregation |
| Pull requests in flight | Needs a manifest per branch, which means a build per branch |
| Per-person rankings | Ruled out on purpose. A public ranking moves behaviour towards avoiding blame rather than towards quality, and the tool loses its audience. Attribution exists so a gap can be routed to whoever can close it, so Hunter routes by owner and reports by team |

## Partly built

| Item | What works | What does not |
|---|---|---|
| Pull request diffing | Given a previous `report.json`, a true before-and-after | Without one it reports findings on the files the change touched, which is a superset. The comment says so rather than presenting the two as the same |
| SQL structure checks | Star selects, hardcoded references, length, join count, step naming | The specification asks for sqlfluff and dbt-score to be wrapped rather than reimplemented. They are not wrapped yet, and the current checks are deliberately shallow rather than a second SQL parser |
| LookML | Views, fields, explores, refinements | Derived tables are recorded and skipped. 13 of 80 views in the pilot. Liquid inside SQL is not evaluated |
| Entity inference | Column shape, with published confidence | No warehouse evidence, so it caps what it will claim and excludes low-confidence judgements from the score |
| Type comparison | Runs where a catalogue file exists | Almost no manifest carries types, so on most projects it reports that it could not run |
| The window report | Every fact: commits, pull requests, tables added and changed, tickets, debt created alongside | No written narrative. That is milestone M3, and it will never introduce a fact absent from the computed set |
| Jira integration | The ticket pattern is configured and references are extracted from subjects, bodies and trailers | Sprint boundaries are not read from a board, so the window is a fixed number of days |
| The Action | Written, tested, and installable from tag `v0.1.0`, which the release job creates when a version bump reaches main | Not on the Marketplace |

## Not built and not planned

| Absent | Why |
|---|---|
| A web application or hosted service | One instance per repository, no shared store. A service would change that |
| Real-time or on-save checking | The pipeline runs in 2 seconds, so a pre-commit hook is possible, but nothing needs it yet |
| A dbt package | Hunter reads a manifest; a package would mean running inside dbt and inheriting its dependency constraints |
| Editor integration | The same reasoning as the pre-commit hook |

## Known limitations of what is built

Worth stating plainly, because each one is a place a reader could be misled.

**The score is only as good as what went in.** Six of eight areas measured on a
repository with no design files, and the report says so on its own page. Nobody
should compare two scores computed from different sources.

**Name matching is not exact.** 36 of 72 designed entities matched their
business-model counterpart by normalised name. The rest is a real gap, but some
of it may be a naming difference Hunter could not bridge. An explicit mapping in
the register settles any specific case.

**Findings have no age without a previous report.** A finding's first-seen date
comes from the model's creation date, which is a proxy. Real ageing needs score
history, which is M1.

**The window report attributes debt by touched table, not by date.** A finding
on a table changed in the window is counted as debt for that window, even if it
predates the change. Getting this right needs a report per window.

**Confidence is Hunter's own estimate.** It is computed from how cleanly the
signals agree, not calibrated against outcomes. A 0.8 does not mean eight in ten
such findings prove correct, because nobody has measured that yet.
