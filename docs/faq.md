# Questions

## Does it need access to my warehouse?

No. Everything Hunter reads at this version is in the repository.

Warehouse access would add what is actually deployed, what it costs, row counts
and partitioning checks. That is one of the eight areas of the score, and
without it that area is excluded and its weight shared across the rest.

## Will it change anything in my repository?

`hunter init` writes two configuration files. Nothing else writes to your
repository, ever. No commits, no branches, no pull requests, no writes to your
warehouse.

Those are licence terms, not just how it currently behaves.

## Does it read my data?

No. Metadata and aggregate counts only. Where warehouse access is granted at
all, it is read-only and scoped to metadata and job history. No row-level data
is read, stored or published.

## How is this different from dbt-score or dbt-project-evaluator?

Those work inside dbt and check dbt. Hunter's own effort goes on the joins
between dbt and everything around it:

- The design against the repository. Was what was built what was specified?
- The repository against the reporting layer. Will a renamed column break a
  dashboard?
- The repository against the people in it. Who can close this gap?
- One sprint against the last. Did anything improve?

Wrapping the existing tools as inputs is the intention and is not done yet. If
you already run them, keep running them.

## The score seems high given how many findings there are

That happens, and it is worth understanding rather than dismissing.

An area's score is the share of its checks that passed. A repository with 761
findings across tens of thousands of checks genuinely passes most of them.

What a mean hides is a rule that failed on *everything*. So those are reported
separately, above the number:

```
  Missing everywhere it was checked:
    63 of 63  Who owns what
```

Read those first. "89.5, and no table has an owner" is the honest reading, and
both halves are true.

## Can I change the weights?

Yes, in `hunter.yml`. They must total 100 and every area needs one.

Every difference from the house standard appears on the site's conventions page
with the reason given for it. That is the point of asking for a reason: a weight
nobody can see is a weight nobody will accept.

## Can I switch a rule off?

Two ways, for two purposes.

**In `hunter.yml`**, for the whole repository, when the rule does not apply to
how you work. It needs a reason and the reason is published.

**In the register**, for particular tables and with an end date, when the
finding is true and is not being fixed yet. It still appears on the site, with
its reason, and comes back automatically when the date passes.

Nothing can be hidden permanently by accident.

## Why does it say "not measured" instead of zero?

Because a zero reports a failure and there was no measurement.

An area Hunter could not measure is excluded and its weight shared across the
rest, so the score is still out of 100. Which areas, and why, are on a page of
its own.

## Why is my table reported as "built off-plan"?

It exists and appears on no design.

Three responses, all valid: add it to the design, retire it, or accept it in the
register with a reason and a review date. Accepting it keeps it on the site as
an approved exception rather than as a fault.

## It says a table is switched off. What does that mean?

It is built, and disabled, usually by a dbt variable or `enabled: false`. The
code exists and nothing is being produced from it.

This is its own state because calling it "designed, not started" would be wrong,
and one real repository has six of them.

## Why does it say "behaves like a fact" about my dimension?

It reads the shape of the columns: how many foreign keys, how many figures, how
many descriptive columns, whether there is a date grain.

Below the confidence floor it says so rather than naming a type:

> not clear from its columns (closest guess fact, confidence 0.3, below the 0.7
> needed to say)

Low-confidence judgements are suggestions and do not affect the score. Without
warehouse access there is no uniqueness ratio or row count, so Hunter caps what
it will claim.

## Why are so many findings on tables I did not write?

They may be from an installed package. Those are reported for completeness and
never scored: holding you to your own conventions on code you would have to fork
to change produces findings nobody can act on.

The catalogue page marks them.

## Why does the reconciliation say a table is designed but not built, when it is?

Probably a name difference the normalised matching could not bridge. One real
repository names the same entity three ways across its business model, its
design and its repository.

Settle any specific case with an `implements` entry in the register.

## Can it run on Snowflake, or with something other than LookML?

Not yet. Each is one file in `ingest/`, once there is somebody who needs it.

## Can I get a true before-and-after on a pull request?

Yes, by giving Hunter the report from before the change:

```bash
hunter check --previous-report before.json
```

Without one it lists findings on the files the change touched, which is a
superset, and says so in the comment.

## Will it fail my build?

Not unless you ask it to. Advisory is the default and never fails anything.

`ratchet` fails on a real regression below your committed baseline, and it
distinguishes real movement from movement caused by upgrading Hunter, so an
upgrade never fails a build. `gate` fails below a threshold you set.

## Why did my score change when I upgraded Hunter?

It should not, and if it does Hunter tells you.

The baseline records which Hunter version, house ruleset and score model
produced it. Where any differs, the movement is attributed to the upgrade and
reported apart from real change. Ratchet mode ignores it.

## Can I compare two repositories' scores?

Only if the same sources were available for both. A repository with no design
files is scored on six areas; one with everything on seven. The "what was not
checked" page says which.

Comparing a repository against its own baseline is always meaningful. Comparing
two repositories usually is not.

## How long does it take?

Two seconds on a 280-model repository. Three and a half with the site built.

## Will it get slow on a large repository?

The budget is five minutes for 400 models and it currently runs in two seconds,
so there is room. History is read in one pass rather than one call per file, and
graph traversals are memoised.

## Where does the number come from, exactly?

Every deduction names its rule, its object and its file, and the whole ruleset
is published on the site's conventions page. `report.json` has the arithmetic
per area: points lost, points available, and the weight applied.

## Who can see the site?

Wherever you publish it. Hunter builds static HTML and JSON and does not host
anything.

If you publish to GitHub Pages from a private repository outside GitHub
Enterprise Cloud, note that the site is **public** and its files are
downloadable by anyone. A browser-side password check is not access control. See
[In CI](ci.md).

## Is it open source?

No. Proprietary, all rights reserved. See
[LICENSE](https://github.com/sav-sus/Hunter/blob/main/LICENSE).
