# Installation

<p class="lede">One command, then find your dbt manifest. No warehouse
credential.</p>

```bash
uv tool install "rittman-hunter[site] @ git+https://github.com/sav-sus/Hunter@v0.1.0"
hunter version
```

| You need | Notes |
|---|---|
| Python 3.11 or newer | Developed and tested on 3.12 |
| A dbt `manifest.json` | Anywhere. You tell Hunter where |
| Read access to the repository | Nothing else |

The `[site]` extra pulls in MkDocs, needed only for `hunter docs build`. Leave
it off for the score, the report and the dashboard.

<div class="key" markdown>
**Always pin a version. Never install from a branch.** A repository's score
must not move because somebody pushed a commit. Same for the
[GitHub Action](ci.md): reference a tag, never `@main`.
</div>

??? note "With pipx instead of uv"

    ```bash
    pipx install "rittman-hunter[site] @ git+https://github.com/sav-sus/Hunter@v0.1.0"
    ```

??? note "What `hunter version` prints, and why three numbers"

    ```json
    { "hunter": "0.1.0", "house_ruleset": "1", "score_model": "1" }
    ```

    All three are stamped on every report. The score model version is what lets
    a later run tell real change from movement caused by upgrading Hunter.

## Getting the manifest

dbt writes `manifest.json` into `target/`, which is almost always in
`.gitignore`. So it is a build output, not a file sitting in the repository.

Three ways to get one, in the order worth trying.

### 1. Parse with no credential

```bash
cd your-dbt-project
dbt parse
```

Usually enough. dbt reads the project files and works out what each model
refers to. It needs a valid-looking `profiles.yml` entry even when it never
connects, so a stub profile does.

### 2. Parse with a read-only credential

If step 1 fails, use a read-only service account. Workload Identity Federation
rather than a stored key file.

### 3. Use the manifest your dbt job already produces

If dbt runs anywhere already, the manifest already exists.

```bash
hunter score . --manifest path/to/manifest.json
```

This is the option that turns installing Hunter from a security review into a
configuration change, so it is worth five minutes to check.

??? note "Why `dbt parse` sometimes needs a connection"

    It fails when a model cannot be understood without asking the warehouse a
    question first.

    | Pattern | What it asks the warehouse |
    |---|---|
    | `dbt_utils.star(from=ref('x'))` | Which columns does `x` have? |
    | `dbt_utils.get_column_values(...)` | What distinct values are in this column? |
    | `dbt_utils.union_relations(...)` | What is the combined column set? |
    | `adapter.get_columns_in_relation(...)` | The same, asked directly |
    | `run_query(...)` in a macro | Anything at all |

    Well-written versions of these are wrapped so parsing skips them. Badly
    wrapped ones are not.

??? note "Where to look for an existing manifest"

    | Where dbt runs | Where the manifest lands |
    |---|---|
    | dbt Cloud | Run artifacts endpoint, or the Discovery API |
    | GitHub Actions | An uploaded workflow artifact |
    | Dagster or Airflow | Usually a bucket alongside the run |
    | Committed for state comparison | A dedicated branch or `state/` |

    Five checks that need access to nothing but the repository:

    | Check | What it tells you |
    |---|---|
    | `.gitignore` for `target/` | Confirms the manifest is not committed |
    | `.github/workflows/*.yml` for `dbt` | Whether dbt runs in Actions, and whether it uploads artifacts |
    | `cloudbuild.yaml` or Cloud Build triggers | Whether dbt runs there, and whether it writes to a bucket |
    | Dagster, Airflow or scheduler config | Whether a scheduler runs dbt, and where its working directory persists |
    | Search the repository for `manifest.json` | Code that already moves the artifact somewhere |

    If none turn anything up, either dbt Cloud holds it in run artifacts, or dbt
    only runs on laptops and there is no artifact to fetch.

## Optional: a catalogue

`dbt docs generate` writes `catalog.json` beside the manifest, carrying column
data types. A manifest almost never has them: one real repository has types for
164 of 5,251 columns.

Hunter reads it automatically where it exists. Without it, two checks are
weaker, and Hunter says so rather than reporting a clean result.

| Without a catalogue | What happens |
|---|---|
| Entity inference | Rests on naming, and caps its confidence at 0.65 instead of 0.85 |
| Type drift between design and build | Cannot run. Reported as not checked |

## For development

```bash
git clone https://github.com/sav-sus/Hunter
cd Hunter
uv sync --all-extras
uv run pytest
uv run hunter score examples/tiny-shop
```

See [Contributing](contributing.md).
