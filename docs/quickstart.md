# Getting started

Five commands, about ten minutes. Nothing is written to your warehouse and
nothing in your repository is changed except the two configuration files
`hunter init` creates.

## 1. Set it up

```bash
cd your-analytics-repo
hunter init
```

This looks at the repository, works out where things are, and writes two
files. The ruleset it writes extends the Rittman Analytics house standard,
`ra-house@1`.

```
note: No target/manifest.json was found. Run `dbt parse` in the project, or
      pass --manifest with the path to one your dbt job already produces.
Wrote .hunter/hunter.yml
Wrote .hunter/register.yml
```

Read the notes. They say what Hunter could not find, and each one is a line to
correct in `.hunter/hunter.yml` if the guess was wrong.

If a manifest is already present, `hunter init` also scores the repository and
fills the register with the tables it would flag, each with a blank reason:

```
  The register lists 63 tables with no owner and 8 built without a design.
  Fill in the blanks.
```

That is the intended way to use it. Being handed an empty file and asked to
document your exceptions does not work. Being handed the list and asked for a
reason against each does.

## 2. Score it

```bash
hunter score
```

```
  89.6 / 100
  Well maintained. Safe to build on

   90.4  A  What is checked automatically            38 findings
   87.3  A  Does what was built match the design    190 findings
   92.6  A  How the tables fit together              53 findings
   77.2  B  What is written down                    135 findings
   86.7  A  Do the reports still match the data     183 findings
   98.3  A  Are the house rules followed              6 findings
   98.3  A  Are the tables the shape they claim       7 findings
      -  -  What it costs to run                  not measured

  Missing everywhere it was checked:
    63 of 63  Who owns what
    54 of 54  Do the reports still match the data

  648 open, 10 suggestions, 0 silenced

  Report written to out/report.json
```

Three things to read, in this order.

**The systemic gaps.** A rule that failed on everything it examined is one
decision nobody has taken, not many defects. Those are the conversations.

**"not measured".** That area was excluded and its weight shared across the
rest. It is not a zero and it is not a pass.

**The number.** Last, because on its own it invites an argument. Everything
behind it is in `out/report.json` and on the site.

## 3. Record where you started

```bash
hunter baseline
git add .hunter/baseline.json && git commit -m "Record the starting score"
```

An existing repository starts where it starts and only has to improve. Without
this, every later run reports an absolute number and the first conversation is
about whether the number is fair.

Commit it. Later runs then measure movement, and a drop caused by upgrading
Hunter is reported apart from a real one.

## 4. Read the site

```bash
hunter docs build
open out/site/_built/index.html
```

Twelve pages. Start with these three.

| Page | What it answers |
|---|---|
| Overview | Is this in good shape, what is going well, what needs a decision |
| Designed against built | One table: what was asked for, what was designed, what exists |
| What was not checked | What the score is not based on |

The overview page is written for someone who has never opened a SQL file. That
is deliberate: the plain language sits above the detail on the same page rather
than in a separate mode nobody finds.

## 5. Look at one table

```bash
hunter explain wh_shop__customer_dim
```

Everything Hunter knows about it: what it is, what one row means, who owns it,
what it is named as against how it behaves, its columns and their tests, what
depends on it, and every finding against it.

## Then what

**Fill in the register.** Owners first. It is the single most common systemic
gap, and it is the one that makes every other finding routable.

**Leave the mode on advisory.** A tool that fails builds in its first week gets
switched off in its second. Advisory is the default and it never fails
anything.

**Add it to CI when you are ready.** See [In CI](ci.md).

## Other commands worth knowing

```bash
# What was designed against what exists, on its own
hunter align

# What changed in the last two weeks, and what it cost
hunter showcase --days 14

# Build the pull request comment for the current branch
hunter check --pr 1184

# Print one diagram
hunter diagram --level conceptual

# Every rule Hunter can report
hunter rules
```

Full reference: [Commands](cli.md).

## If something goes wrong

| Message | What to do |
|---|---|
| `Could not read the dbt manifest` | Run `dbt parse`, or pass `--manifest` with a path. See [Installing](install.md) |
| `The ruleset is not valid` | The message names the field. Unknown keys are errors on purpose, so a typo cannot silently switch off a rule |
| `The register file is not valid` | The message names the entry. Approvals need a reason and a named approver; silences need an end date |
| `No model named 'x'` | Hunter suggests near matches. Use the name as it appears in the manifest |
| Most areas say "not measured" | Read the "what was not checked" page. Usually the design files or the reporting layer are somewhere Hunter did not look |
