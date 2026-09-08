# The dashboard

This is the front page of a Hunter report: the whole of [`examples/tiny-shop`](https://github.com/sav-sus/Hunter/tree/main/examples/tiny-shop) in one screen. It is generated output, not a mock-up, and it is rebuilt whenever the tool changes.

[Open the dashboard](dashboard.html){ .md-button .md-button--primary }

## What is on it

| Band | What it shows |
|---|---|
| The number | How healthy is this repository |
| Checklist | Statements that should hold, grouped: design to build, warehouse to Looker, Droughty, documentation, tests. Each says how many hold and names what does not |
| Modelling alignment | The same entities at the conceptual, logical and physical levels, side by side, with the breaks marked |
| Model diagrams | The conceptual, logical and physical models drawn with Mermaid, with tabs and zoom |
| Every table | One row per table, searchable: what is in the design, the repository, the warehouse and Looker |
| What everything else is built on | Which tables are load-bearing and unchecked |
| Do these first | What to fix, ranked by what closing it recovers |
| What this is not based on | What Hunter could not read |

## How it is built

One HTML file. The stylesheet, every chart and the logo are inlined, so it needs nothing installed and nothing beside it: it opens from a build artifact, a shared drive or an email attachment.

The one thing fetched from anywhere is the diagram library, at a pinned version. Where it does not arrive, the diagram source is shown as text with a note saying why, and nothing else on the page depends on it.

Two scripts run on the page. One filters the table list as you type; every row is already in the HTML, so with scripting off the list still reads in full. The other draws the model diagrams with Mermaid, which is the one thing the page fetches (pinned by version). Without a connection the diagram source is shown as text and the rest of the page is unaffected.

Every chart is SVG generated in Python rather than drawn by a charting library. That keeps the file self-contained, and it keeps the output byte-identical between runs, which is what lets the whole site be compared against a committed file in review.

```bash
hunter dashboard                 # one self-contained file
hunter docs build                # the dashboard plus the detail pages
```

---

_Rittman Hunter is a Rittman Analytics product._
