# The solution

Hunter reads a repository and reports on it. It changes nothing.

It is a Rittman Analytics tool, used on engagements and offered with a support
plan.

## What it produces

**A score out of 100**, with a grade for each of eight areas, every deduction
traceable to a rule, an object and a line. The number is always the headline
and the reading of it always sits beneath, never in place of it.

**A reconciliation**, one row per entity, showing whether the business asked for
it, whether it was designed, whether it was built and whether it is live. This
is the page a non-technical reader can act on without opening a single file.

**A list of what needs doing**, ranked by how much the score would recover,
each item saying what breaks if it is left.

**A dashboard**, one screen, in Rittman Analytics colours. Nine bands, each
answering one question: the number, what nobody has decided, where the points
are going, how much of the plan is real, every rule at once, which tables
everything is built on, and what to fix first. It is one self-contained HTML
file, so it can be sent as an attachment. Everything is inlined except the
diagram library, which is pinned and degrades to source text.

**A site**, twelve pages behind the dashboard, readable by an engineer and by
someone who has never seen SQL. Plain language sits above the detail on the same
page rather than in a separate mode nobody finds.

**Three CI checks that can fail a build.** LookML sync, Droughty sync and
Modelling sync, each its own GitHub Action, each answering one question about
whether one layer has drifted from another. Each is a slice of the rules the
score already runs, so a sync check and the score cannot contradict each other.

**A pull request comment**, short, specific to the change, with what it reaches.

## How each problem is addressed

| Problem | What Hunter does |
|---|---|
| Debt merged unseen | Comments on each pull request with the score, the findings on what changed, and what those changes reach |
| A lead cannot see across the repository | One score, seven area grades, and a list of what to do first. No code reading required |
| Working steps not distinguished from finished tables | Classifies every table as temporary or permanent and records which signal decided, so the answer can be argued with |
| No attribution | Attributes every table to the commit, author and pull request that created it. Routes by owner, reports by team |
| Modelling unchecked | Infers what each table behaves like from its column shape and compares that against what its name claims |
| Layers drift | Maps every reporting field to the column it reads, so a rename shows up as a broken field |
| No cost visibility | Not built. Needs warehouse access, milestone M2 |
| No measure of improvement | A committed baseline, so a repository starts where it starts and only has to improve, plus a window report of what changed |

## The four additions

These were asked for during the build and are not in the original
specification.

**An authored register.** A file where the team records what it has decided
about particular tables: that one is temporary on purpose, that an off-plan
build is accepted, who owns what, what one row means. Plain information needs no
justification. An exception or an approval needs a reason, and a silenced rule
needs an end date, so nothing goes quiet permanently.

**Three model levels rendered.** The business model, the design and what was
built, drawn side by side per area. Hunter draws them rather than only embedding
the authored diagrams, because a hand-maintained diagram drifts and Hunter knows
the real state.

**A five-point alignment chain.** The original specification reconciles three
places. This runs conceptual, logical, design, repository and warehouse, so a
gap points at a specific step rather than at "somewhere".

**A Droughty scan without warehouse access.** Droughty generates dbt tests and
descriptions by introspecting a warehouse. Running it needs a credential. But a
project that commits its output can have that output checked from files alone,
and that is the half that matters for installing at a client.

## Who it is for, and where they meet it

| Who | What they need | Where |
|---|---|---|
| Team or engagement lead | An overview without reading code, and where to point the team next | The site: overview, reconciliation, what needs doing |
| Reviewer | To know what a change breaks before approving it | The pull request comment |
| Junior engineer | To learn the conventions through immediate feedback | The pull request comment, the conventions page |
| Non-technical stakeholder | To understand what exists, what is coming, and whether it can be trusted | The site: overview, business model, reconciliation |
| Account lead | Evidence of progress across an engagement | The site: score trend, coverage, the window report |
| Sales and delivery | A baseline assessment of a new repository | The command line, run locally, one report |

## Where it runs

| Surface | What it is | When |
|---|---|---|
| Command line | `hunter score`, `align`, `check`, `explain`, `showcase`, `docs build` | Run locally by a consultant |
| GitHub Action | A composite action wrapping the command line | On a pull request, a push to main, and weekly |
| Pull request comment | Score, findings on the change, what it reaches, a collapsed diagram | When a pull request opens or updates |
| Site | Twelve pages, published | On a push to main, plus a scheduled refresh |

The command line is the only place logic lives. The Action and the site are
thin wrappers over it. That is what makes a run in CI and a run on a laptop give
the same answer by construction rather than by discipline.

## What it will never do

Hunter never modifies code, never opens a commit or a pull request, and never
writes to a warehouse. Where warehouse access is granted it is read-only and
scoped to metadata and job history. It reads metadata and aggregate counts: no
row-level data is read, stored or published.

These are licence terms, not only design intent. See [`LICENSE`](../LICENSE).
