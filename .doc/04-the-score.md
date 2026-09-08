# The score

A number between 0 and 100. Deterministic arithmetic only: no language model
touches any part of it.

## The eight areas

Weights live in the Rittman Analytics house standard and total 100. They are published on the
site's conventions page, because a weight nobody can see is a weight nobody
will accept.

| Area | Weight | What it covers |
|---|---|---|
| What is checked automatically | 18 | Key tests, relationship tests, coverage weighted by what depends on the table |
| Does what was built match the design | 15 | Design against manifest, keys, relationships, delivery coverage, off-plan builds |
| How the tables fit together | 13 | Fanout, rejoins, dead tables, layer bypass, exposed working steps |
| What is written down | 13 | Table and column descriptions, owners, staleness, design notes |
| Do the reports still match the data | 13 | Reporting fields against columns, Droughty drift, exposures |
| Are the house rules followed | 13 | Naming, layering, SQL structure, hardcoded references |
| Are the tables the shape they claim | 8 | Entity type correctness, surrogate keys, declared against observed grain |
| What it costs to run | 7 | Not built. Needs warehouse access, milestone M2 |

## How an area is scored

An area's score is a weighted mean of its rules' pass rates, each rule weighted
by its own declared points.

```
rule pass rate      = 1 - (points lost on that rule / points it could have lost)
area score          = 100 x (1 - sum(rule points x rule loss rate) / sum(rule points))
```

### Why not total points lost over total available

Because that has a perverse property. A rule examining 230 tables contributes a
denominator 70 times larger than one examining 3, so a rule that mostly passes
dilutes every other rule in its area. Adding a rule then raises the score
mechanically.

That matters beyond tidiness. The specification requires that a client on a
support plan never sees an apparent regression caused by an upgrade. A scheme
where adding a rule moves the score is a scheme that produces exactly that
movement, in the flattering direction, and then the opposite when a stricter
rule is added.

Weighting per rule removes it. Adding a rule shifts the mix; it does not inflate
a denominator.

### Exposure weighting

A finding costs more where more depends on the object. A missing test on a table
feeding twelve report fields costs more than the same gap on one nothing reads.

The weight grows with the logarithm of downstream reach and is capped at 3, so
one heavily used table cannot dominate the whole score. Both the numerator and
the denominator carry the weighting, so an area can reach 0 but never go below
it.

Reverse-ETL destinations and declared exposures count double: something outside
the project depending on a table is a stronger signal of use than one more
field.

### Aggregating rules

A rule reporting one finding per table but counting many things inside it
scales its deduction by the share that failed. A table missing 1 of 58 column
descriptions loses a fraction of the points one missing all 58 loses, while both
count as one check. Table-level and column-level gaps then weigh comparably,
which matters: one real repository documents 1,615 of 1,615 columns and 0 of 54
tables, and a scheme that rolled those together would call it undocumented.

## Areas that could not be measured

An area with no runnable rule, or nothing of its kind in the repository, is
excluded. Its weight is shared across the rest, and the report says which areas
were left out and why.

Without this, a repository with no warehouse access would be scored out of 93
and look worse than it is for a reason unconnected to the repository.

The alternative, scoring an unmeasured area as zero, is worse still: it reports
a failure where there was no measurement.

## Systemic gaps

Reported apart from the number, above it.

A rule that failed on every object it examined is one decision nobody has taken,
not many separate defects. "No table in the warehouse layer names an owner, 63
of 63" is a single conversation. A weighted mean is arithmetically right and
still leaves it looking like a rounding error.

This was added after reading a real result: the repository scored 89.6, grade A,
while no table had an owner and none declared an exposure. Both facts were true.
Only one of them was visible.

A rule needs at least three objects before failing on all of them counts as
systemic. Rules that report what Hunter could not check are excluded: "Hunter
could not resolve this table name" is not something the team failed to do.

## Grades and reading

One set of thresholds serves both the letter grade and the reading, so the two
cannot disagree.

| Score | Grade | Reading |
|---|---|---|
| 85 to 100 | A | Well maintained. Safe to build on |
| 70 to 84 | B | Sound, with known gaps |
| 55 to 69 | C | Workable but accumulating risk |
| 40 to 54 | D | Fragile. Changes are likely to break things |
| 0 to 39 | E | Unmanaged. Treat findings as a remediation backlog |

The number is always the headline. The reading always sits beneath it in its own
panel, never in place of it. A reader who is shown only "Sound, with known gaps"
cannot tell 70 from 84, and cannot tell whether last month was better.

## The baseline

An existing repository starts where it starts and only has to improve.

`hunter baseline` records the current score, the per-area scores, the commit and
the versions that produced them. Committing that file means later runs measure
movement rather than absolutes.

Without it, installing Hunter on a mature project produces a low number and an
argument rather than a direction of travel.

## Version movement

The baseline records which Hunter version, house ruleset version and score model
version produced it. Where any of those differ from the current run, the
movement is attributed to the upgrade and reported apart from real change.

Hunter cannot separate the two exactly without re-running the old arithmetic,
which it does not carry. So it attributes the whole movement to the version
change and says so, rather than presenting an upgrade artefact as a regression
someone would be asked to explain.

The `score_model_version` constant in `src/hunter/__init__.py` is bumped
whenever the arithmetic changes in a way that moves a number. Forgetting to bump
it is the failure mode this design guards against, and the golden-file test is
what catches it.

## Confidence and suggestions

A finding below the configured confidence floor is reported as a suggestion and
excluded from the score. Entity type inference is the main case: without
warehouse access there is no uniqueness ratio or row count, so the judgement
rests on column shape alone and Hunter caps what it will claim at 0.65 rather
than 0.85.

The reasoning is in the risk register. Entity inference producing false
positives loses trust early, and a tool that has lost trust is not used. A
suggestion that turns out right costs nothing; a scored finding that turns out
wrong costs the tool its audience.

## Silenced findings

A silenced finding still appears, with its reason and its expiry date. It costs
nothing.

Nothing is ever hidden. An exception the team agreed to is visible as an
exception, and it comes back automatically on its expiry date, so a silence
cannot become permanent by neglect.

## Failing a build

| Mode | Behaviour |
|---|---|
| Advisory | Never fails. The default |
| Ratchet | Fails on a real regression below the committed baseline. Movement attributed to a version change does not count |
| Gate | Fails below the threshold set in the project ruleset |

Advisory is the default because a tool that fails builds in its first week gets
switched off in its second.

Ratchet mode distinguishing real from version-attributed movement is the point
of separating them. Otherwise upgrading Hunter would fail a client's build.

## Worked example

The example project in `examples/tiny-shop` is eight tables with one deliberate
flaw per finding class. It scores 88.2 and triggers 28 rules across all seven
scored areas.

Its report is pinned in `tests/golden/tiny-shop.json`. Changing the arithmetic
changes that file, and the diff is part of the review. That is the mechanism
that stops a score moving without anyone deciding it should.
