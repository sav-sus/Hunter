---
hide:
  - navigation
  - toc
---

<div class="hero" markdown>

# Overview

Rittman Hunter is a health dashboard for an analytics warehouse. It reads the
dbt models, the LookML, the data model design and the git history in a
repository, checks them against each other, and publishes one page a business
stakeholder can read without a GitHub account. It runs on every pull request and
changes nothing.

[See the dashboard](example/dashboard.md){ .md-button }
[Install it](install.md){ .md-button .md-button--secondary }

<div class="figures">
  <div><b>0</b><span>manual steps</span></div>
  <div><b>3</b><span>sync checks on every pull request</span></div>
  <div><b>77</b><span>rules</span></div>
  <div><b>0</b><span>credentials needed</span></div>
</div>

</div>

## The problem

A warehouse is built in layers: staging models feed integration models, which
feed warehouse tables, which feed Looker. Each layer is edited by different
people at different times, and nothing checks that they still agree.

| What goes wrong | What it costs |
|---|---|
| A column is renamed in dbt and a Looker field still points at the old name | The client finds the broken dashboard, not the build |
| Droughty generates tests and descriptions that never reach dbt | Everyone believes a check is running that is not |
| A working step is used as if it were a finished table | It cannot be changed without breaking something nobody knew about |
| A table is built with no design and no owner | Nobody can be asked what one row means, or asked to fix it |
| A table meant to run once is still running a year later | Cost and confusion, with nobody sure whether it is safe to remove |
| Only the people with repository access can see any of this | The stakeholder who pays for the warehouse has no view of its state |

Finding any of this today means reading the whole repository by hand.

## The solution

Hunter reads what is already in the repository and reports on it. It does not
need a warehouse connection, and it never writes anything back.

| It reads | To answer |
|---|---|
| The dbt manifest | What tables exist, what feeds what, what is tested |
| The design files (DBML and Mermaid) | Whether what was built is what was designed and asked for |
| The LookML | Whether the reporting layer still matches the tables |
| The committed Droughty output | Whether the generated tests and descriptions were applied and are current |
| The register, a small YAML file | Who owns each table, and whether it is temporary, verified or permanent |
| Git history | Who built what, and what changed |

Every check is a plain statement that either holds or does not, with the tables
that let it down named. Nothing on the page is written by a language model.

## How it works

<ol class="steps" markdown>
<li markdown><b>Someone opens a pull request</b>
Any change to the repository. There is no path filter and nothing to run by hand.</li>
<li markdown><b>GitHub Actions runs Hunter</b>
Five jobs: the score, and the LookML, Droughty and modelling sync checks, each as its own line on the pull request. Hunter finds the layers itself, so a new directory of models is picked up without configuration.</li>
<li markdown><b>The pull request gets one comment</b>
What the change touches, what it reaches downstream, and what it adds to the debt. Edited in place on each push.</li>
<li markdown><b>On merge, the dashboard is rebuilt and published</b>
To GitHub Pages, in the same repository. A stakeholder opens a link.</li>
</ol>

The full walk-through, in order, is on [From a pull request to the dashboard](how-it-works.md).

## What Hunter produces

| Output | What it is | Who it is for |
|---|---|---|
| [The dashboard](example/dashboard.md) | Score, checklist, roadmap, modelling alignment, diagrams, data flow and table readiness, on one page | A stakeholder with no repository access |
| [The roadmap](example/roadmap.md) | Every table in one lane: planned, being built, live, temporary by design, being phased out, retired | Whoever plans the work |
| [Designed against built](example/reconciliation.md) | One row per table: asked for, designed, built | The product owner |
| [What needs doing](example/debt.md) | Every open finding, ranked by what fixing it recovers | The engineering team |
| [Three sync checks](sync-checks.md) | LookML, Droughty and modelling drift, each a separate CI check that can fail a build | The pull request reviewer |
| A pull request comment | What this change touches and what it breaks downstream | The author of the change |

## Status: temporary, verified or permanent

Every built table carries one of three words, recorded in [the register](register.md).

| Status | Meaning | How it gets there |
|---|---|---|
| Temporary | A working step, or a table only ever meant to run once. Carries a review date | Declared in the register, or inferred from the layer |
| Verified | Meant to stay, and a named person has confirmed it | Declared in the register, with the person's name |
| Permanent | Meant to stay | Inferred from the layer and materialisation |

## Quick links

<div class="cards">
  <a href="install/">
    <span class="tag">5 minutes</span>
    <b>Installation</b>
    <p>One command, then find your dbt manifest.</p>
  </a>
  <a href="quickstart/">
    <span class="tag">10 minutes</span>
    <b>Quick start</b>
    <p>Set up, score, publish. Then what to do with what you see.</p>
  </a>
  <a href="how-it-works/">
    <span class="tag">In order</span>
    <b>From a pull request to the dashboard</b>
    <p>Every step, and what each one produces.</p>
  </a>
  <a href="publish/">
    <span class="tag">GitHub Pages</span>
    <b>Publish the dashboard</b>
    <p>One setting in the repository. The workflow does the rest.</p>
  </a>
  <a href="cli/">
    <span class="tag">Reference</span>
    <b>Commands</b>
    <p>Thirteen commands and 77 rules.</p>
  </a>
  <a href="https://github.com/sav-sus/Hunter">
    <span class="tag">Source</span>
    <b>GitHub</b>
    <p>sav-sus/Hunter. Proprietary, Rittman Analytics.</p>
  </a>
</div>

---

Proprietary. Not open source. See
[LICENSE](https://github.com/sav-sus/Hunter/blob/main/LICENSE).
Rittman Hunter is a Rittman Analytics product.
