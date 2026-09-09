# Run it on every pull request

<p class="lede">One workflow file, written by <code>hunter init</code>. Every
pull request gets the score and the three sync checks. Every push to main
rebuilds the dashboard and publishes it. Nobody runs anything by hand.</p>

## Before the first run: two secrets

Every Hunter command reads dbt's manifest, and dbt writes it under `target/`,
which is gitignored. A CI checkout never has one. So the workflow builds it
first with `dbt parse`, and `dbt parse` needs a profile it can resolve.

| Secret | What it holds |
|---|---|
| `DBT_PROFILES_YML` | The whole contents of a `profiles.yml` for CI. The header of the generated workflow shows one for BigQuery with a service account |
| `DBT_KEYFILE_JSON` | The service account key as JSON. The workflow writes it to `/home/runner/.dbt/keyfile.json`, the path the profile points at. Not needed for adapters that authenticate another way |

Add both under Settings, Secrets and variables, Actions. Without the first,
the manifest job stops with a message naming it, and nothing else runs.

<div class="key" markdown>
**Already have a manifest?** If your own dbt job publishes `manifest.json`
somewhere, replace the steps of the `manifest` job with one that fetches it to
the path in `MANIFEST`, keep the upload step, and skip both secrets. `dbt parse`
does not connect to the warehouse, but dbt will not start without a profile.
</div>

## The workflow

Six jobs. Each shows as its own line on the pull request.

| Job | When | What it does |
|---|---|---|
| Build the dbt manifest | Every run | Installs the dbt version the repository pins, runs `dbt deps` and `dbt parse`, and hands `manifest.json` to the other jobs |
| Score | Every pull request and push | Scores the repository and posts one comment, edited in place |
| LookML sync | Every pull request and push | Does the reporting layer still match the tables? |
| Droughty sync | Every pull request and push | Was the generated schema applied, and is it current? |
| Modelling sync | Every pull request and push | Does what exists match what was designed and asked for? |
| Publish | Push to main only | Puts the rebuilt dashboard on GitHub Pages |

There is no path filter. A new layer or a new model is detected by Hunter
itself, so the file never needs editing as the warehouse grows.

The file `hunter init` writes carries a long header comment covering the
secrets, then this:

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

env:
  DBT_PROJECT_DIR: analytics_warehouse
  MANIFEST: analytics_warehouse/target/manifest.json

jobs:
  manifest:
    name: Build the dbt manifest
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install --quiet "dbt-core~=1.10" "dbt-bigquery~=1.9"
        # pinned to match requirements.txt; unpinned, with a note, if no pin was found
      - name: Write the dbt profile from the repository secrets
        env:
          DBT_PROFILES_YML: ${{ secrets.DBT_PROFILES_YML }}
          DBT_KEYFILE_JSON: ${{ secrets.DBT_KEYFILE_JSON }}
        run: |
          # Fails with a message naming the secret if it is missing, then
          # writes ~/.dbt/profiles.yml and ~/.dbt/keyfile.json
      - run: dbt deps
        working-directory: ${{ env.DBT_PROJECT_DIR }}
      - run: dbt parse
        working-directory: ${{ env.DBT_PROJECT_DIR }}
      - uses: actions/upload-artifact@v4
        with:
          name: dbt-manifest
          path: ${{ env.MANIFEST }}

  hunter:
    name: Score
    needs: manifest
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/download-artifact@v4
        with:
          name: dbt-manifest
          path: analytics_warehouse/target
      - uses: sav-sus/Hunter@v0.1.0
        with:
          mode: advisory
          manifest: ${{ env.MANIFEST }}
          publish: ${{ github.event_name != 'pull_request' }}
      - if: github.event_name != 'pull_request'
        uses: actions/upload-pages-artifact@v3
        with:
          path: out/site/_built

  lookml-sync:
    name: LookML sync
    needs: manifest
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          name: dbt-manifest
          path: analytics_warehouse/target
      - uses: sav-sus/Hunter/actions/lookml-sync@v0.1.0
        with:
          manifest: ${{ env.MANIFEST }}

  # droughty-sync and modelling-sync: the same shape as lookml-sync

  publish:
    name: Publish the dashboard
    if: github.event_name != 'pull_request'
    needs: hunter
    runs-on: ubuntu-latest
    permissions:
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deploy.outputs.page_url }}
    steps:
      - id: deploy
        uses: actions/deploy-pages@v4
```

`hunter init` writes this file to `.github/workflows/hunter.yml`. The sync
checks start on `fail-on: never`, which reports and never fails a build. Turn
one up to `high` once the team reads the comments. See
[Check the layers agree](sync-checks.md).

<div class="key" markdown>
**`fetch-depth: 0` matters.** The default checkout is shallow and has no
history, so attribution and the window report produce nothing. Hunter reports a
shallow clone rather than staying quiet about it, but the fix is here.

**Never reference the Action at `@main`.** Pin a tag, or a repository's score
moves because somebody pushed a commit to Hunter.
</div>

## How the checks are named, and the logo

A check on a pull request is named `<workflow name> / <job name>`. Both come
from the workflow file, so rename them there. The workflow above shows as
**Hunter / Score**, **Hunter / LookML sync**, **Hunter / Droughty sync** and
**Hunter / Modelling sync**.

GitHub puts its own icon next to every check that comes from Actions and
offers no way to change it. The only way to get a different icon on the check
row itself is a GitHub App, which is a separate piece of infrastructure and not
part of Hunter.

What Hunter can do is put the Rittman Analytics logo at the top of the pull
request comment and of each sync summary. Set a public URL in `hunter.yml`:

```yaml
branding:
  logo_url: https://<organisation>.github.io/<repository>/assets/rittman-analytics.png
```

It is off by default because GitHub only renders images it can fetch. A raw
file URL from a private repository shows as a broken image. The published
documentation site, once Pages is on, serves the logo at the path above.

## The score action

The rest of this page is about the first job, the composite action at the
repository root. It wraps the command line and nothing else, so CI and local
results agree by construction.

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
in its second. Ratchet mode tells real movement from upgrade movement, so
upgrading Hunter never fails a build.

## What it does on each event

| Event | What happens |
|---|---|
| A pull request | Scores, writes a run summary, posts or updates one comment, uploads the report |
| A push to main | Scores, builds the site, and hands it to the publish job, which puts it on GitHub Pages |
| The weekly schedule | The same as a push. Catches drift that arrives from outside the repository |

The weekly run is worth keeping: a design file edited outside a pull request,
or a change made in Looker, moves the answer without anything being pushed.

## The comment

One comment, edited in place on each push. A new comment on every push is how a
tool gets muted.

It carries the score and its movement, the findings on what this change
touches, what those tables reach, and a collapsed diagram of the affected
tables. Standing debt stays on the site; the comment is about this change.

Needs `pull-requests: write`. Without it the score and summary still work and
the comment step is skipped.

??? note "Getting a true before-and-after"

    By default the comment lists findings on the files the change touched,
    which is a superset of what the change introduced, and says so. For an
    exact diff, give it the report from before.

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

Covered on its own page: [Publish the dashboard](publish.md). In short, set the
repository's Pages source to GitHub Actions once, and the publish job does the
rest on every push to main.

??? note "Running it without GitHub Actions"

    Nothing in Hunter depends on Actions. In any CI system:

    ```bash
    pip install "rittman-hunter[site] @ git+https://github.com/sav-sus/Hunter@v0.1.0"
    hunter score . --out report.json
    hunter sync --root . --out sync.json
    hunter docs build . --out site
    ```

    Exit code 1 means the gate failed, 2 means it could not run.

## What it never does

No writes to your warehouse. No commits, no branches, no pull requests. No
row-level data read, stored or published. Where warehouse access is granted at
all it is read-only and scoped to metadata and job history.

Those are licence terms, not only design intent.
