# First run

<p class="lede">Five commands, about ten minutes. Nothing is written to your
warehouse, and nothing in your repository changes except the two files
<code>hunter init</code> creates.</p>

<ol class="steps" markdown>

<li markdown>
<b>Set it up</b>

```bash
cd your-analytics-repo
hunter init
```

Works out where everything is and writes `.hunter/hunter.yml` and
`.hunter/register.yml`. Read the notes it prints: each one is a line to correct
if the guess was wrong.

If a manifest is already there, it also fills the register with the tables it
would flag, each with a blank reason.

??? note "Why it pre-fills the register"

    Being handed an empty file and asked to document your exceptions does not
    work. Being handed the list and asked for a reason against each does.

    ```
    The register lists 63 tables with no owner and 8 built without a design.
    Fill in the blanks.
    ```
</li>

<li markdown>
<b>Score it</b>

```bash
hunter score
```

```
  89.6 / 100     Well maintained. Safe to build on

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
```

Read it in this order:

| Read | Because |
|---|---|
| **The systemic gaps** | A rule that failed on everything is one decision nobody took, not many defects. These are the conversations |
| **"not measured"** | That area was excluded and its weight shared out. Not a zero, not a pass |
| **The number** | Last. On its own it invites an argument |
</li>

<li markdown>
<b>Record where you started</b>

```bash
hunter baseline
git add .hunter/baseline.json && git commit -m "Record the starting score"
```

An existing repository starts where it starts and only has to improve. Commit
it, and later runs measure movement instead of arguing about an absolute number.
</li>

<li markdown>
<b>Open the dashboard</b>

```bash
hunter dashboard && open out/dashboard.html
```

The whole report in one screen. [See one](example/dashboard.md).

For the detail pages behind it, with search and navigation:

```bash
hunter docs build && open out/site/_built/dashboard.html
```
</li>

<li markdown>
<b>Look at one table</b>

```bash
hunter explain wh_shop__customer_dim
```

What it is, what one row means, who owns it, how it behaves against what its
name claims, its columns and tests, what depends on it, and every finding
against it.
</li>

</ol>

## Then what

| Do this | Why |
|---|---|
| **Fill in owners first** | The most common systemic gap, and the one that makes every other finding routable |
| **Leave the mode on advisory** | A tool that fails builds in its first week gets switched off in its second. Advisory is the default |
| **Add it to CI when ready** | See [In CI](ci.md) |

## If something goes wrong

| Message | What to do |
|---|---|
| `Could not read the dbt manifest` | Run `dbt parse`, or pass `--manifest`. See [Install](install.md) |
| `The ruleset is not valid` | The message names the field. Unknown keys are errors on purpose, so a typo cannot silently switch off a rule |
| `The register file is not valid` | The message names the entry. Approvals need a reason and a named approver; silences need an end date |
| `No model named 'x'` | Hunter suggests near matches. Use the name as it appears in the manifest |
| Most areas say "not measured" | Read the "what was not checked" page. Usually the design files or the LookML are somewhere Hunter did not look |

Full command reference: [Commands](cli.md).
