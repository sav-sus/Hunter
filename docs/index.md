---
hide:
  - navigation
  - toc
---

<div class="hero" markdown>

# Know what state your analytics repository is in

Point Hunter at a repository holding dbt and LookML. It reads the code, the
design and the git history, then reports on them. It changes nothing: no
commits, no pull requests, no writes to your warehouse.

[See the dashboard](example/dashboard.md){ .md-button }
[Install it](install.md){ .md-button .md-button--secondary }

<div class="figures">
  <div><b>2s</b><span>on 280 models</span></div>
  <div><b>77</b><span>rules</span></div>
  <div><b>0</b><span>credentials needed</span></div>
  <div><b>8</b><span>areas scored</span></div>
</div>

</div>

## What you get

<div class="cards">
  <a href="example/dashboard/">
    <span class="tag">One screen</span>
    <b>A dashboard</b>
    <p>The score, what nobody has decided, where the points are going, and what
    to fix first. One self-contained HTML file.</p>
  </a>
  <a href="example/reconciliation/">
    <span class="tag">One row per table</span>
    <b>Designed against built</b>
    <p>Whether the business asked for it, whether it was designed, whether it
    was built. Readable without opening a file.</p>
  </a>
  <a href="example/debt/">
    <span class="tag">Ranked</span>
    <b>What needs doing</b>
    <p>Ordered by how many points closing it recovers, each item saying what
    breaks if it is left.</p>
  </a>
  <a href="ci/">
    <span class="tag">On every change</span>
    <b>A pull request comment</b>
    <p>What the change touches, what it breaks downstream, and the debt it
    adds. Advisory by default.</p>
  </a>
</div>

## The four questions it answers

Each one currently takes reading the whole repository by hand.

| Question | How Hunter answers it |
|---|---|
| **What is in here, and what is just a working step?** | Classifies every table as temporary or permanent, and records which of five signals decided |
| **Who built each part?** | Attributes every table to a commit, author and pull request. Routes findings by owner, reports by team, never ranks people |
| **Is the modelling right?** | Works out what a table behaves like from its columns, then compares that against what its name claims |
| **Do the layers agree?** | Maps every report field to the column it reads, so a renamed column shows up in the pull request, not in a client's dashboard |

## What makes it different

<div class="cards">
  <div>
    <b>Every finding says what breaks</b>
    <p>Not "high severity: relationships test missing". Instead: "Where these
    references point at rows that do not exist, joined figures come out low and
    the rows simply vanish."</p>
  </div>
  <div>
    <b>It says what it did not check</b>
    <p>An area Hunter could not measure is excluded and named, with its weight
    shared across the rest. Never scored as zero, never quietly out of less
    than 100.</p>
  </div>
  <div>
    <b>It has no opinions of its own</b>
    <p>Layer names, conventions and weights are all declared. It ships with the
    Rittman Analytics standard, and every difference from it is published with
    the reason given.</p>
  </div>
  <div>
    <b>Systemic gaps sit above the number</b>
    <p>"No table names an owner, 63 of 63" is one decision nobody took, not 63
    defects. A weighted mean buries that, so it is listed separately.</p>
  </div>
</div>

<div class="key" markdown>
**Nothing is written by a language model.** Every sentence in a report is a
template filled from a finding's own evidence, so each one has a deterministic
check behind it.
</div>

## What it reads

A dbt `manifest.json` is the only requirement. Everything else adds an area to
the score rather than being a prerequisite.

| Source | What it adds | Credential |
|---|---|---|
| `manifest.json` | Tables, columns, tests, lineage | No |
| DBML design files | Does what was built match the design | No |
| A conceptual Mermaid diagram | Does the design match what the business asked for | No |
| LookML | Will a renamed column break a report | No |
| Committed Droughty output | Are generated tests and descriptions still applied | No |
| Git history | Who wrote what, and what changed in a window | No |
| `catalog.json` | Column types, which sharpen two checks | No |
| BigQuery metadata | What is deployed, and what it costs | Yes. Not built yet |

## Where to go next

<div class="cards">
  <a href="install/">
    <span class="tag">5 minutes</span>
    <b>Install and run it</b>
    <p>Then the first run, and what to do with the score you get.</p>
  </a>
  <a href="concepts/">
    <span class="tag">Background</span>
    <b>The ideas behind it</b>
    <p>Seven of them. Everything else in Hunter follows from these.</p>
  </a>
  <a href="configuration/">
    <span class="tag">Setup</span>
    <b>Configure it</b>
    <p>Two files. What correct looks like, and what your team has decided.</p>
  </a>
  <a href="cli/">
    <span class="tag">Reference</span>
    <b>Commands and rules</b>
    <p>Ten commands, 77 rules, and what each one costs.</p>
  </a>
</div>

---

Proprietary. Not open source. See
[LICENSE](https://github.com/sav-sus/Hunter/blob/main/LICENSE).
Rittman Hunter is a Rittman Analytics product.
