# The dashboard

This is the front page of a Hunter report: the whole of [`examples/tiny-shop`](https://github.com/sav-sus/Hunter/tree/main/examples/tiny-shop) in one screen. It is generated output, not a mock-up, and it is rebuilt whenever the tool changes.

[Open the dashboard](../dashboard.html){ .md-button .md-button--primary }

## What is on it

| Band | The question it answers |
|---|---|
| The number | How healthy is this repository |
| Needs a decision | What has nobody decided, as opposed to not fixed |
| Where the ground is being lost | Which area is costing the most points |
| How much of the plan is real | How much of the business model exists |
| Every entity | Where each table actually stands, in one of eleven states |
| Every rule at once | Is this a few bad tables or a habit |
| What everything else is built on | Which tables are load-bearing and unchecked |
| Do these first | What to fix, ranked by what closing it recovers |
| What this is not based on | What Hunter could not read |

## How it is built

One HTML file. The stylesheet, every chart and the logo are inlined, so it opens with no network and nothing beside it: from a build artifact, a shared drive or an email attachment.

Every chart is SVG generated in Python rather than drawn by a charting library. That keeps the file self-contained, and it keeps the output byte-identical between runs, which is what lets the whole site be compared against a committed file in review.

```bash
hunter dashboard                 # one self-contained file
hunter docs build                # the dashboard plus the detail pages
```

---

_Rittman Hunter is a Rittman Analytics product._
