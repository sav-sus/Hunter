# In CI

Hunter ships as a composite GitHub Action, published by Rittman Analytics and
wrapping the command line. It calls
the same commands you would run locally, so CI and local results are the same by
construction rather than by discipline.

## The workflow

```yaml
name: Hunter

on:
  pull_request:
  push:
    branches: [main]
  schedule:
    - cron: '0 6 * * 1'

permissions:
  contents: read
  pull-requests: write

jobs:
  hunter:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: sav-sus/Hunter@v0.1.0
        with:
          mode: advisory
          publish: ${{ github.event_name == 'push' }}
```

`hunter init` writes this file for you.

## Two things that are easy to get wrong

**`fetch-depth: 0`.** The default checkout is shallow and has no history, so
attribution and the window report silently produce nothing. Hunter reports a
shallow clone rather than staying quiet about it, but the fix is here.

**Never reference the Action at `@main`.** Pin a tag. A repository's score must
not move because somebody pushed a commit to Hunter.

## Inputs

| Input | Default | What it does |
|---|---|---|
| `mode` | `advisory` | `advisory`, `ratchet` or `gate` |
| `working-directory` | `.` | The repository root to read |
| `config` | | Path to `hunter.yml`. Found automatically if omitted |
| `manifest` | | Path to `manifest.json`, if not where the ruleset says |
| `publish` | `false` | Build the site as well as the report |
| `comment` | `true` | Post or update the pull request comment |
| `previous-report` | | A `report.json` from before the change, for a true before-and-after |
| `hunter-version` | `0.1.0` | Which Hunter version to install |
| `python-version` | `3.12` | Which Python to run under |

## Outputs

| Output | What it is |
|---|---|
| `score` | The score out of 100 |
| `grade` | The letter grade |
| `delta` | Movement against the baseline, if there is one |
| `report` | Path to `report.json` |

## Modes

| Mode | Behaviour | When to use it |
|---|---|---|
| `advisory` | Never fails a build | Always, for the first few weeks |
| `ratchet` | Fails on a real regression below the baseline | Once a baseline is committed and the team is used to the comments |
| `gate` | Fails below `scoring.fail_under` | Once a threshold has been agreed rather than imposed |

Start on advisory. A tool that fails builds in its first week gets switched off
in its second, and then none of the rest of this matters.

Ratchet mode distinguishes real movement from movement caused by upgrading
Hunter, so an upgrade never fails a build.

## What it does on each event

| Event | What happens |
|---|---|
| A pull request | Scores, writes a run summary, posts or updates one comment, uploads the report |
| A push to main | Scores, builds the site if `publish` is set, uploads both |
| The weekly schedule | The same as a push. Catches drift that arrives from outside the repository |

The weekly run is worth keeping. A design file edited outside a pull request, or
a reporting change made in Looker, changes the answer without anything being
pushed.

## The comment

One comment, edited in place on each push. A new comment on every push is how a
tool gets muted.

It carries the score and its movement, the findings on what this change touches,
what those tables reach, and a collapsed diagram of the affected tables.

Standing debt stays on the site. The comment is about this change.

Needs `pull-requests: write`. Without it the score and the summary still work
and the comment step is skipped.

## A true before-and-after

By default the comment lists findings on the files the change touched, which is a
superset of what the change introduced, and says so.

For an exact diff, give it the previous report:

```yaml
      - name: Fetch the report from main
        uses: actions/download-artifact@v4
        continue-on-error: true
        with:
          name: hunter-report
          path: previous
          github-token: ${{ github.token }}
          run-id: ${{ needs.find-baseline.outputs.run-id }}

      - uses: sav-sus/Hunter@v0.1.0
        with:
          previous-report: previous/report.json
```

Worth it once the comment is being read. Not worth it on day one.

## Publishing the site

Set `publish: true` on pushes to main and the site is built and uploaded as an
artifact. Serving it somewhere is a separate decision.

If your organisation is on GitHub Enterprise Cloud, private Pages restricts a
site to people with read access to the repository, which is the straightforward
option. Outside Enterprise Cloud a private repository still publishes a
**public** Pages site, and its HTML and JSON are downloadable by anyone, so
Pages is not an option there. Cloud Run behind IAP is the fallback. A
browser-side password check is not access control.

## Running it without GitHub Actions

Nothing in Hunter depends on Actions. In any CI system:

```bash
pip install "rittman-hunter[site] @ git+https://github.com/sav-sus/Hunter@v0.1.0"
hunter score . --out report.json
hunter docs build . --out site
```

Exit code 1 means the gate failed, 2 means it could not run.

## What it never does

No writes to your warehouse. No commits, no branches, no pull requests. No
row-level data read, stored or published. Where warehouse access is granted at
all it is read-only and scoped to metadata and job history.

Those are licence terms, not only design intent.
