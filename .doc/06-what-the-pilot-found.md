# What running it against a real repository found

Every rule was run against a real 280-model Rittman Analytics client
repository before it was trusted. Twelve rules and two framework bugs were
wrong, and only real data exposed them. This is a record of what, and what
changed.

The pattern is worth noting on its own: none of the first nine would have been
found by the example project, because the example was written by the same person
as the rules. A rule tested only against a fixture is a rule tested against its
own assumptions.

The last three were found by rebuilding the example to match the real layout,
which is the same lesson from the other direction: a fixture that does not look
like the real thing does not behave like it either.

## Rules that were wrong

### `select *` fired on 226 of 228 models

The rule flagged any star select. But `select * from {{ ref('x') }}` is ordinary
dbt style, and so is `select * from final` at the end of a query.

A rule that fires on 99% of a codebase is noise, and noise is what gets a tool
muted. The risk register names it directly.

Narrowed to star selects reading a raw source or a hardcoded table, where an
upstream schema change actually leaks through. That is 109 of 228, all genuine.
Also set to low severity: downstream models select named columns and so fail
loudly at build time rather than producing quiet wrong numbers.

### `is distinct from` was read as a FROM clause

`or curr.x is distinct from prev.y` matched the pattern for `from <table>`, so
Hunter reported a hardcoded reference to a table called `prev`.

Now guarded, along with the `from` inside `extract(day from x)` and `trim`.

### The staging-bypass rule used the wrong order

It reported "skips the seeds layer to read a warehouse table", which is
meaningless. It was using the order layers happen to appear in the configuration
file as the pipeline order.

Pipeline position is now declared explicitly per layer. The 34 findings became
15 real ones, all warehouse models reading staging directly and skipping
integration.

### Measure detection missed the middle of names, then over-reached

The first version matched measure words as suffixes, so
`store_visitor_count_actual` read as having no measures and its fact was wrongly
flagged as having nothing to add up.

Changed to match words anywhere in the name. That then flagged
`exchange_rate_from_currency` as a measure, because it contains "rate", and
`employee_cost_centre_name`, because it contains "cost". Both are labels.

Now matched as tokens with an exclusion list for endings that describe rather
than measure. A mid-name boolean marker was also being missed, so
`exchange_rate_is_carried_forward` counted as a figure on a dimension.

### Column types are almost never in the manifest

Only 164 of 5,251 columns carried a data type. Types come from `catalog.json`,
which `dbt docs generate` writes, and the manifest carries almost none.

Two consequences. Entity inference rests on naming rather than types, so it caps
its confidence lower and says so in its evidence. And the type-drift rule cannot
run at all, so it reports that it could not run rather than reporting no drift,
which a reader would take as "the types are fine".

An optional catalogue reader was added for projects that do run
`dbt docs generate`.

### LookML refinements were treated as redefinitions

`view: +orders` refines an existing view rather than redefining it, and the
pilot uses it heavily: generated base views refined with hand-written measures.

Treating them as duplicates misattributed 1,823 measures and produced 93 false
"defined twice" findings. Folding them in dropped that to 3, and those 3 are
real duplicate definitions.

Explores can be refined too, which was missed on the first pass. 15 explores
were counted twice and 15 caching policies missed.

### LookML constant syntax was not stripped

Three views name their table as `@{project}.@{dataset}.@{table}`. Hunter reported
them as unresolvable, which is the right outcome, but only after `@{...}` was
added to the patterns it strips. Before that the whole string was treated as a
table name.

### The main design file did not parse

The repository's `physical_model.dbml` fails with the pinned parser. It escapes
a quote inside a note by doubling it, SQL style, 140 times.

A normalising pass fixes it. It is done with a small scanner rather than a
regular expression, because `''` is genuinely ambiguous: inside a string with
content it is an escaped quote, but at the start of a string it is an empty
string, and a regular expression corrupts the second case.

If a file still fails, it is parsed table by table so one bad note costs one
table rather than a whole area of the score.

### Requiring three words of a column description

A three-word floor is right for a table description and wrong for a column.
"Order date" is a useful column description. The floor now applies to tables
only.

## Framework bugs

### The alignment area always scored zero

The module called `examine()` only when a rule fired, so the denominator equalled
the numerator. Any repository with a single off-plan table scored 0 for that
whole area.

Now every candidate is examined, whether or not it fails.

### Adding a rule raised the score

An area's score was total points lost over total points available across its
rules. A rule examining 230 tables contributes a denominator 70 times larger
than one examining 3, so a mostly-passing rule diluted every other rule in its
area.

That is exactly the movement the specification asks Hunter not to present to a
client as real change. Changed to a weighted mean of per-rule pass rates.

## Things that were right but incomplete

### Four alignment states were missing

| State added | Why |
|---|---|
| Built, switched off | Six models are built and disabled by a dbt variable. They sit in a separate part of the manifest, and calling them "designed, not started" would have been six false findings |
| Built off-plan, approved | The register lets a team accept an off-plan build. It still appears, so the approval is visible |
| On the business model only | 71 business entities have no design yet. That is the design backlog, and "not present anywhere" misdescribed it |
| On the data flow diagram only | 20 entities are named only in the flow diagram, most produced by installed packages |

### Vendored code was being scored

57 of 299 models come from installed packages. Holding a team to their own
conventions on code they cannot change without forking the package produces
findings nobody can act on.

### Domains were inconsistent

Domains arrive from three places that disagree: a design table group
(`wh_commerce`), a model name (`commerce`), and a diagram block
(`wh_master_data`). Left alone they produced 16 groups where there are 13, and
would have split the site's grouping in two.

### Reverse-ETL models were outside the chain

Adding them surfaced 8 genuine off-plan builds: tables that push data out of the
warehouse and appear on no design.

### The divergence report missed disabled rules

The specification asks for rules the project has overridden, disabled or
reweighted, and why. A disabled rule never appeared, because the house ruleset
declares no rules block and so there was nothing to diverge from. Disabled and
reweighted rules are now reported against the house's implicit position.

Found by writing the example project, which is the one thing the example caught
that the real repository did not.

### Absolute paths reached the output

Absolute paths from whoever's laptop ran it were appearing in findings, the
report and the pull request comment: a home directory, then the folder they keep
client work in, then the repository. Unreadable in a client's pull request, and a
small leak of who ran it and how they organise their machine.

Every path is now relative to the repository root, and a test asserts that no
home-directory prefix reaches the report. The content guard in
`scripts/check_no_client_content.py` catches the same thing in tracked files,
and caught it in this very sentence on the first attempt at writing it.

## What the numbers came out as

Predicted in the plan against what the finished tool reports.

| Measure | Predicted | Actual | Why |
|---|---|---|---|
| Designed and delivered | 54 | 56 | Normalised matching found two more pairs |
| Built, switched off | 6 | 6 | |
| Designed, not started | 3 | 10 | The prediction counted exact matches on one layer; the chain covers all 72 designed entities |
| Built off-plan | 0 | 8 | Reverse-ETL joined the chain |
| Missing descriptions | 0 | 0 | |
| Empty descriptions | 0 | 0 | |
| Orphaned descriptions | 360 | 360 | |
| Dropped generation overrides | Unknown | 0 | The team's current regeneration is clean |

## What it produced in the end

| Measure | Value |
|---|---|
| Score | 89.6, grade A |
| Findings | 644 open, 10 suggestions |
| Run time | 2.1 seconds |
| Areas scored | 7 of 8 |
| Systemic gaps | 2: no table names an owner, none declares an exposure |

## Four more, found by rebuilding the example

Rebuilding the example project to match the real layout, with real SQL files
and the layered LookML structure, found four further faults. That is the
strongest argument for keeping an example realistic: a fixture that does not
look like the real thing does not behave like it either.

### A LookML refinement replaced the field it refined

The layered structure refines generated dimensions purely to add a label and a
group. Hunter replaced the whole field, which dropped the base field's `sql`
and so its column reference.

The cross-layer check then had nothing to check on any refined field. On the
real repository that hid 629 of 4,314 field references, and the broken-field
rule found seven where it should have found more. A refinement now merges
property by property, which is Looker's own behaviour.

### The star-select rule reported the house pattern

The standard reads a source with `select *` into a CTE, then names and casts
every column in the next one. Nothing leaks, because the second CTE fixes the
shape.

Hunter flagged all of it: 109 of 228 models. The rule now fires only where a
query never names a column anywhere, so the source's shape passes straight
through. That is 2 of 228, and both are hardcoded tables rather than sources.

### BigQuery quotes each part of a table name separately

`` `project`.`dataset`.`table` `` is three backtick groups, not one, so both the
hardcoded-reference and star-select rules reported only the first part as the
table name. A finding that names `` `warehouse` `` instead of the table is a
finding nobody can act on.

### The rendered output was not deterministic

Committing the example turned two of its findings into git-derived values, and
chasing that down exposed a worse fault behind it.

The blast-radius diagram looped over a set of table names. Set order over
strings depends on Python's hash seed, which is fixed inside one process and
different between processes. So two runs of the same commit drew the same edges
in a different order, on three committed pages.

The golden-file test could not have caught this. It runs in one process, where
the order is stable, so the comparison passed every time. The drift only
appeared when the pages were rebuilt from a second process.

Two changes came out of it. The loop now walks the sorted list and keeps the set
for membership only. And the determinism test now renders every page and every
diagram twice, in two subprocesses with different hash seeds, and compares the
bytes. Reverting the one-line fix makes that test fail, which is the only
evidence worth having that a test covers what it claims to.

The git-derived values were the smaller half. Attribution and the
description-staleness rule both read history, which would tie the pinned output
to whoever committed the example and when. A shallow checkout, a squash merge or
a second developer would each have broken it. The example's committed output now
skips history, and says so on its "what was not checked" page.
