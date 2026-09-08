# Contributing

## Getting set up

```bash
git clone https://github.com/sav-sus/Hunter
cd Hunter
uv sync --all-extras
```

Four gates, all of which CI runs:

```bash
uv run pytest                    # 515 tests
uv run ruff check .              # lint
uv run ruff format --check .     # formatting
uv run mypy                      # types, strict on checks, score and model
```

Plus two that are specific to Hunter:

```bash
uv run python scripts/check_no_client_content.py
uv run python -m tests.regenerate_golden && git diff --exit-code tests/golden/
```

## The rule that holds the design together

Every reader writes into one normalised model in `src/hunter/model/entities.py`,
and no check ever reads a raw source. A check that opens `manifest.json` is a
bug, however convenient.

The point is replaceability. Adding Snowflake, or a semantic layer other than
LookML, touches one file in `ingest/` and nothing else.

## Adding a rule

Declare it, then use it. Three steps.

**1. Declare it in the check module**, with everything about it in one place:

```python
KEY_UNIQUENESS_MISSING = rule(
    "testing.key_uniqueness_missing",
    dimension=Dimension.TESTING,
    severity=Severity.HIGH,
    points=2.0,
    title="Nothing tests that {key} is unique on {subject}",
    consequence=(
        "Nothing checks that {label} holds one row per {grain}. If duplicates "
        "appear, every total built from it is overstated and nobody is told. "
        "{consumers}."
    ),
    plain_heading="What is tested",
    requires=(REQ_MANIFEST,),
)
```

**2. Examine every candidate, and report the failures:**

```python
for model in context.project.sorted_models():
    if not model.is_scoreable:
        continue
    context.examine(KEY_UNIQUENESS_MISSING.id, model.name)  # every candidate
    if not has_unique_test(model):
        findings.add(
            context.finding(  # only the failures
                KEY_UNIQUENESS_MISSING.id,
                subject=model.name,
                file=model.path,
                evidence={"key": key, "grain": grain, "consumers": consumers},
            )
        )
```

Calling `examine` only when a rule fires makes the denominator equal the
numerator, and the area then scores 0 whenever anything fails. That bug shipped
once.

**3. Write both cases into the example project.** A passing case and a failing
case. See below.

### Rules to follow

**No numbers in check code.** Every threshold is a field on a configuration
model. A rule with a hardcoded number is a rule nobody can tune.

**The consequence line says what breaks.** Not what is missing, and never how
severe it is. "Three dashboards will show wrong figures if this changes", not
"high severity: test missing". A test asserts that no consequence line contains
the word "severity".

**Build findings through `context.finding`.** It applies rule overrides,
register silences, exposure weighting and the confidence floor. Constructing a
`Finding` directly bypasses all of it.

**Use `plural()` for counts in prose.** "1 columns" is not acceptable output.

**Scale a partial gap.** Pass `points_scale` where a rule reports once per table
but counts many things inside it.

**Mark a coverage rule as one.** If the rule reports what Hunter could not check
rather than what the repository got wrong, set `about_coverage=True`. Otherwise
it appears as a gap in the repository, which it is not.

## Run it against something real

This is the part that matters most, and it is what the test suite cannot do for
you.

Nine rules were wrong when first written, and every one was found by running
against a real repository rather than by testing against the example. `select *`
fired on 226 of 228 models. `is distinct from` was read as a FROM clause. A rule
tested only against a fixture is a rule tested against its own assumptions,
because the same person wrote both.

Point it at the largest repository you have access to and read the findings.
Then read them again asking "would I act on this".

## The example project

`examples/tiny-shop` is eight tables with one deliberate flaw per finding class.
It exercises 28 rules across all seven scored areas, including a silenced
finding, a low-confidence suggestion, a table built and switched off, an
off-plan build and a dropped generation override.

Adding a table or a flaw:

```bash
# Edit examples/tiny-shop/build.py, saying in a comment what the table is for
uv run python examples/tiny-shop/build.py     # rewrite the manifest
uv run python -m tests.regenerate_golden      # rewrite the pinned report
uv run python scripts/build_docs_pages.py     # rewrite the documented example
```

Then review all three diffs.

## The golden file

`tests/golden/tiny-shop.json` is the example's whole report, minus its
timestamp. Every change to the arithmetic changes it, and CI fails if it has
drifted.

That is the mechanism that stops a score moving without anybody deciding it
should. When you regenerate it, the diff is the review.

If the arithmetic changed in a way that moves numbers, bump
`SCORE_MODEL_VERSION` in `src/hunter/__init__.py`. That is what lets a client's
next run report the movement as caused by the upgrade rather than by their
repository.

## Generated documentation

Two pages are generated and must not be edited by hand:

| Page | From |
|---|---|
| `docs/reference/rules.md` | The rule registry |
| `docs/example/` | A real run against `examples/tiny-shop` |

```bash
uv run python scripts/build_docs_pages.py
```

CI regenerates and fails on a difference, so neither can go stale. A stale rules
reference is worse than none, because somebody will act on it.

## Client content

`scripts/check_no_client_content.py` fails on client-identifying strings in
tracked files, and CI runs it.

Hunter is developed by running it against real client repositories, so the rule
is enforced rather than remembered. Names in the example project are invented
and resemble no client's.

## Third-party parsers

`pydbml` and `lkml` are pinned exactly, not to a range. Both are
small-maintainer projects parsing formats that shift, and pinning means a break
surfaces at upgrade rather than in a client run.

Both are wrapped behind Hunter's own interface, so nothing outside
`ingest/dbml.py` and `ingest/lookml.py` knows they exist. When one breaks, the
fix is in one file.

MkDocs and its theme are pinned below their next major version. MkDocs 2.0 will
remove the plugin system and rewrite theming with no migration path, so moving
those pins is a piece of work rather than a bump.

## Style

Match the surrounding code. Beyond that:

**Say why, not what.** The code says what it does. A comment earns its place by
explaining a decision, a constraint, or something that was tried and did not
work. Several of the comments in the codebase record a rule that was wrong and
how it was found; those are the useful ones.

**Docstrings name the requirement.** `FR7.9` or `section 11.4`. It makes the
link from behaviour back to the reason it exists.

**Type everything in `checks/`, `score/` and `model/`.** They are strict under
mypy, because a wrong type there is a wrong number in somebody's report.

## Where things are

| Path | What it is |
|---|---|
| `src/hunter/run.py` | The pipeline. Start here |
| `src/hunter/checks/base.py` | Rules, context, the one way a finding is made |
| `src/hunter/model/entities.py` | The normalised model everything reads |
| `src/hunter/model/align.py` | The five-point chain |
| `src/hunter/score/engine.py` | The arithmetic |
| `src/hunter/config/house/ra-house-1.yml` | The standard |
| `.doc/` | Why it is built this way |
