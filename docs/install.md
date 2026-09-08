# Installing

## What you need

| Requirement | Notes |
|---|---|
| Python 3.11 or later | Tested on 3.11, 3.12 and 3.13 |
| A dbt `manifest.json` | Anywhere. Hunter is told where to look |
| Read access to the repository | Nothing else. No warehouse credential |

Hunter does not install dbt and does not import it. It reads a manifest file.

## As a tool

The usual way. Installs Hunter on its own, isolated from your project's
dependencies.

```bash
uv tool install "rittman-hunter[site] @ git+https://github.com/sav-sus/Hunter@v0.1.0"
```

The `[site]` extra pulls in MkDocs, which is only needed for `hunter docs
build`. Leave it off if you only want the score and the report.

With pip instead:

```bash
pipx install "rittman-hunter[site] @ git+https://github.com/sav-sus/Hunter@v0.1.0"
```

Check it worked:

```bash
hunter version
```

```json
{
  "hunter": "0.1.0",
  "house_ruleset": "1",
  "score_model": "1"
}
```

Those three versions are stamped on every report. The score model version is
what lets a later run tell real change from a change caused by upgrading
Hunter.

## Always pin a version

Never install from a branch. A repository's score must not move because someone
pushed a commit, and pinning is what guarantees that.

The same applies to the [GitHub Action](ci.md): reference a tag, never `@main`.

## Getting the manifest

Hunter needs `manifest.json`, which dbt writes into `target/`. That directory
is almost always in `.gitignore`, so it is a build output rather than something
sitting in the repository.

Three ways to get one, in the order worth trying.

### 1. Parse with no credential

```bash
cd your-dbt-project
dbt parse
```

Usually this needs no warehouse connection. dbt reads the project files and
works out what each model refers to.

It fails without a connection when a model cannot be understood without asking
the warehouse a question first. The common cases:

| Pattern | What it asks the warehouse |
|---|---|
| `dbt_utils.star(from=ref('x'))` | Which columns does `x` have? |
| `dbt_utils.get_column_values(...)` | What distinct values are in this column? |
| `dbt_utils.union_relations(...)` | What is the combined column set? |
| `adapter.get_columns_in_relation(...)` | The same question, asked directly |
| `run_query(...)` in a macro | Anything at all |

Well-written versions of these are wrapped so they are skipped during parsing.
Badly wrapped ones are not.

dbt also expects a valid-looking `profiles.yml` entry even when it never
connects, so a stub profile is enough.

### 2. Parse with a read-only credential

If the above fails, `dbt parse` with a read-only service account. Workload
Identity Federation rather than a stored key file.

### 3. Use the manifest your dbt job already produces

If dbt already runs somewhere, the manifest already exists. Point Hunter at it:

```bash
hunter score . --manifest path/to/manifest.json
```

| Where dbt runs | Where the manifest lands |
|---|---|
| dbt Cloud | The run artifacts endpoint, or the Discovery API |
| GitHub Actions | An uploaded workflow artifact |
| Dagster or Airflow | Usually a bucket alongside the run |
| Committed for state comparison | A dedicated branch or a `state/` directory |

This is the option that turns installing Hunter from a security review into a
configuration change, so it is worth five minutes to find out whether it
applies.

### Finding out which applies to you

Five checks against the repository, needing access to nothing else.

| Check | What it tells you |
|---|---|
| `.gitignore` for `target/` | Confirms the manifest is not committed. It almost always is ignored |
| `.github/workflows/*.yml` for `dbt` | Whether dbt runs in Actions, and whether the run uploads artifacts |
| `cloudbuild.yaml` or Cloud Build triggers | Whether dbt runs there, and whether it writes to a bucket |
| Any Dagster, Airflow or scheduler config | Whether a scheduler runs dbt, and where its working directory persists |
| A repository-wide search for `manifest.json` | Existing code that already moves the artifact somewhere |

If none of those turn anything up, either dbt Cloud holds it in run artifacts,
or dbt only runs on developer laptops and there is no artifact to fetch.

## Also useful: a catalogue

`dbt docs generate` writes `catalog.json` next to the manifest. It carries
column data types, which a manifest almost never does: one real repository has
types for 164 of 5,251 columns.

Hunter reads it automatically where it exists. Without it, two things are
weaker. Entity inference rests on naming rather than types and caps its
confidence lower. And the type comparison between the design and what was built
cannot run at all, so it reports that rather than reporting no drift.

Nothing breaks without it. Hunter says which of the two situations it is in.

## For development

```bash
git clone https://github.com/sav-sus/Hunter
cd Hunter
uv sync --all-extras

uv run pytest
uv run hunter score examples/tiny-shop
```

See [Contributing](contributing.md).
