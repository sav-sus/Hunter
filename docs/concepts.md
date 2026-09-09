# The ideas behind it

<p class="lede">Seven of them. Everything else in Hunter follows from
these.</p>

## 1. One model, four levels

Most of what Hunter finds comes from comparing them.

| Level | What it is | Read from |
|---|---|---|
| **Business model** | The things the business needs held, in business language. No columns | A conceptual Mermaid diagram, or the register |
| **Design** | The specification: columns, keys, relationships, what one row means | Authored DBML files |
| **Built** | What the repository actually produces | The dbt manifest |
| **Deployed** | What is in the warehouse | Not read at this version |

An entity can exist at some levels and not others, and each combination means
something different.

| Exists at | Means |
|---|---|
| Built, not designed | Undocumented and unowned |
| Designed, not built | A plan |
| Business model only | The backlog |

??? note "Names differ between the levels, and matching them is not trivial"

    On one real repository the business model says `wh_commerce__demand_orders`
    where the design says `wh_commerce__demand_order_fact`. Exact matching
    paired 3 of 72.

    Hunter matches three ways, strongest first:

    | Method | What it is |
    |---|---|
    | Declared | An `implements` entry in the register. A person said so |
    | Exact | The names are identical |
    | Normalised | Layer prefix, entity suffix, plural and domain alias removed |

    Normalising took that repository from 3 matches to 36. Where a normalised
    match lands on two candidates, Hunter reports it as ambiguous rather than
    choosing: choosing silently produces a wrong row that reads as fact.

## 2. Layers, and what may read what

A layer is a stage in the pipeline. Reading past a stage means the checks in
that stage do not apply.

The Rittman Analytics standard, shipped as `ra-house@1`:

| Layer | Prefix | Stage | Persistence | May read |
|---|---|---|---|---|
| `seeds` | | outside the flow | permanent | nothing |
| `staging` | `stg_` | 1 | temporary | sources, seeds |
| `integration` | `int_` | 2 | temporary | staging, integration, seeds |
| `warehouse` | `wh_` | 3 | permanent | staging, integration, warehouse, seeds |
| `reverse_etl` | | 4 | permanent | warehouse, integration |
| `ai` | | 4 | permanent | warehouse, integration |

All of it is configurable. Hunter has no built-in opinion about your layer
names.

**Layers Hunter finds on its own.** A directory under `models/` that no layer
claims becomes a layer named after the directory. Its models are grouped,
scored and shown on the report, and the report says the layer was found rather
than declared. It carries no rules until it is declared in `hunter.yml`,
because Hunter knows the models are grouped, not what the group should look
like. A new part of the warehouse therefore appears on the next run with no
configuration change.

??? note "Two fields worth understanding"

    **`pipeline_stage`** is where the layer sits in the flow. Reading two stages
    below is a bypass. A layer at stage 0 sits outside the flow, so reading it
    bypasses nothing.

    **`in_alignment`** says whether the layer holds modelled entities. Only
    those layers appear in the reconciliation. Without it, 129 staging models
    would each be reported as built off-plan, which is not a finding anyone can
    act on.

## 3. Temporary, verified or permanent

A temporary table is a working step, or a table only ever meant to run once. A
permanent one is something to report from. A verified one is permanent, and a
named person has confirmed it should stay. Working steps get depended on, and
then cannot be changed, which is one of the problems Hunter exists for.

Hunter can infer the first and the last. It can never infer verified, because
verified means somebody looked. The dashboard shows the three words side by
side, so a reader can tell a table that was checked from one that was assumed.

Hunter decides in this order, and records which signal decided:

| | Signal |
|---|---|
| 1 | A declaration in [the register](register.md) |
| 2 | A warehouse table expiration (not read at this version) |
| 3 | `materialized: ephemeral` |
| 4 | The layer's declared persistence |
| 5 | The materialisation |
| 6 | Whether anything reads it |

<div class="key" markdown>
**The register comes first, ahead of anything Hunter can infer.** A person
stating intent outranks a guess, and it costs them a written reason. Recording
the deciding signal is what makes the answer arguable: "it is temporary because
its layer says so" can be disagreed with, "it is temporary" cannot.
</div>

## 4. What a test proves, not how many there are

One real repository has 3,926 tests. 3,492 are the same check that a column is
not entirely empty, and 100 are uniqueness tests. Counting tests scores that
repository well while its keys go largely unverified.

| Kind | What it proves | Counts as key cover |
|---|---|---|
| `unique` | No duplicates | Yes |
| `not_null` | Always populated | Yes |
| `relationships` | Every reference resolves | Yes, for foreign keys |
| `at_least_one` | Not entirely empty | No |
| `accepted_values` | Within a known set | No |
| anything else | Something | No |

A test set to warn rather than error lets the build carry on, so bad data
reaches reports anyway. Hunter reports that separately.

## 5. Exposure weighting

A missing test on a table feeding twelve report fields matters more than the
same gap on a table nothing reads.

Hunter counts what depends on each table: tables downstream, report fields,
explores and declared exposures. A finding's cost is multiplied by that reach.
The weight grows with the logarithm of the reach and caps at 3, so one heavily
used table cannot dominate the score.

## 6. Confidence, and suggestions

Some judgements are facts. "This table has no description" is one. Others are
readings: "named as a dimension but behaves like a fact" is an inference from
its columns.

Every finding carries a confidence. Below the configured floor it is reported
as a suggestion and left out of the score.

<div class="key" markdown>
**The reasoning is about trust, not accuracy.** A suggestion that turns out
right costs nothing. A scored finding that turns out wrong costs the tool its
audience.
</div>

??? note "Where confidence gets capped, and why"

    Entity inference is the main case. Without warehouse access there is no
    uniqueness ratio and no row count, so the judgement rests on column shape
    alone. Hunter caps what it will claim at 0.65 rather than 0.85, and says so
    in the finding's evidence.

## 7. What was not checked

A score is only as good as what went into it. An area Hunter could not measure
is excluded, its weight shared across the rest, and named on a page of its own.

| Alternative | Why it is worse |
|---|---|
| Score it as zero | Reports a failure where there was no measurement |
| Drop it silently | The score is then out of less than 100 without saying so |

The same applies inside an area. Where column types are unavailable, the
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
| **exposure** | A note that something outside the project, usually a dashboard, depends on a table |
| **systemic gap** | A rule that failed on everything it examined |
| **vendored** | Code from an installed package. Reported, never scored |
| **silenced** | A finding somebody agreed to leave, with a reason and an end date |
