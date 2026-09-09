# Quick start, step by step

<p class="lede">From nothing to a published dashboard. Twelve steps. Each one
says what to do, what you should see, and what to do if you do not see it.
Nothing here changes your warehouse.</p>

You need three things before you start.

| You need | How to check |
|---|---|
| Python 3.11 or newer | Type `python3 --version` in a terminal. You should see `3.11` or higher. Hunter is tested on `3.12` |
| A repository that holds a dbt project | Look for a file called `dbt_project.yml` in it |
| Permission to change settings on that repository in GitHub | Open the repository on GitHub. You should see a **Settings** tab |

If any of the three is missing, ask whoever looks after the repository. Do
not carry on without them.

## 1. Install Hunter

Open a terminal and type:

```bash
uv tool install "rittman-hunter[site] @ git+https://github.com/sav-sus/Hunter@v0.1.0"
```

Then check it worked:

```bash
hunter version
```

**You should see** three version numbers, something like:

```json
{ "hunter": "0.1.0", "house_ruleset": "1", "score_model": "1" }
```

**If you see** `command not found: uv`, install uv first from
<https://docs.astral.sh/uv/>, then come back to this step.
**If you see** `command not found: hunter`, close the terminal, open a new one
and try `hunter version` again.

## 2. Go to your repository

```bash
cd path/to/your-analytics-repo
ls
```

**You should see** the top of the repository: the folder that holds
`dbt_project.yml`, and usually a `.github` folder.

**If you see** `dbt_project.yml` itself, you are one folder too deep. Type
`cd ..` and look again. Hunter is set up from the top of the repository, not
from inside the dbt project.

## 3. Make sure dbt has produced a manifest

The manifest is a file dbt writes that lists every model and what it reads.
Hunter needs it.

```bash
cd path/to/the-dbt-project      # the folder with dbt_project.yml
dbt parse
cd -                            # back to the top of the repository
```

**You should see** dbt finish without an error, and a file at
`target/manifest.json` inside the dbt project.

**If dbt asks for a connection**, see [Getting the manifest](install.md#getting-the-manifest).
Usually your dbt job already produces one and you can point Hunter at it.

## 4. Let Hunter set itself up

From the top of the repository:

```bash
hunter init
```

**You should see** any notes about what Hunter could not find, then three
`Wrote` lines, then what to do next:

```
Wrote .hunter/hunter.yml
Wrote .hunter/register.yml
Wrote .github/workflows/hunter.yml

Next: run `hunter score` and then `hunter baseline` to record a start.
```

| File | What it is for |
|---|---|
| `.hunter/hunter.yml` | What correct looks like. Rarely edited |
| `.hunter/register.yml` | What your team has decided about tables. Edited often |
| `.github/workflows/hunter.yml` | Runs Hunter on every pull request and publishes the dashboard |

If a manifest was found, the register is pre-filled with the tables Hunter
would flag, each with a blank next to it for an owner.

**If it says** it could not find something, read the line. It names the file
and the setting to correct in `.hunter/hunter.yml`. Everything else still
works.

## 5. Score it

```bash
hunter score
```

**You should see** a number out of 100, a grade, and one line per area:

```
  89.6 / 100     Well maintained. Safe to build on

   90.4  A  What is checked automatically            38 findings
   87.3  A  Does what was built match the design    190 findings
   ...
  Missing everywhere it was checked:
    63 of 63  Who owns what
```

Read it in this order.

| Read first | Because |
|---|---|
| **Missing everywhere it was checked** | A rule that failed on every table is one decision nobody took, not many defects. Usually it is "who owns what" |
| **not measured** | That area had nothing to read, so it was left out. Not a zero |
| **The number** | Last. On its own it invites an argument |

**If you see** `Could not read the dbt manifest`, go back to step 3, or tell
Hunter where the manifest is:

```bash
hunter score --manifest path/to/manifest.json
```

## 6. Look at the dashboard on your own machine

```bash
hunter dashboard
open out/dashboard.html          # on Windows: start out\dashboard.html
```

**You should see** one page in your browser: the score, a checklist, the
roadmap, the model diagrams and a list of every table. This is the page a
stakeholder will get a link to in step 11. [Here is what it looks like](example/dashboard.md).

## 7. Record where you started

```bash
hunter baseline
```

**You should see** `.hunter/baseline.json` written. This is the starting score.
From now on Hunter reports movement against it, so an old repository is judged
on whether it is improving, not on where it started.

## 8. Switch on GitHub Pages

This is the one thing done by clicking, and it is done once.

1. Open the repository on GitHub.
2. Click the **Settings** tab, along the top.
3. In the left-hand list, click **Pages**.
4. Under **Build and deployment**, find **Source**.
5. Change it from **Deploy from a branch** to **GitHub Actions**.

There is no save button. The change applies as soon as you pick it.

<div class="key" markdown>
**Read this before you click.** Unless your organisation is on GitHub
Enterprise Cloud, a Pages site is public, even from a private repository. The
dashboard shows table names, column names, owners and findings. It shows no
data. If a public page is not acceptable, skip this step and see
[Publish the dashboard](publish.md) for the alternative.
</div>

## 9. Add the two dbt secrets

Hunter reads the file dbt writes when it parses the project, and that file is
never in a checkout. So the workflow runs `dbt parse` itself before anything
else, and `dbt parse` needs a dbt profile. You give it one as a secret.

1. In the repository on GitHub, click **Settings**.
2. In the left-hand list, click **Secrets and variables**, then **Actions**.
3. Click **New repository secret**. Name: `DBT_PROFILES_YML`. Value: the whole
   contents of a `profiles.yml` for CI. The top of the generated
   `.github/workflows/hunter.yml` shows one to copy, with your profile name
   already filled in.
4. For BigQuery with a service account, add a second secret. Name:
   `DBT_KEYFILE_JSON`. Value: the service account key file, as JSON.

**If your dbt job already produces a manifest** somewhere, you can skip the
secrets: the header of the workflow file says how to fetch that file instead.

**If you skip this step**, the first job on the pull request stops with a
message that names the missing secret. Nothing else runs until it is added.

## 10. Commit the files and open a pull request

```bash
git checkout -b add-hunter
git add .hunter .github/workflows/hunter.yml
git commit -m "Add Hunter"
git push -u origin add-hunter
```

Then open the repository on GitHub. **You should see** a yellow banner offering
to open a pull request for `add-hunter`. Click **Compare & pull request**, then
**Create pull request**.

Within a minute or two, **you should see** at the bottom of the pull request:

| What appears | What it is |
|---|---|
| A check called **Build the dbt manifest** | `dbt parse`, using the profile from step 9. The other four wait for it |
| A check called **Score** | The whole repository scored. It never fails the build |
| **LookML sync**, **Droughty sync**, **Modelling sync** | One line each. Does one layer still match another? |
| One comment from the GitHub Actions bot | What this change touches, what it reaches, and what it adds to the debt |

Nothing fails on this first run if step 9 was done. All four Hunter checks start in report-only mode.

**If no checks appear**, click the **Actions** tab. If the list is empty,
Actions is switched off for the repository: Settings, Actions, General, allow
all actions. Then push a small change to the branch.

## 11. Merge, then open the dashboard

Click **Merge pull request**, then **Confirm merge**.

Click the **Actions** tab. **You should see** a run called **Hunter** on
`main`. Wait for every job to show a green tick, including **Publish the
dashboard**. It takes two to four minutes.

Then open:

```
https://<your-organisation>.github.io/<your-repository>/
```

**You should see** the same page you saw in step 6, now on a link anyone can
open. Send the link to whoever asked for it. It updates itself every time a
pull request is merged, and every Monday morning.

**If the Publish job failed**, go back to step 8. The Pages source is still set
to a branch.

## 12. Fill in the register

This is the step that turns findings into something people can act on, and it
is the one you will come back to.

Open `.hunter/register.yml`. It has a list of tables with a blank owner. Fill
each one in with a team name:

```yaml
models:
  wh_commerce__order_fact:
    owner: commerce
    grain: one row per order
```

Then decide the status of the tables you know about.

| If the table is | Write |
|---|---|
| A finished table someone has checked and stands behind | `persistence: verified`, with `verified_by: <name>` and a `reason` |
| A working step, or a table only ever meant to run once | `persistence: temporary`, with a `reason` and a `review_by` date |
| On its way out | `status: deprecated`, with a `review_by` date |
| Not built yet, but agreed | `status: planned` |

```yaml
  wh_commerce__order_fact:
    owner: commerce
    grain: one row per order
    persistence: verified
    verified_by: sav
    reason: signed off at the design review as the order fact of record

  int_shop__orders:
    persistence: temporary
    reason: a working step feeding the order fact, not for reporting from
    review_by: 2027-01-31

  wh_commerce__legacy_fact:
    owner: commerce
    status: deprecated
    review_by: 2027-03-31
```

Commit it on a branch, open a pull request, merge. **You should see** the
"who owns what" gap shrink on the dashboard, the roadmap move the tables into
their lanes, and each table carry its word: temporary, verified or permanent.

The full list of what the file accepts is on
[Mark a table temporary, verified or permanent](register.md).

## After that

Nothing to run. Every pull request is checked. Every merge republishes the
dashboard. Every Monday the same run catches drift that arrived from outside a
pull request.

| Do this | When |
|---|---|
| Read the Monday run | Weekly. Five minutes |
| Fill in owners as tables are touched | Whenever a pull request touches a table with no owner |
| Turn one sync check up to `fail-on: high` | Once the team has been reading the comments for a few weeks. See [Check the layers agree](sync-checks.md) |

## If something goes wrong

| Message | What to do |
|---|---|
| `Could not read the dbt manifest` | Step 3, or pass `--manifest`. See [Getting the manifest](install.md#getting-the-manifest) |
| `The ruleset is not valid` | The message names the field in `.hunter/hunter.yml`. Unknown keys are errors on purpose, so a typo cannot silently switch off a rule |
| `The register file is not valid` | The message names the entry. A `verified` table needs `verified_by`; a `temporary` one needs a reason; a silence needs an end date |
| `No model named 'x'` | Hunter suggests near matches. Use the name as it appears in the manifest |
| Most areas say "not measured" | Read the "what was not checked" page on the dashboard. Usually the design files or the LookML are somewhere Hunter did not look |
| The Publish job fails | Step 8. The Pages source is still set to a branch |
| `Missing secret DBT_PROFILES_YML` | Step 9. The workflow cannot build the manifest without a dbt profile |
| `unable to resolve action` | The Hunter version in the workflow has no release tag. In the Hunter repository, run `python scripts/check_release.py --release` on `main` |

Full command reference: [Commands](cli.md).
