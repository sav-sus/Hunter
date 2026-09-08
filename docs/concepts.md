# Concepts

Seven ideas. Everything else follows from them.

## 1. The same model exists at four levels

Most of what Hunter finds comes from comparing them.

| Level | What it is | Where Hunter reads it |
|---|---|---|
| **Business model** | The things the business needs held, in business language. No columns | A conceptual Mermaid diagram, or the register |
| **Design** | The specification: columns, keys, relationships, what one row means | Authored DBML files |
| **Built** | What the repository actually produces | The dbt manifest |
| **Deployed** | What is in the warehouse | Not read at this version |

An entity can exist at some levels and not others, and each combination means
something different. A table built with no design is undocumented and unowned. A
design with nothing built is a plan. A business entity with no design is the
backlog.

### Names differ between the levels

They do in practice, and by a lot. On one real repository the business model
says `wh_commerce__demand_orders` where the design says
`wh_commerce__demand_order_fact`. Exact matching paired 3 of 72.

Hunter matches in three ways, strongest first:

1. **Declared.** An `implements` entry in the register. A person said so.
2. **Exact.** The names are identical.
3. **Normalised.** Layer prefix, entity suffix, plural and domain alias
   removed. This took the same repository from 3 matches to 36.

Where a normalised match lands on two candidates, Hunter reports it as
ambiguous rather than choosing. Choosing silently produces a wrong
reconciliation row that reads as fact.

## 2. Layers, and what may read what

A layer is a stage in the pipeline. Data moves through them, and reading past a
stage means the checks in that stage do not apply.

The shipped standard:

| Layer | Prefix | Stage | Temporary or permanent | May read |
|---|---|---|---|---|
| `seeds` | | outside the flow | permanent | nothing |
| `staging` | `stg_` | 1 | temporary | sources, seeds |
| `integration` | `int_` | 2 | temporary | staging, integration, seeds |
| `warehouse` | `wh_` | 3 | permanent | staging, integration, warehouse, seeds |
| `reverse_etl` | | 4 | permanent | warehouse, integration |
| `ai` | | 4 | permanent | warehouse, integration |

All of it is configurable. Rename them, add one, change the rules. Hunter has no
built-in opinion about your layer names.

Two fields are worth understanding:

**`pipeline_stage`** is where the layer sits in the flow. Reading two stages
below is a bypass. A layer at stage 0 sits outside the flow, so reading it
bypasses nothing.

**`in_alignment`** says whether the layer holds modelled entities. Only those
layers appear in the reconciliation. Without it, 129 staging models would each
be reported as built off-plan, which is not a finding anyone can act on.

## 3. Temporary against permanent

A temporary table is a working step. A permanent one is something to report
from. Getting the distinction visible is one of the problems Hunter exists for:
working steps get consumed and depended on, and then cannot be changed.

Hunter decides in this order, and records which signal decided:

1. A declaration in the register
2. A warehouse table expiration (not read at this version)
3. `materialized: ephemeral`
4. The layer's declared persistence
5. The materialisation
6. Whether anything reads it

The register comes first, ahead of everything Hunter can infer. A person
stating intent outranks a guess, and the declaration costs them a written
reason.

Recording the deciding signal matters because it makes the answer arguable. "It
is temporary because its layer says so" can be disagreed with. "It is
temporary" cannot.

## 4. What a test proves, not how many there are

One real repository has 3,926 tests. 3,492 are the same check that a column is
not entirely empty, and 100 are uniqueness tests. Counting tests scores that
repository well while its keys go largely unverified.

So Hunter separates them:

| Kind | What it proves | Counts as key cover |
|---|---|---|
| `unique` | No duplicates on this column | Yes |
| `not_null` | Always populated | Yes |
| `relationships` | Every reference resolves | Yes, for foreign keys |
| `at_least_one` | Not entirely empty | No |
| `accepted_values` | Within a known set | No |
| anything else | Something | No |

A test set to warn rather than error reports a problem and lets the build carry
on, so bad data reaches reports anyway. Hunter reports that separately.

## 5. Exposure weighting

A missing test on a table feeding twelve report fields matters more than the
same gap on a table nothing reads.

Hunter counts what depends on each table: other tables downstream, reporting
fields, explores and declared exposures. A finding's cost is multiplied by that
reach.

The weight grows with the logarithm of the reach and is capped at 3, so one
heavily used table cannot dominate the whole score.

## 6. Confidence, and suggestions

Some judgements are certain. "This table has no description" is a fact. Others
are inference: "this table is named as a dimension but behaves like a fact" is a
reading of its columns.

Every finding carries a confidence. Below the configured floor, it is reported
as a suggestion and left out of the score.

Entity inference is the main case. Without warehouse access there is no
uniqueness ratio and no row count, so the judgement rests on column shape alone.
Hunter caps what it will claim at 0.65 rather than 0.85, and says so in the
finding's evidence.

The reasoning is about trust rather than accuracy. A suggestion that turns out
right costs nothing. A scored finding that turns out wrong costs the tool its
audience.

## 7. What was not checked

A score is only as good as what went into it.

An area Hunter could not measure is excluded and its weight shared across the
rest. The report names it, says why, and puts it on a page of its own.

Two alternatives, both worse. Scoring it as zero reports a failure where there
was no measurement. Dropping it silently means the score is out of less than 100
without saying so.

The same applies within an area. Where column types are unavailable, the
type-drift rule reports that it could not run rather than reporting no drift, so
nobody reads silence as an all-clear.

## Terms

| Term | Meaning |
|---|---|
| **model** | One table or view the project builds. The dbt word |
| **grain** | What one row represents. "One row per order", "one row per store per day" |
| **fact** | A table of things that happened, with figures you would add up |
| **dimension** | A table that describes things. You join to it to label figures |
| **aggregate** | Figures already added up to a chosen level |
| **primary key** | The column identifying a row uniquely |
| **foreign key** | A column pointing at a row in another table |
| **exposure** | A note recording that something outside the project, usually a dashboard, depends on a table |
| **systemic gap** | A rule that failed on everything it examined |
| **vendored** | Code from an installed package. Reported, never scored |
| **silenced** | A finding somebody agreed to leave, with a reason and an end date |
