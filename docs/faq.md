# Questions

<p class="lede">Grouped, shortest answers first. If yours is not here, the
answer is usually in <a href="../concepts/">the ideas behind it</a> or
<a href="../scoring/">the score</a>.</p>

## Access and safety

### Does it need access to my warehouse?

No. Everything Hunter reads is in the repository. Warehouse access would add
what is deployed, what it costs, row counts and partitioning. That is one of
eight areas; without it the area is excluded and its weight shared out.

### Will it change anything in my repository?

`hunter init` writes two configuration files. Nothing else, ever: no commits,
no branches, no pull requests, no writes to your warehouse. Licence terms, not
just current behaviour.

### Does it read my data?

No. Metadata and aggregate counts only. Any warehouse access is read-only and
scoped to metadata and job history. No row-level data is read, stored or
published.

### Who can see the report?

Wherever you publish it. Hunter builds static HTML and JSON and hosts nothing.

<div class="key" markdown>
**GitHub Pages from a private repository is public**, unless you are on GitHub
Enterprise Cloud. The files are downloadable by anyone. A browser-side password
check is not access control. See [In CI](ci.md).
</div>

## The score

### The score seems high given how many findings there are

An area's score is the share of its checks that passed, and 644 findings across
tens of thousands of checks still passes most of them.

What a mean hides is a rule that failed on *everything*, so those are reported
separately, above the number:

```
  Missing everywhere it was checked:
    63 of 63  Who owns what
```

Read those first. "89.6, and no table has an owner" is the accurate reading,
and both halves are true.

### Why does it say "not measured" instead of zero?

Because a zero reports a failure and there was no measurement. The area is
excluded and its weight shared out, so the score is still out of 100. Which
areas, and why, is on a page of its own.

### Can I change the weights?

Yes, in `hunter.yml`. They must total 100 and every area needs one. Every
difference from the standard is published with its reason: a weight nobody can
see is a weight nobody will accept.

### Can I compare two repositories' scores?

Only if the same sources were available for both: a repository with no design
files is scored on six areas, one with everything on seven. Comparing a
repository against its own baseline is always meaningful. Comparing two
repositories usually is not.

### Why did my score change when I upgraded Hunter?

It should not, and if it does Hunter says so. The baseline records which
version, ruleset and score model produced it. Where any differs, the movement
is attributed to the upgrade and reported apart from real change. Ratchet mode
ignores it.

### Where does the number come from, exactly?

Every deduction names its rule, its object and its file, and the whole ruleset
is on the report's rules page. `report.json` carries the arithmetic per area:
points lost, points available, weight applied.

## Findings

### Why is my table reported as "built off-plan"?

It exists and appears on no design. Three valid responses: add it to the
design, retire it, or accept it in [the register](register.md) with a reason and
a review date. Accepting keeps it on the report as an approved exception rather
than a fault.

### It says a table is switched off. What does that mean?

It is built and disabled, usually by a dbt variable or `enabled: false`, so
the code exists and nothing is produced from it. Its own state, because
"designed, not started" would be wrong. One real repository has six.

### Why does it say "behaves like a fact" about my dimension?

It reads the shape of the columns: foreign keys, figures, descriptive columns,
whether there is a date grain. Below the confidence floor it says so rather than
naming a type, and does not affect the score:

> not clear from its columns (closest guess fact, confidence 0.3, below the 0.7
> needed to say)

### Why are so many findings on tables I did not write?

Probably from an installed package. Those are reported for completeness and
never scored: holding you to your own conventions on code you would have to fork
to change produces findings nobody can act on.

### Why does it say a table is designed but not built, when it is?

Probably a name difference normalised matching could not bridge. One real
repository names the same entity three ways across its business model, design
and repository. Settle any specific case with an `implements` entry in the
register.

### Can I switch a rule off?

Two ways. In `hunter.yml` for the whole repository, when the rule does not
apply to how you work. In the register for particular tables and with an end
date, when the finding is true and is not being fixed yet. Nothing can be
hidden permanently by accident. See
[configuration](configuration.md#turning-a-rule-off-or-changing-what-it-costs).

## Running it

### Will it fail my build?

Not unless you ask. Advisory is the default and never fails anything. `ratchet`
fails on a real regression below your baseline, ignoring upgrade movement.
`gate` fails below a threshold you set.

### Can I get a true before-and-after on a pull request?

Yes, by giving Hunter the report from before the change:

```bash
hunter check --previous-report before.json
```

Without one it lists findings on the files the change touched, a superset, and
the comment says so.

### How long does it take?

Two seconds on a 280-model repository. Three and a half with the site built.

### Will it get slow on a large repository?

The budget is five minutes for 400 models and it runs in two, so there is room.
History is read in one pass rather than one call per file, and graph traversals
are memoised.

## About it

### How is this different from dbt-score or dbt-project-evaluator?

Those work inside dbt and check dbt. Hunter's effort goes on the joins between
dbt and everything around it.

| Join | The question |
|---|---|
| Design against repository | Was what was built what was specified? |
| Repository against reporting layer | Will this change break a dashboard? |
| Business model against design | Is what the business asked for even designed? |
| One sprint against the next | Is this getting better or worse? |

### Can it run on Snowflake, or with something other than LookML?

Not yet. Each is one file in `ingest/`, once there is somebody who needs it.

### Who makes it?

Rittman Analytics. It is used on client engagements and offered with a support
plan.

### Is it open source?

No. Proprietary, all rights reserved, Rittman Analytics. See
[LICENSE](https://github.com/sav-sus/Hunter/blob/main/LICENSE).
