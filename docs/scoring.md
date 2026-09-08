# The score

<p class="lede">Deterministic arithmetic. No language model touches any part of
it, and the same inputs give the same number every time.</p>

## The eight areas

Weights come from the Rittman Analytics standard and total 100. They are
published on the report's own rules page, because a weight nobody can see is a
weight nobody will accept.

| Area | Weight | What it covers |
|---|---|---|
| What is checked automatically | 18 | Key tests, relationship tests, coverage weighted by reach |
| Does what was built match the design | 15 | Design against manifest, keys, relationships, off-plan builds |
| How the tables fit together | 13 | Fanout, rejoins, dead tables, layer bypass, exposed working steps |
| What is written down | 13 | Table and column descriptions, owners, staleness, design notes |
| Do the reports still match the data | 13 | Report fields against columns, generated-schema drift, exposures |
| Are the house rules followed | 13 | Naming, layering, SQL structure, hardcoded references |
| Are the tables the shape they claim | 8 | Entity type correctness, surrogate keys, declared against observed grain |
| What it costs to run | 7 | Needs warehouse access. Not read at this version |

## How an area is scored

A weighted mean of its rules' pass rates, each rule weighted by its own points.

```
rule loss rate = points lost on that rule / points that rule could have lost
area score     = 100 x (1 - sum(rule points x loss rate) / sum(rule points))
```

<div class="key" markdown>
**Every rule counts what it examined, not only what failed.** So the report can
say "73, because 57 of 63 tables have no description and 63 of 63 name no
owner", and you can check the arithmetic. Without a denominator, a score is
283 points lost out of what?
</div>

??? note "Why not total points lost over total available"

    Because a rule examining 230 tables would contribute a denominator 70 times
    larger than one examining 3. A mostly-passing rule then dilutes every other
    rule in its area, and **adding a rule would raise the score** whether or
    not anything improved.

    That is exactly the movement Hunter is built not to show as real change.
    Weighting per rule removes it: adding a rule changes the mix rather than
    inflating a denominator.

??? note "Partial gaps cost less than total ones"

    A rule reporting once per table but counting many things inside it scales
    its deduction by the share that failed. A table missing 1 of 58 column
    descriptions loses a fraction of what one missing all 58 loses, and both
    count as one check.

    One real repository documents 1,615 of 1,615 columns and 0 of 54 tables.
    Rolling those together would call it undocumented, which is wrong and would
    cost Hunter its credibility on the first run.

## Exposure weighting

A finding costs more where more depends on the object. Hunter counts tables
downstream, report fields, explores and declared exposures.

| Detail | Value |
|---|---|
| Growth | With the logarithm of the reach |
| Cap | 3, so one heavily used table cannot dominate |
| Counted double | Reverse-ETL destinations and declared exposures |
| Switch off with | `scoring.exposure_weighting: false` |

Both the numerator and denominator carry it, so an area can reach 0 but never
go below it.

## Areas that were not measured

An area with no runnable rule, or nothing of its kind in the repository, is
excluded. Its weight is shared across the rest, and the report names it.

```
   98.3  A  Are the tables the shape they claim
      -  -  What it costs to run                  not measured
```

Without this, a repository with no warehouse access would be scored out of 93
and look worse than it is, for a reason that has nothing to do with the
repository. Scoring it zero is worse still: it reports a failure where there
was no measurement.

## Systemic gaps

Reported apart from the number, and above it.

```
  Missing everywhere it was checked:
    63 of 63  Who owns what
    54 of 54  Do the reports still match the data
```

A rule that failed on everything it examined is one decision nobody has taken,
not many defects. "No table names an owner" is a single conversation, and a
weighted mean leaves it looking like a rounding error.

<div class="key" markdown>
**This exists because of a real result.** A repository scored 89.6, grade A,
while no table had an owner and none declared an exposure. Both facts were true.
Only one was visible.
</div>

A rule needs at least three objects before failing on all of them counts. Rules
that report what Hunter could not check are excluded, since "Hunter could not
resolve this table name" is not something the team failed to do.

## Grades

| Score | Grade | Reading |
|---|---|---|
| 85 to 100 | A | Well maintained. Safe to build on |
| 70 to 84 | B | Sound, with known gaps |
| 55 to 69 | C | Workable but accumulating risk |
| 40 to 54 | D | Fragile. Changes are likely to break things |
| 0 to 39 | E | Unmanaged. Treat findings as a remediation backlog |

The number is always the headline and the reading always sits beneath it, never
in place of it. Shown only "Sound, with known gaps", a reader cannot tell 70
from 84, or whether last month was better.

## The baseline

```bash
hunter baseline
git add .hunter/baseline.json && git commit -m "Record the starting score"
```

An existing repository starts where it starts and only has to improve. Without
a baseline, installing Hunter on a mature project produces a low number and an
argument rather than a direction of travel.

### Movement caused by an upgrade

The baseline records which Hunter version, house ruleset and score model
produced it. Where any differs, the movement is attributed to the upgrade and
reported apart from real change.

| Measure | Value |
|---|---|
| Starting point | 82 |
| Now | 87 |
| Change | +5 |
| Of which caused by an upgrade | +5 |
| Of which real change | 0 |

Ratchet mode only fails on real change, so upgrading Hunter never fails a
build.

??? note "Why the whole movement is attributed to the upgrade"

    Hunter cannot separate the two exactly without re-running the old
    arithmetic, which it does not carry. So it attributes all of it to the
    version change and says so, rather than presenting an upgrade artefact as
    something somebody would be asked to explain.

## What does not score

| | Behaviour |
|---|---|
| **Low-confidence findings** | Below `scoring.min_confidence_to_score` (0.7) they are reported as suggestions and left out |
| **Silenced findings** | Appear with their reason and expiry, cost nothing, come back when the date passes. Nothing is hidden |
| **Vendored code** | Models from installed packages are reported, never scored. One real repository has 57 of 299 |

??? note "What a low-confidence finding looks like"

    > not clear from its columns (closest guess fact, confidence 0.3, below the
    > 0.7 needed to say)

    Entity inference is the main case. Without warehouse access there is no
    uniqueness ratio and no row count, so the judgement rests on column shape
    and Hunter caps what it claims at 0.65 rather than 0.85.

    Holding a team to their own conventions on package code they would have to
    fork to change produces findings nobody can act on, which is why vendored
    models are excluded.

## Failing a build

| Mode | Behaviour |
|---|---|
| `advisory` | Never fails. The default |
| `ratchet` | Fails on a real regression below the baseline. Upgrade movement does not count |
| `gate` | Fails below `scoring.fail_under` |

Advisory is the default because a tool that fails builds in its first week gets
switched off in its second.

## Checking the arithmetic

Everything is in `report.json`.

```json
{
  "dimension": "documentation",
  "score": 77.2,
  "weight": 13.0,
  "effective_weight": 14.0,
  "points_lost": 274.3,
  "points_available": 1026.7,
  "finding_count": 135,
  "scored": true
}
```

The report's rules page lists every rule, its points, whether it ran and any
difference from the standard. Any number traces back to the rule that produced
it, which is what makes it survive being challenged.

The example project's whole report is pinned in a committed file, so a change
to the arithmetic is reviewed as a diff rather than discovered in somebody's
report. See [Contributing](contributing.md).
