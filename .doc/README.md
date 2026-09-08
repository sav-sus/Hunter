# Rittman Hunter: the product record

A Rittman Analytics product.

Why Hunter exists, what it does, how it is built, what is left to build, and
what running it against a real repository taught us.

This folder is the internal record. It is written for whoever picks Hunter up
next: a new maintainer, a consultant scoping an engagement, or the same person
in six months. The user-facing documentation is in [`docs/`](../docs) and is
published as a site.

This folder is named `.doc` and so is hidden by default in most file listings.
The README and the published documentation both link to it.

## Read in this order

| File | What it covers |
|---|---|
| [01-the-problem.md](01-the-problem.md) | The eight problems Hunter was built for, in the words of the people who have them |
| [02-the-solution.md](02-the-solution.md) | What Hunter does about each one, who it is for, and where they meet it |
| [03-how-it-works.md](03-how-it-works.md) | The pipeline, the internal model, and the design rules that hold it together |
| [04-the-score.md](04-the-score.md) | How the number is worked out, and why it is worked out that way |
| [05-decisions.md](05-decisions.md) | Every decision taken, with the reason and what it rules out |
| [06-what-the-pilot-found.md](06-what-the-pilot-found.md) | Nine rules and two framework bugs that only real data exposed |
| [07-roadmap.md](07-roadmap.md) | What is built, what is next, and in what order |
| [08-not-built.md](08-not-built.md) | What is deliberately absent, and what it would take to add |
| [09-risks-and-open-items.md](09-risks-and-open-items.md) | What could go wrong, and what still needs someone to decide |

## Where things are

| Path | What it is |
|---|---|
| `src/hunter/` | The package. 45 modules |
| `src/hunter/config/house/ra-house-1.yml` | The Rittman Analytics standard, version-pinned |
| `examples/tiny-shop/` | A working example project, eight tables with one deliberate flaw each |
| `docs/` | The published documentation |
| `tests/` | 519 tests, including a golden file that pins the example's score |
| `action.yml` | The composite GitHub Action |
| `scripts/check_no_client_content.py` | Fails if client-identifying text reaches a tracked file |

## Where it stands

Milestone M0 is complete, plus four additions requested during the build.
Version 0.1.0.dev0, unreleased.

| Measure | Value |
|---|---|
| Rules | 77 across 7 scored areas |
| Tests | 519 |
| Source | 14,300 lines across 45 modules |
| Run time | 2 seconds on a 280-model repository |
| Requires a warehouse credential | No |
