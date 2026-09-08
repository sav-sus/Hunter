# How it works

## The pipeline

Six steps. Only the second touches the outside world.

```
1  config      built-in defaults, then the house ruleset, then hunter.yml,
               then the register, then per-model overrides
2  ingest      the dbt manifest, the design, the diagrams, the reporting layer,
               git history, and the Droughty output
3  normalise   one internal model, the dependency graph, the alignment chain
4  check       every rule that has the data it needs, each returning findings
               with evidence
5  score       weights, exposure weighting, comparison with the baseline
6  emit        report.json, then diagrams, site pages, pull request comment
```

Steps 1 and 3 to 6 are pure functions over what step 2 read. That is what makes
the same inputs give the same output, and it is enforced by a golden-file test
rather than assumed.

Entry point: `src/hunter/run.py`. The command line and the Action both call it
and add nothing.

## The rule that matters

Every reader writes into one normalised model in `src/hunter/model/entities.py`,
and no check ever reads a raw source. A check that opens `manifest.json` is a
bug.

The point is replaceability. Adding Snowflake, or a semantic layer other than
LookML, touches one file in `ingest/` and nothing else. Without the rule, a
second warehouse would mean editing every check.

## The readers

| Reader | Reads | Notes |
|---|---|---|
| `ingest/manifest.py` | `manifest.json`, and `catalog.json` where present | Reads disabled nodes as their own state. Normalises tests by what they prove, not which package they came from |
| `ingest/dbml.py` | The authored design | Normalises known dialect variants before parsing, then falls back to parsing table by table so one bad block costs one table |
| `ingest/diagrams.py` | The conceptual and logical Mermaid diagrams | Learns the status colour code from the diagram's own legend. Treats status as a claim to check, never as truth |
| `ingest/lookml.py` | Views, fields, explores | Folds refinements into the views they refine. Skips derived tables and records that it did |
| `ingest/droughty.py` | The committed generated schema, config, description blocks and introspected design | Reads `test_ignore` and `test_overwrite` as authored intent, so a decision the team recorded is never re-reported |
| `ingest/git.py` | History | One `git log` pass, not one per file. Reports a shallow clone rather than silently producing no attribution |

Hunter does not import dbt. It reads a manifest file and shells out to
`dbt parse` only when asked. That keeps the dependency tree small and avoids
adapter version conflicts.

## The four model levels

The distinction is what makes the alignment chain possible.

| Level | What it is | Where it comes from |
|---|---|---|
| Conceptual | A business entity, in business language, no columns | An authored Mermaid diagram, or the register |
| Designed | A DBML table: columns, keys, relationships, what one row means | Authored DBML files |
| Built | A dbt model: what the repository actually produces | The manifest |
| Deployed | A warehouse object | Not read yet. Reported as not checked |

Names differ between levels, and on a real repository they differ a lot. The
conceptual diagram says `wh_commerce__demand_orders` where the design says
`wh_commerce__demand_order_fact`. Exact matching found 3 of 72. Normalising the
layer prefix, the entity suffix, the plural and the domain alias found 36. The
rest is a real gap, and the alignment check reports it as one.

Where a normalised match lands on two candidates, Hunter reports it as
ambiguous rather than picking one. Picking one silently produces a wrong
reconciliation row that reads as fact.

## The alignment chain

One row per entity across five points, in `src/hunter/model/align.py`. Each
link reports separately, so a gap points at a step.

| State | Meaning |
|---|---|
| Designed and delivered | Working as intended |
| Built, not deployed | The code exists, has not reached production |
| Built, switched off | The code exists but is disabled, so nothing is produced from it |
| Designed, not started | On the plan, no work done |
| Built off-plan | Delivered but never designed, so undocumented and unowned |
| Built off-plan, approved | Accepted as an exception, with a reason and a review date |
| Off-plan, not deployed | Work in progress outside the plan, or abandoned |
| Live without code | Something outside the project is producing this |
| Untracked table | In production, nobody designed or built it here |
| On the business model only | Agreed with the business, not designed yet. The design backlog |
| On the data flow diagram only | Named in the flow diagram, no design and no model of its own |

Four of these were added during the build because real data required them. See
[06-what-the-pilot-found.md](06-what-the-pilot-found.md).

Without warehouse access the last column reports "not checked" rather than
"absent". Assuming a table is missing because Hunter did not look is worse than
saying it did not look.

## The check framework

Every rule is declared in one place with its area, severity, points and a
plain-language consequence template. There are no thresholds or point values
buried in check code.

A check module exposes one function:

```python
def run(context: CheckContext) -> Findings
```

and builds findings through `context.finding(...)`, which applies rule
overrides, silences and exposure weighting centrally. A check that constructs a
finding directly bypasses all of that.

Two framework decisions carry weight.

**Checks declare what they examined, not only what failed.** Without that, a
score is a number with no denominator: 283 points lost out of what? With it, the
scorecard can say "73, because 57 of 63 tables have no description and 63 of 63
name no owner", and a reader can audit it.

**Aggregating rules scale their deduction.** A table missing 1 of 58 column
descriptions does not cost what one missing all 58 costs, while the denominator
stays one check per table. Table-level and column-level gaps then weigh
comparably.

## Consequence lines

Every finding carries a line in business terms:

> Nothing checks that these references in daily store performance point at rows
> that exist. Where they do not, joined figures come out low and the rows simply
> vanish.

Not:

> high severity: relationships test missing

The line is a template held with the rule and filled from that finding's own
evidence. Nothing is generated. That is deliberate: there is no path by which a
sentence could appear without a deterministic finding behind it, which is what
makes the plain-language layer trustworthy rather than decorative.

## Package layout

```
src/hunter/
  run.py                 the pipeline
  cli.py                 the commands
  enums.py               shared vocabulary, imports nothing
  config/
    schema.py            every threshold, as a typed field
    loader.py            five-level resolution with provenance
    register.py          the authored register
    house/ra-house-1.yml the standard, version-pinned
  ingest/                six readers, one per source
  model/
    entities.py          the normalised model
    graph.py             the dependency graph
    match.py             matching one entity across levels
    align.py             the five-point chain
    build.py             normalisation
    findings.py          findings, scores, coverage
  checks/
    base.py              rules, context, the one way a finding is made
    ...                  ten check modules
  score/
    engine.py            the arithmetic
    baseline.py          the committed starting point
  emit/
    report.py            report.json
    plain.py             the plain-language layer and glossary
    mermaid.py           diagrams
    markdown.py          the site
    pr_comment.py        the pull request comment
    showcase.py          the window report
    scaffold.py          hunter init
```

## Determinism

Required by the specification and enforced three ways.

1. Every collection is sorted before emitting. Unsorted dictionary iteration is
   the usual cause of output that differs between runs.
2. `generated_at` sits in `meta` and nowhere else, so two runs of one commit
   produce an identical scored payload.
3. A golden-file test runs the example project twice, compares the two, and
   compares both against a committed file. Any deliberate change requires
   regenerating that file, which puts the score movement into code review.

Verified: two independent runs against a 280-model repository produce identical
reports apart from the timestamp.

## Configuration

Five levels, each overriding the one above.

| Level | File | Owned by |
|---|---|---|
| Built-in defaults | Shipped in the package | Whoever maintains Hunter |
| House ruleset | `house/ra-house-1.yml`, version-pinned | Delivery leadership |
| Project | `.hunter/hunter.yml`, naming the house version it extends | The engagement lead |
| Register | `.hunter/register.yml` | Whoever is doing the work |
| Per-model | `meta.hunter` in a schema file | The model's author |

The merge records where every value came from. That is not a debugging aid: the
specification makes the divergence report a first-class output, so on a client
engagement the site shows how far the repository sits from the standard, which
is itself a finding.

Layer and entity lists merge item by item on their key, so a project overriding
one layer keeps the other five rather than having to restate them.

## Performance

| Step | Time on a 280-model repository |
|---|---|
| Full score, report written | 2.1 seconds |
| Score plus 255 site pages plus the MkDocs build | 3.5 seconds |

The budget is 5 minutes for 400 models without warehouse access.

Two things keep it there. Git history is read in one pass rather than one call
per file, which would be 280 subprocesses. Graph traversals are memoised,
because several checks walk the same subtrees.
