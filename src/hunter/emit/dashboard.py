"""The report front page, as a self-contained dashboard.

One HTML file with the stylesheet, the charts and the logo inlined. It opens
from a build artifact, a shared drive or an email attachment and looks the same
in all three.

Two scripts run on the page, and the page reads in full without either:

* A filter over the table list. Every row is already in the HTML.
* The model diagrams. These need the Mermaid library, which is the one thing
  fetched from anywhere (pinned by version). If it does not arrive, the
  diagram source is shown as text and a note says why. Nothing else on the
  page depends on it.

The page is built to be read in this order:

    the number        how healthy is this repository
    the checklist     which statements about the repository hold, by area
    the alignment     the same entities at every model level, side by side
    the diagrams      the conceptual, logical and physical models, drawn
    the table list    what have we got, and what stands behind each one
    the load-bearing  which tables everything else depends on, and are they checked
    the queue         what should be done first

Everything drawn here traces to a rule and a finding. There is no panel whose
number is computed only for the picture, because a figure nobody can click
through to is a figure nobody should trust.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from hunter import brand
from hunter.emit import charts
from hunter.emit.charts import LaneCell, LaneRow, esc
from hunter.emit.plain import DIMENSION_HEADINGS, severity_label, top_fixes
from hunter.enums import Presence, Severity
from hunter.model.align import AlignmentRow
from hunter.run import RunResult

STYLE = f"""
*, *::before, *::after {{ box-sizing: border-box; }}
:root {{
  --ink: {brand.INK};
  --primary: {brand.PRIMARY};
  --accent: {brand.ACCENT};
  --sky: {brand.SKY};
  --peach: {brand.PEACH};
  --border: {brand.BORDER};
  --muted: {brand.MUTED};
  --muted-ink: {brand.MUTED_INK};
  --radius: 14px;
}}
html {{ -webkit-text-size-adjust: 100%; }}
body {{
  margin: 0;
  font-family: {brand.FONT_STACK};
  color: var(--ink);
  background: #f4f5f9;
  font-size: 15px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}}
.wrap {{ max-width: 1240px; margin: 0 auto; padding: 0 24px; }}

/* ---- top bar ---- */
.topbar {{
  background: #fff; border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 20;
}}
.topbar .wrap {{ display: flex; align-items: center; gap: 20px; height: 68px; }}
.topbar img {{ height: 26px; width: auto; display: block; }}
.brandmark {{ display: flex; align-items: center; gap: 14px; }}
.brandmark .divider {{ width: 1px; height: 26px; background: var(--border); }}
.brandmark .product {{ font-weight: 700; letter-spacing: -0.01em; font-size: 17px; }}
.topbar nav {{ margin-left: auto; display: flex; gap: 4px; flex-wrap: wrap; }}
.topbar nav a {{
  color: var(--ink); text-decoration: none; font-size: 13.5px; font-weight: 500;
  padding: 7px 11px; border-radius: 8px;
}}
.topbar nav a:hover {{ background: var(--muted); color: var(--primary); }}

/* ---- hero ---- */
.hero {{ background: var(--ink); color: #fff; padding: 40px 0 46px; }}
.hero .wrap {{ display: flex; gap: 44px; align-items: center; flex-wrap: wrap; }}
.hero-ring {{ position: relative; flex: 0 0 auto; }}
.ring-value {{ font: 700 46px/1 {brand.FONT_STACK}; fill: #fff; letter-spacing: -0.02em; }}
.ring-label {{ font: 500 12px/1 {brand.FONT_STACK}; fill: rgba(255,255,255,0.55); }}
.hero-copy {{ flex: 1 1 380px; min-width: 300px; }}
.grade-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }}
.grade {{
  font-weight: 700; font-size: 15px; padding: 4px 13px; border-radius: 999px;
  color: #fff; letter-spacing: 0.02em;
}}
.hero h1 {{
  margin: 0 0 10px; font-size: 34px; line-height: 1.15; font-weight: 700;
  letter-spacing: -0.025em; max-width: 32ch;
}}
.hero p {{ margin: 0; color: rgba(255,255,255,0.62); max-width: 58ch; font-size: 14.5px; }}
.delta {{ font-size: 13px; font-weight: 600; padding: 4px 11px; border-radius: 999px; }}
.delta.up {{ background: rgba(22,163,74,0.2); color: #86efac; }}
.delta.down {{ background: rgba(239,68,68,0.2); color: #fca5a5; }}
.delta.flat {{ background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.7); }}

.kpis {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(132px, 1fr));
  gap: 12px; flex: 1 1 100%; margin-top: 6px;
}}
.kpi {{
  background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
  border-radius: var(--radius); padding: 15px 17px;
}}
.kpi b {{ display: block; font-size: 27px; font-weight: 700; letter-spacing: -0.02em; }}
.kpi span {{
  display: block; font-size: 11.5px; text-transform: uppercase;
  letter-spacing: 0.06em; color: rgba(255,255,255,0.5); margin-top: 3px; font-weight: 600;
}}

/* ---- cards ---- */
main {{ padding: 30px 0 12px; }}
.grid {{ display: grid; gap: 18px; grid-template-columns: repeat(12, 1fr); }}
.card {{
  background: #fff; border: 1px solid var(--border); border-radius: var(--radius);
  padding: 22px 24px; grid-column: span 12; min-width: 0;
}}
.card.half {{ grid-column: span 6; }}
.card.third {{ grid-column: span 4; }}
.card.two-thirds {{ grid-column: span 8; }}
@media (max-width: 940px) {{
  .card.half, .card.third, .card.two-thirds {{ grid-column: span 12; }}
  .hero h1 {{ font-size: 27px; }}
}}
.card > h2 {{
  margin: 0 0 3px; font-size: 16.5px; font-weight: 700; letter-spacing: -0.015em;
}}
.card > .sub {{ margin: 0 0 18px; font-size: 13px; color: #6b7280; max-width: 80ch; }}
.card .foot {{
  margin: 16px 0 0; padding-top: 14px; border-top: 1px solid var(--border);
  font-size: 12.5px; color: #6b7280;
}}
.split {{ display: flex; gap: 26px; align-items: center; flex-wrap: wrap; }}
.split > .chart {{ flex: 0 0 auto; }}
.split > .side {{ flex: 1 1 200px; min-width: 180px; }}

/* ---- charts ---- */
.bar-track {{ fill: #eceef4; }}
.bar-label {{ font: 500 13px/1 {brand.FONT_STACK}; fill: var(--ink); }}
.bar-value {{ font: 700 13px/1 {brand.MONO_STACK}; fill: var(--ink); }}
.bar-note {{ font: 400 10.5px/1 {brand.FONT_STACK}; fill: #9aa1ad; }}
.funnel-value {{ font: 700 19px/1 {brand.FONT_STACK}; fill: #fff; }}
.funnel-label {{ font: 600 11.5px/1 {brand.FONT_STACK}; fill: rgba(255,255,255,0.85); }}
.funnel-drop {{ font: 600 11.5px/1 {brand.FONT_STACK}; fill: #9aa1ad; }}
.donut-centre {{ font: 700 20px/1 {brand.FONT_STACK}; fill: var(--ink); }}
.stack {{ border-radius: 6px; overflow: hidden; display: block; }}
.legend {{ list-style: none; margin: 14px 0 0; padding: 0; }}
.legend li {{
  display: flex; align-items: center; gap: 9px; padding: 5px 0; font-size: 13px;
  border-bottom: 1px solid #f1f2f6;
}}
.legend li:last-child {{ border-bottom: 0; }}
.legend b {{ font-weight: 500; flex: 1; }}
.legend em {{ font-style: normal; font-weight: 700; font-family: {brand.MONO_STACK}; }}
.swatch {{ width: 11px; height: 11px; border-radius: 3px; flex: 0 0 auto; }}
.heat {{ display: block; }}
.heat-key {{
  display: flex; gap: 16px; margin-top: 14px; font-size: 12px; color: #6b7280;
  flex-wrap: wrap;
}}
.heat-key span {{ display: flex; align-items: center; gap: 6px; }}

/* ---- tables ---- */
table {{ width: 100%; border-collapse: collapse; font-size: 13.5px; }}
th {{
  text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em;
  color: #6b7280; font-weight: 700; padding: 0 12px 9px 0; border-bottom: 1px solid var(--border);
}}
td {{ padding: 11px 12px 11px 0; border-bottom: 1px solid #f1f2f6; vertical-align: top; }}
tr:last-child td {{ border-bottom: 0; }}
td.num {{ font-family: {brand.MONO_STACK}; font-weight: 700; white-space: nowrap; }}
.pill {{
  display: inline-block; font-size: 11px; font-weight: 700; padding: 3px 9px;
  border-radius: 999px; color: #fff; white-space: nowrap;
}}
code {{
  font-family: {brand.MONO_STACK}; font-size: 12px; background: var(--muted);
  padding: 1.5px 5px; border-radius: 4px;
}}
.objects {{ color: #6b7280; font-size: 12px; }}

/* ---- the checklist ---- */
.checklist {{ background: #fff; border-bottom: 1px solid var(--border); padding: 26px 0 28px; }}
.cl-grid {{
  display: grid; gap: 16px;
  grid-template-columns: repeat(auto-fit, minmax(330px, 1fr));
}}
.cl {{ border: 1px solid var(--border); border-radius: var(--radius); padding: 16px 18px 8px; }}
.cl header {{
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  margin-bottom: 8px;
}}
.cl h3 {{ margin: 0; font-size: 15px; font-weight: 700; letter-spacing: -0.01em; }}
.badge {{
  font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 999px;
  white-space: nowrap; font-family: {brand.MONO_STACK};
}}
.badge.yes {{ background: {brand.GREEN_LIGHT}; color: #15803d; }}
.badge.mostly {{ background: #fdebc8; color: #92400e; }}
.badge.no {{ background: {brand.PEACH_LIGHT}; color: #9f1d1d; }}
.cl ul {{ list-style: none; margin: 0; padding: 0; }}
.cl li {{
  display: flex; align-items: flex-start; gap: 10px; padding: 9px 0;
  border-top: 1px solid #f1f2f6; font-size: 13.5px;
}}
.cl .tick {{
  flex: 0 0 auto; width: 18px; height: 18px; border-radius: 50%; margin-top: 1px;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; color: #fff;
}}
.cl li.yes .tick {{ background: #16a34a; }}
.cl li.yes .tick::before {{ content: "\2713"; }}
.cl li.mostly .tick {{ background: #d97706; }}
.cl li.mostly .tick::before {{ content: "!"; }}
.cl li.no .tick {{ background: {brand.DESTRUCTIVE}; }}
.cl li.no .tick::before {{ content: "\2717"; }}
.cl .say {{ flex: 1; font-weight: 500; }}
.cl .miss {{
  display: block; font-weight: 400; font-size: 12px; color: #6b7280; margin-top: 2px;
  font-family: {brand.MONO_STACK};
}}
.cl .n {{
  flex: 0 0 auto; font-family: {brand.MONO_STACK}; font-size: 12.5px; font-weight: 700;
  color: #6b7280; padding-top: 1px;
}}
.cl li.no .n {{ color: {brand.DESTRUCTIVE}; }}
.cl li.mostly .n {{ color: #b45309; }}

/* ---- model diagrams ---- */
.tabs {{
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 14px;
}}
.tab {{
  font: 600 13.5px/1 {brand.FONT_STACK}; color: #52525b; background: none; border: 0;
  padding: 9px 13px; border-radius: 8px; cursor: pointer;
}}
.tab:hover {{ background: var(--muted); }}
.tab.on {{ background: var(--ink); color: #fff; }}
.zoom {{ margin-left: auto; display: flex; gap: 4px; }}
.zoom button {{
  font: 600 13px/1 {brand.FONT_STACK}; color: var(--ink); background: #fff;
  border: 1px solid var(--border); border-radius: 7px; padding: 7px 11px; cursor: pointer;
}}
.zoom button:hover {{ border-color: var(--primary); color: var(--primary); }}
.pane .blurb {{ margin: 0 0 12px; font-size: 13px; color: #6b7280; }}
.canvas {{
  overflow: auto; max-height: 720px; border: 1px solid var(--border); border-radius: 10px;
  background: #fafbfe; padding: 18px;
}}
.canvas pre.mermaid {{
  margin: 0; font: 12px/1.5 {brand.MONO_STACK}; color: #52525b; white-space: pre;
}}
.canvas pre.mermaid[data-processed] {{ font: inherit; color: inherit; }}
.canvas svg {{ display: block; height: auto; }}
.offline {{
  margin: 0 0 12px; padding: 10px 14px; border-radius: 9px; font-size: 13px;
  background: #fdebc8; color: #92400e;
}}

/* ---- model lanes ---- */
.lanes {{ display: block; }}
.lane-bed {{ fill: #f7f8fc; }}
.lane-head {{
  font: 700 11px/1 {brand.FONT_STACK}; fill: #6b7280; text-transform: uppercase;
  letter-spacing: 0.07em;
}}
.lane-group {{
  font: 700 10.5px/1 {brand.FONT_STACK}; fill: #9aa1ad; text-transform: uppercase;
  letter-spacing: 0.07em;
}}
.lane-box {{ fill: #fff; stroke: var(--primary); stroke-width: 1.5; }}
.lane-box.off {{ fill: none; stroke: #d3d7e0; stroke-dasharray: 4 3; }}
.lane-text {{
  font: 600 12px/1 {brand.MONO_STACK}; fill: var(--ink); dominant-baseline: middle;
}}
.lane-text.off {{ font-weight: 400; fill: #b0b6c2; font-family: {brand.FONT_STACK}; }}
.lane-link {{ stroke-width: 2; }}
.lane-link.ok {{ stroke: #16a34a; }}
.lane-link.broken {{ stroke: {brand.DESTRUCTIVE}; stroke-dasharray: 4 3; }}
.lane-link.unplanned {{ stroke: #d97706; stroke-dasharray: 1 4; stroke-linecap: round; }}
.lane-link.none {{ stroke: #e2e5ec; }}

/* ---- searchable catalogue ---- */
.finder {{
  display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 14px;
}}
.finder input {{
  flex: 1 1 260px; min-width: 200px; font: 400 14px/1.4 {brand.FONT_STACK};
  padding: 9px 12px; border: 1px solid var(--border); border-radius: 9px; color: var(--ink);
}}
.finder input:focus {{ outline: 2px solid var(--primary); outline-offset: -1px; }}
.finder .tally {{ font-size: 12.5px; color: #6b7280; font-family: {brand.MONO_STACK}; }}
.mark {{
  display: inline-block; width: 20px; text-align: center; font-weight: 700; font-size: 14px;
}}
.mark.yes {{ color: #16a34a; }}
.mark.no {{ color: {brand.DESTRUCTIVE}; }}
.mark.off {{ color: #d97706; font-size: 11px; }}
.mark.dash {{ color: #c3c8d2; }}
.scroller {{ overflow-x: auto; }}
.empty {{ padding: 18px 0; color: #6b7280; font-size: 13.5px; }}
[hidden] {{ display: none !important; }}

/* ---- footer ---- */
footer {{
  margin-top: 34px; border-top: 1px solid var(--border); background: #fff;
  padding: 24px 0; font-size: 12.5px; color: #6b7280;
}}
footer .wrap {{ display: flex; gap: 18px; align-items: center; flex-wrap: wrap; }}
footer img {{ height: 19px; opacity: 0.75; }}
footer .meta {{ margin-left: auto; font-family: {brand.MONO_STACK}; font-size: 11.5px; }}
a {{ color: var(--primary); }}
@media print {{
  body {{ background: #fff; }}
  .topbar {{ position: static; }}
  .card {{ break-inside: avoid; }}
}}
"""


def _kpi(value: str, label: str) -> str:
    return f"<div class='kpi'><b>{esc(value)}</b><span>{esc(label)}</span></div>"


def _card(
    title: str, sub: str, body: str, *, span: str = "", foot: str = "", anchor: str = ""
) -> str:
    if not body.strip():
        return ""
    ident = f' id="{esc(anchor)}"' if anchor else ""
    classes = f"card {span}".strip()
    footer = f"<p class='foot'>{foot}</p>" if foot else ""
    return (
        f"<section class='{classes}'{ident}><h2>{esc(title)}</h2>"
        f"<p class='sub'>{esc(sub)}</p>{body}{footer}</section>"
    )


# ---------------------------------------------------------------- checklist


@dataclass(frozen=True)
class Check:
    """One statement about the repository, and whether it holds.

    ``done`` of ``total`` is the whole answer. ``missing`` names the ones that
    let it down, because a fraction tells a reader there is a problem and a
    name tells them where it is. ``rule`` is the rule the numbers came from,
    where there is one, so every figure here can be traced to a finding.
    """

    statement: str
    done: int
    total: int
    missing: tuple[str, ...] = ()
    rule: str | None = None

    @property
    def holds(self) -> bool:
        return self.total > 0 and self.done == self.total

    @property
    def verdict(self) -> str:
        """Green, amber or red. Amber is "nearly", which is 4 in 5 or better."""
        if self.holds:
            return "yes"
        if self.total and self.done >= 0.8 * self.total:
            return "mostly"
        return "no"


@dataclass(frozen=True)
class Section:
    """A group of related statements, with a heading a stakeholder would use."""

    title: str
    checks: tuple[Check, ...]

    @property
    def passed(self) -> int:
        return sum(1 for check in self.checks if check.holds)


def _in_repo(row: AlignmentRow) -> bool:
    """Whether the code for this entity exists, switched on or off.

    A model behind a disabled flag is still written, reviewed and merged. Saying
    it is not built would report the same table as both missing and off-plan.
    """
    return row.repo in (Presence.PRESENT, Presence.DISABLED)


def _from_rule(result: RunResult, statement: str, *rules: str) -> Check | None:
    """A statement backed by one or more rules, counted from what they examined.

    A rule that examined nothing is left out rather than reported as passing:
    there was nothing for it to pass.
    """
    checked = sum(result.examined[rule].checked for rule in rules if rule in result.examined)
    if checked == 0:
        return None
    failing = sorted({finding.subject for finding in result.open_findings if finding.rule in rules})
    # Several rules can fail on the same object. Counting it once is what
    # makes "5 of 6" mean six objects rather than six checks.
    failed = (
        len(failing)
        if len(rules) > 1
        else sum(1 for finding in result.open_findings if finding.rule in rules)
    )
    return Check(statement, max(0, checked - failed), checked, tuple(failing), rules[0])


def checklist(result: RunResult) -> list[Section]:
    """Everything the dashboard asserts about the repository, grouped.

    A section is only shown where Hunter read the source it needs, and a
    statement is only made where there was something to check. A statement
    nobody could test is left off rather than shown as failing.
    """
    rows = result.alignment.rows
    built = [row for row in rows if _in_repo(row)]
    project = result.project
    sections: list[Section] = []

    def add(title: str, *checks: Check | None) -> None:
        kept = tuple(check for check in checks if check is not None)
        if kept:
            sections.append(Section(title, kept))

    # ---- design to build
    design: list[Check | None] = []
    if project.has_conceptual:
        wanted = [row for row in rows if row.conceptual is Presence.PRESENT]
        design.append(
            Check(
                "Every business entity has a design",
                sum(1 for row in wanted if row.designed is Presence.PRESENT),
                len(wanted),
                tuple(sorted(row.label for row in wanted if row.designed is not Presence.PRESENT)),
            )
        )
    if project.has_dbml:
        planned = [row for row in rows if row.designed is Presence.PRESENT]
        design.append(
            Check(
                "Every designed table is built",
                sum(1 for row in planned if _in_repo(row)),
                len(planned),
                tuple(
                    sorted(row.designed_name or row.label for row in planned if not _in_repo(row))
                ),
            )
        )
        design.append(
            Check(
                "Every built table has a design",
                sum(1 for row in built if row.designed is Presence.PRESENT),
                len(built),
                tuple(
                    sorted(
                        row.model_name or row.label
                        for row in built
                        if row.designed is not Presence.PRESENT
                    )
                ),
            )
        )
        design.append(
            _from_rule(
                result,
                "Every built column is in the design",
                "conformance.column_missing_from_design",
            )
        )
        design.append(
            _from_rule(
                result,
                "Every designed column is built",
                "conformance.column_missing_from_model",
            )
        )
    claimed = [row for row in rows if row.claim_matches_reality is not None]
    if claimed:
        design.append(
            Check(
                "The business diagram matches what is built",
                sum(1 for row in claimed if row.claim_matches_reality),
                len(claimed),
                tuple(sorted(row.label for row in claimed if not row.claim_matches_reality)),
            )
        )
    add("Design to build", *design)

    # ---- warehouse to Looker
    if project.has_lookml:
        add(
            "Warehouse to Looker",
            Check(
                "Every built table has a LookML view",
                sum(1 for row in built if project.views_for_model(row.model_name or "")),
                len(built),
                tuple(
                    sorted(
                        row.model_name or row.label
                        for row in built
                        if not project.views_for_model(row.model_name or "")
                    )
                ),
            ),
            _from_rule(
                result,
                "Every LookML view points at a table that exists",
                "crosslayer.view_model_missing",
            ),
            _from_rule(
                result,
                "Every LookML field points at a real column",
                "crosslayer.field_references_missing_column",
            ),
            _from_rule(
                result,
                "Every table reports read from is declared as an exposure",
                "crosslayer.exposure_missing",
            ),
        )

    # ---- Droughty
    if project.has_droughty:
        live_check = None
        introspected = project.droughty.introspected if project.droughty else {}
        if introspected:
            live = {name.lower() for name in introspected}
            live_check = Check(
                "Every built table is live in the warehouse",
                sum(1 for row in built if (row.model_name or "").lower() in live),
                len(built),
                tuple(
                    sorted(
                        row.model_name or row.label
                        for row in built
                        if (row.model_name or "").lower() not in live
                    )
                ),
            )
        add(
            "Droughty",
            live_check,
            _from_rule(
                result,
                "Every built table is covered by Droughty tests",
                "droughty.model_not_covered",
            ),
            _from_rule(
                result,
                "Every Droughty test is applied in dbt",
                "droughty.generated_test_missing",
            ),
            _from_rule(
                result,
                "Every warehouse column is in the design",
                "droughty.introspected_column_undesigned",
            ),
        )

    # ---- documentation
    add(
        "Documentation",
        _from_rule(
            result,
            "Every table carries a description",
            "documentation.model_description_missing",
        ),
        _from_rule(
            result,
            "Every column carries a description",
            "documentation.column_description_missing",
        ),
        _from_rule(result, "Every table has a named owner", "documentation.owner_missing"),
    )

    # ---- tests
    add(
        "Tests",
        _from_rule(result, "Every table has at least one test", "testing.no_tests_at_all"),
        _from_rule(result, "Every key is tested for uniqueness", "testing.key_uniqueness_missing"),
        _from_rule(result, "Every key is tested for nulls", "testing.key_not_null_missing"),
    )
    return sections


def _named(missing: tuple[str, ...], limit: int = 3) -> str:
    if not missing:
        return ""
    shown = ", ".join(missing[:limit])
    if len(missing) > limit:
        shown += f" and {len(missing) - limit} more"
    return shown


def _checklist(result: RunResult) -> str:
    sections = checklist(result)
    if not sections:
        return ""
    cards = []
    for section in sections:
        total = len(section.checks)
        tone = "yes" if section.passed == total else "mostly" if section.passed else "no"
        items = []
        for check in section.checks:
            names = _named(check.missing)
            miss = f"<span class='miss'>{esc(names)}</span>" if names else ""
            items.append(
                f"<li class='{check.verdict}'>"
                f"<span class='tick'></span>"
                f"<span class='say'>{esc(check.statement)}{miss}</span>"
                f"<span class='n'>{check.done} of {check.total}</span></li>"
            )
        cards.append(
            f"<section class='cl'><header><h3>{esc(section.title)}</h3>"
            f"<span class='badge {tone}'>{section.passed} of {total} hold</span></header>"
            f"<ul>{''.join(items)}</ul></section>"
        )
    return f"""<div class="checklist" id="checklist">
  <div class="wrap">
    <div class="cl-grid">{"".join(cards)}</div>
  </div>
</div>"""


# ------------------------------------------------------------------- panels


def _hero(result: RunResult, generated: dt.datetime) -> str:
    score = result.score
    models = [m for m in result.project.models.values() if not m.vendored]
    open_count = len(result.open_findings)
    scored = len(score.dimensions_scored)
    total_areas = scored + len(score.dimensions_skipped)

    delta_html = ""
    if score.delta is not None:
        direction = "up" if score.delta > 0 else "down" if score.delta < 0 else "flat"
        sign = "+" if score.delta > 0 else ""
        delta_html = f"<span class='delta {direction}'>{sign}{score.delta:g} since baseline</span>"

    grade_colour = brand.grade_colour(score.grade)
    return f"""<div class="hero">
  <div class="wrap">
    <div class="hero-ring">{charts.score_ring(score.total, score.grade)}</div>
    <div class="hero-copy">
      <div class="grade-row">
        <span class="grade" style="background:{grade_colour}">Grade {esc(score.grade)}</span>
        {delta_html}
      </div>
      <h1>{esc(score.interpretation)}</h1>
      <p>{len(models)} tables read, {open_count} open findings, {scored} of {total_areas} areas
         measured. Scored on {esc(generated.strftime("%d %B %Y"))} from the repository alone,
         with no warehouse credential.</p>
    </div>
    <div class="kpis">
      {_kpi(str(len(models)), "tables")}
      {_kpi(str(open_count), "open findings")}
      {_kpi(f"{scored}/{total_areas}", "areas measured")}
      {_kpi(str(len(result.alignment.rows)), "entities tracked")}
      {_kpi(str(len(result.suppressed_findings)), "accepted by the team")}
    </div>
  </div>
</div>"""


#: The chain, in the order a table travels along it. Each entry is the lane
#: heading, the attribute on an alignment row, and the source that has to have
#: been read for the lane to mean anything.
LANES: tuple[tuple[str, str, str], ...] = (
    ("Conceptual · the business model", "conceptual", "conceptual"),
    ("Logical · the data flow", "logical", "logical"),
    ("Physical · the DBML design", "designed", "dbml"),
    ("Built · in the repository", "repo", "manifest"),
)

#: How many entities the lane diagram draws before it stops. Past this it stops
#: being a picture and becomes a list, and there is a searchable list below it.
LANE_LIMIT = 30


def _three_models(result: RunResult) -> str:
    """The business, logical and physical models drawn against each other."""
    available = {
        "conceptual": result.project.has_conceptual,
        "logical": any(row.logical is not Presence.UNKNOWN for row in result.alignment.rows),
        "dbml": result.project.has_dbml,
        "manifest": result.project.has_manifest,
    }
    lanes = [lane for lane in LANES if available.get(lane[2])]
    if len(lanes) < 2:
        return ""

    # The two business levels are named in business words and the two technical
    # levels in table names, because that is what each level is written in.
    names = {
        "conceptual": lambda row: row.label,
        "logical": lambda row: row.label,
        "designed": lambda row: row.designed_name or row.key,
        "repo": lambda row: row.model_name or row.key,
    }
    drawn = result.alignment.rows[:LANE_LIMIT]
    rows = [
        LaneRow(
            label=row.label,
            group=row.domain or "",
            cells=tuple(
                LaneCell(
                    present=getattr(row, attr) is Presence.PRESENT,
                    name=names[attr](row),
                    note=row.state_label,
                )
                for _, attr, _ in lanes
            ),
        )
        for row in drawn
    ]

    hidden = len(result.alignment.rows) - len(drawn)
    foot = (
        "Green means the two levels agree. Red is a break: the level on the left "
        "has it, the level on the right does not. Amber is the other way round, "
        "something built that the level above never asked for."
    )
    if hidden > 0:
        foot += f" {hidden} more entities are in the searchable table below."
    return _card(
        "Modelling alignment",
        "The conceptual, logical and physical models against what is built. Read "
        "across one band to follow a single table.",
        charts.model_lanes([lane[0] for lane in lanes], rows),
        foot=foot,
        anchor="alignment",
    )


#: The library that draws the model diagrams, pinned to one version so the same
#: source renders the same way next year. This is the only thing on the page
#: fetched from anywhere. Without it the diagram source is shown as text and
#: everything else on the page is unaffected.
MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"

#: The three diagrams, in the order a stakeholder reads them.
DIAGRAMS: tuple[tuple[str, str, str], ...] = (
    ("conceptual", "Conceptual", "The business entities, grouped by area, coloured by state."),
    ("logical", "Logical", "The designed tables from the DBML, with their keys and attributes."),
    ("physical", "Physical", "The tables as built, with their real columns and types."),
)


def _diagrams(result: RunResult) -> str:
    """The three models as diagrams a stakeholder can switch between and zoom."""
    from hunter.emit import mermaid

    sources = {
        "conceptual": mermaid.conceptual_diagram(result.alignment)
        if result.project.has_conceptual
        else "",
        "logical": mermaid.logical_diagram(result.project, result.alignment)
        if result.project.has_dbml
        else "",
        "physical": mermaid.physical_diagram(result.project, result.alignment),
    }
    available = [
        (key, label, blurb)
        for key, label, blurb in DIAGRAMS
        if sources[key].strip() and sources[key].strip() not in ("erDiagram", "flowchart TB")
    ]
    if not available:
        return ""

    tabs = "".join(
        f"<button type='button' class='tab{' on' if index == 0 else ''}' "
        f"data-pane='{key}' aria-selected='{'true' if index == 0 else 'false'}'>"
        f"{esc(label)}</button>"
        for index, (key, label, _) in enumerate(available)
    )
    panes = "".join(
        f"<div class='pane' id='pane-{key}'{'' if index == 0 else ' hidden'}>"
        f"<p class='blurb'>{esc(blurb)}</p>"
        f"<div class='canvas'><pre class='mermaid'>{esc(sources[key].strip())}</pre></div>"
        "</div>"
        for index, (key, _, blurb) in enumerate(available)
    )
    controls = (
        "<div class='zoom' hidden>"
        "<button type='button' data-zoom='out' aria-label='Zoom out'>&minus;</button>"
        "<button type='button' data-zoom='reset'>Fit</button>"
        "<button type='button' data-zoom='in' aria-label='Zoom in'>+</button>"
        "</div>"
    )
    offline = (
        "<p class='offline' id='diagram-offline' hidden>The diagram library could not be "
        "loaded, so the diagram source is shown as text. Open this page with a "
        "connection to see it drawn.</p>"
    )
    return _card(
        "Model diagrams",
        "Switch between the three models. Drag to scroll, use the buttons to zoom. "
        "Colour follows the state in the catalogue below.",
        f"<div class='tabs' role='tablist'>{tabs}{controls}</div>{offline}{panes}",
        anchor="diagrams",
    )


#: What one cell in the catalogue can say. "off" is a table whose code exists
#: but is switched off; "unknown" is a level Hunter had no source for.
MARKS: dict[str, tuple[str, str, str]] = {
    "yes": ("yes", "&#10003;", "yes"),
    "no": ("no", "&#10007;", "no"),
    "off": ("off", "&#9679;", "built but switched off"),
    "unknown": ("dash", "&#8211;", "Hunter had nothing to read"),
}


def _mark(state: str) -> str:
    klass, glyph, title = MARKS[state]
    return f"<span class='mark {klass}' title='{title}'>{glyph}</span>"


@dataclass(frozen=True)
class CatalogueRow:
    """One table, and what stands behind it at every level."""

    name: str
    business: str
    domain: str
    designed: str
    built: str
    warehouse: str
    looker: str
    state: str
    is_table: bool = True

    @property
    def searchable(self) -> str:
        parts = (self.name, self.business, self.domain, self.state)
        return " ".join(part for part in parts if part).lower()


def catalogue_rows(result: RunResult) -> list[CatalogueRow]:
    """Every table Hunter saw anywhere, sorted by area then name.

    The union matters. A table can be in the design and not the repository, in
    the repository and not the warehouse, or in the warehouse and in neither,
    and a list built from any single source hides one of those three.
    """
    project = result.project
    introspected = project.droughty.introspected if project.droughty else {}
    live = {name.lower(): name for name in introspected}
    knows_warehouse = bool(live)
    knows_looker = project.has_lookml
    knows_design = project.has_dbml

    def looker_for(model_name: str | None) -> str:
        if not knows_looker:
            return "unknown"
        return "yes" if model_name and project.views_for_model(model_name) else "no"

    rows: list[CatalogueRow] = []
    seen: set[str] = set()

    for row in result.alignment.rows:
        name = row.technical_name or ""
        lookup = name.lower()
        if lookup:
            seen.add(lookup)
        if row.repo is Presence.PRESENT:
            built = "yes"
        elif row.repo is Presence.DISABLED:
            built = "off"
        else:
            built = "no"
        rows.append(
            CatalogueRow(
                name=name or row.label,
                business=row.business_name or "",
                domain=row.domain or "",
                designed=("yes" if row.designed is Presence.PRESENT else "no")
                if knows_design
                else "unknown",
                built=built,
                warehouse=("yes" if lookup in live else "no") if knows_warehouse else "unknown",
                looker=looker_for(row.model_name),
                state=row.state_label,
                is_table=bool(name),
            )
        )

    # Anything the warehouse holds that no design and no model accounts for.
    for lowered, name in sorted(live.items()):
        if lowered in seen:
            continue
        rows.append(
            CatalogueRow(
                name=name,
                business="",
                domain="",
                designed="no" if knows_design else "unknown",
                built="no",
                warehouse="yes",
                looker=looker_for(None),
                state="Untracked table",
            )
        )

    rows.sort(key=lambda row: (row.domain or "~", row.name))
    return rows


def _catalogue(result: RunResult) -> str:
    """Every table, at every level, with a search box over it."""
    rows = catalogue_rows(result)
    if not rows:
        return ""
    knows_warehouse = any(row.warehouse != "unknown" for row in rows)
    knows_looker = any(row.looker != "unknown" for row in rows)

    heads = ["Table", "Area", "In the design", "In the repository"]
    if knows_warehouse:
        heads.append("In the warehouse")
    if knows_looker:
        heads.append("Looker view")
    heads.append("Where it stands")

    body = []
    for row in rows:
        if row.is_table:
            label = f"<code>{esc(row.name)}</code>"
        else:
            label = f"{esc(row.name)} <span class='objects'>(no table yet)</span>"
        if row.business and row.business.lower() != row.name.lower():
            label += f"<br><span class='objects'>{esc(row.business)}</span>"
        cells = [
            f"<td>{label}</td>",
            f"<td class='objects'>{esc(row.domain.replace('_', ' ') or '-')}</td>",
            f"<td>{_mark(row.designed)}</td>",
            f"<td>{_mark(row.built)}</td>",
        ]
        if knows_warehouse:
            cells.append(f"<td>{_mark(row.warehouse)}</td>")
        if knows_looker:
            cells.append(f"<td>{_mark(row.looker)}</td>")
        cells.append(f"<td class='objects'>{esc(row.state)}</td>")
        body.append(f'<tr data-find="{esc(row.searchable)}">{"".join(cells)}</tr>')

    header = "".join(f"<th>{esc(head)}</th>" for head in heads)
    finder = (
        "<div class='finder'>"
        "<input type='search' id='table-search' autocomplete='off'"
        " placeholder='Search a table, an area or a state'"
        " aria-label='Search the table list'>"
        f"<span class='tally' id='table-tally'>{len(rows)} tables</span>"
        "</div>"
    )
    key = (
        "<div class='heat-key'>"
        "<span><b class='mark yes'>&#10003;</b> it is there</span>"
        "<span><b class='mark no'>&#10007;</b> it is not</span>"
        "<span><b class='mark off'>&#9679;</b> built but switched off</span>"
        "<span><b class='mark dash'>&#8211;</b> Hunter had nothing to read</span>"
        "</div>"
    )
    foot = ""
    if knows_warehouse:
        foot = (
            "The warehouse column is read from the Droughty introspection committed "
            "in the repository, not from a live connection."
        )
    return _card(
        "Every table, and what stands behind it",
        "One row per table. Type to filter.",
        finder + "<div class='scroller'><table id='table-list'>"
        f"<thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
        "<p class='empty' id='table-empty' hidden>Nothing matches that.</p>" + key,
        foot=foot,
        anchor="catalogue",
    )


def _load_bearing(result: RunResult) -> str:
    """The tables most is built on, and whether anything checks them.

    This is the panel a lead reads before agreeing to a change. A table with
    nothing downstream can be wrong for a week and nobody notices. A table
    twelve things read, with no key test, is where a silent error becomes
    twelve wrong dashboards.
    """
    project = result.project
    candidates = [
        model
        for model in project.models.values()
        if not model.vendored and (model.downstream_count or model.exposure_weight > 1.0)
    ]
    if not candidates:
        return ""

    # Reach counts report views as well as tables. A table nothing else reads
    # but a dashboard does is exactly as load-bearing as one three tables read,
    # and ranking on tables alone would have sorted it to the bottom.
    def reach_of(model: object) -> int:
        return model.downstream_count + len(project.views_for_model(model.name))  # type: ignore[attr-defined]

    candidates.sort(key=lambda m: (-reach_of(m), m.name))
    widest = max(reach_of(model) for model in candidates) or 1

    rows = []
    for model in candidates[:8]:
        tests = project.tests_for(model.name)
        keyed = any(test.is_key_test for test in tests)
        views = len(project.views_for_model(model.name))
        if keyed:
            mark = "<span class='pill' style='background:#16a34a'>checked</span>"
        elif tests:
            mark = "<span class='pill' style='background:#d97706'>weak checks only</span>"
        else:
            mark = (
                f"<span class='pill' style='background:{brand.DESTRUCTIVE}'>"
                "nothing checks it</span>"
            )
        meter = charts.meter(
            reach_of(model),
            widest,
            colour=brand.PRIMARY if keyed else brand.DESTRUCTIVE,
        )
        rows.append(
            f"<tr><td><code>{esc(model.name)}</code></td>"
            f"<td class='num'>{model.downstream_count}</td>"
            f"<td class='num'>{views}</td>"
            f"<td>{meter}</td>"
            f"<td>{mark}</td></tr>"
        )
    return _card(
        "What everything else is built on",
        "Ranked by reach: tables downstream plus report views. Long reach and "
        "nothing checking it is where one silent error becomes many wrong numbers.",
        "<table><thead><tr><th>Table</th><th>Tables downstream</th>"
        "<th>Report views</th><th>Reach</th><th>Is it checked</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>",
        span="two-thirds",
        anchor="load-bearing",
    )


def _queue(result: RunResult) -> str:
    fixes = top_fixes(result, limit=12)
    if not fixes:
        return ""
    rows = []
    for fix in fixes:
        objects = ", ".join(str(item) for item in list(fix["objects"])[:3])  # type: ignore[call-overload]
        more = int(fix["count"]) - 3  # type: ignore[call-overload]
        if more > 0:
            objects += f" and {more} more"
        colour = brand.severity_colour(str(fix["severity"]))
        rows.append(
            f"<tr><td class='num'>{fix['points_recoverable']}</td>"
            f"<td><span class='pill' style='background:{colour}'>"
            f"{esc(severity_label(Severity(str(fix['severity']))))}</span></td>"
            f"<td><b>{esc(fix['heading'])}</b><br><span class='objects'>{esc(objects)}</span></td>"
            f"<td>{esc(fix['consequence'])}</td></tr>"
        )
    return _card(
        "Do these first",
        "Ranked by the points closing the whole group would recover.",
        "<table><thead><tr><th>Points back</th><th>How much it matters</th>"
        "<th>What is wrong</th><th>What breaks if it is left</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>",
        anchor="queue",
    )


def _not_checked(result: RunResult) -> str:
    from hunter.emit.markdown import UNAVAILABLE_REASONS

    missing = sorted(set(UNAVAILABLE_REASONS) - set(result.available))
    skipped = [DIMENSION_HEADINGS[dimension] for dimension in result.score.dimensions_skipped]
    if not missing and not skipped:
        return ""
    rows = "".join(
        f"<tr><td><code>{esc(item)}</code></td><td>{esc(UNAVAILABLE_REASONS[item])}</td></tr>"
        for item in missing
    )
    rows += "".join(
        f"<tr><td>{esc(heading)}</td><td>Not measured. Left out of the score, with its "
        "weight shared across the areas that were.</td></tr>"
        for heading in skipped
    )
    return _card(
        "What this score is not based on",
        "Anything Hunter could not read is excluded, never scored as zero.",
        f"<table><thead><tr><th>Not available</th><th>What that means</th></tr>"
        f"</thead><tbody>{rows}</tbody></table>",
        span="half",
        anchor="not-checked",
    )


def _sources(result: RunResult) -> str:
    if not result.sources_read:
        return ""
    rows = "".join(f"<tr><td><code>{esc(path)}</code></td></tr>" for path in result.sources_read)
    return _card(
        "Every file this was computed from",
        "Nothing else was read. Nothing was written.",
        f"<table><tbody>{rows}</tbody></table>",
        span="half",
        anchor="sources",
    )


# --------------------------------------------------------------------- page


NAV = [
    ("#checklist", "Checklist"),
    ("#alignment", "Modelling alignment"),
    ("#diagrams", "Diagrams"),
    ("#catalogue", "Every table"),
    ("#queue", "Do first"),
    ("scorecard/", "Full report"),
]

#: The only script on the page. It filters a table that is already fully
#: rendered in the HTML, so with scripting switched off every row still shows
#: and nothing on the page depends on it running.
SEARCH_JS = """
(function () {
  var box = document.getElementById('table-search');
  var table = document.getElementById('table-list');
  if (!box || !table) { return; }
  var tally = document.getElementById('table-tally');
  var empty = document.getElementById('table-empty');
  var rows = Array.prototype.slice.call(table.tBodies[0].rows);
  function filter() {
    var needle = box.value.trim().toLowerCase();
    var shown = 0;
    for (var i = 0; i < rows.length; i++) {
      var hit = !needle || rows[i].getAttribute('data-find').indexOf(needle) !== -1;
      rows[i].hidden = !hit;
      if (hit) { shown++; }
    }
    if (tally) {
      tally.textContent = shown === rows.length
        ? rows.length + ' tables'
        : shown + ' of ' + rows.length + ' tables';
    }
    if (empty) { empty.hidden = shown !== 0; }
  }
  box.addEventListener('input', filter);
})();
"""

#: Tabs and zoom for the model diagrams. Each diagram is drawn the first time
#: its tab is opened, because the library measures text and a hidden element
#: measures as nothing. If the library never arrived the source stays as text
#: and a note says so.
DIAGRAM_JS = """
(function () {
  var card = document.getElementById('diagrams');
  if (!card) { return; }
  var tabs = card.querySelectorAll('.tab');
  var zoom = card.querySelector('.zoom');
  var note = document.getElementById('diagram-offline');
  var scale = {};
  var ready = typeof window.mermaid !== 'undefined' && !window.hunterDiagramsOffline;
  if (ready) {
    window.mermaid.initialize({ startOnLoad: false, theme: 'neutral',
      themeVariables: { fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif' } });
  } else if (note) {
    note.hidden = false;
  }
  function pane(key) { return document.getElementById('pane-' + key); }
  function svgOf(key) { var p = pane(key); return p ? p.querySelector('svg') : null; }
  function apply(key) {
    var svg = svgOf(key);
    if (!svg) { return; }
    var base = parseFloat(svg.getAttribute('data-base') || '0');
    if (!base) {
      base = svg.getBoundingClientRect().width || 800;
      svg.setAttribute('data-base', String(base));
    }
    svg.style.maxWidth = 'none';
    svg.style.width = (base * (scale[key] || 1)) + 'px';
  }
  function draw(key) {
    var p = pane(key);
    if (!ready || !p) { return; }
    var pre = p.querySelector('pre.mermaid');
    if (!pre || pre.getAttribute('data-processed')) { apply(key); return; }
    window.mermaid.run({ nodes: [pre] }).then(function () {
      scale[key] = 1; apply(key);
      if (zoom) { zoom.hidden = false; }
    }).catch(function () { if (note) { note.hidden = false; } });
  }
  var current = null;
  function show(key) {
    current = key;
    for (var i = 0; i < tabs.length; i++) {
      var on = tabs[i].getAttribute('data-pane') === key;
      tabs[i].classList.toggle('on', on);
      tabs[i].setAttribute('aria-selected', on ? 'true' : 'false');
      var p = pane(tabs[i].getAttribute('data-pane'));
      if (p) { p.hidden = !on; }
    }
    draw(key);
  }
  for (var i = 0; i < tabs.length; i++) {
    tabs[i].addEventListener('click', function (event) {
      show(event.currentTarget.getAttribute('data-pane'));
    });
  }
  if (zoom) {
    zoom.addEventListener('click', function (event) {
      var what = event.target.getAttribute('data-zoom');
      if (!what || !current) { return; }
      var s = scale[current] || 1;
      if (what === 'in') { s = Math.min(4, s * 1.25); }
      else if (what === 'out') { s = Math.max(0.25, s / 1.25); }
      else { s = 1; }
      scale[current] = s;
      apply(current);
    });
  }
  if (tabs.length) { show(tabs[0].getAttribute('data-pane')); }
})();
"""


def dashboard_html(result: RunResult, *, generated_at: dt.datetime | None = None) -> str:
    """The whole dashboard, as one self-contained HTML document."""
    generated = generated_at or dt.datetime.now()
    branding = result.config.branding
    title = branding.site_name
    if branding.client_name:
        title = f"{branding.client_name}: {title}"

    panels = "".join(
        [
            _three_models(result),
            _diagrams(result),
            _catalogue(result),
            _load_bearing(result),
            _queue(result),
            _not_checked(result),
            _sources(result),
        ]
    )
    nav = "".join(f"<a href='{esc(href)}'>{esc(label)}</a>" for href, label in NAV)
    meta = result.meta
    stamp = " · ".join(
        part
        for part in (
            f"hunter {meta.get('hunter_version')}" if meta.get("hunter_version") else "",
            f"house {meta.get('house_ruleset_version')}"
            if meta.get("house_ruleset_version")
            else "",
            f"commit {str(meta.get('commit'))[:8]}" if meta.get("commit") else "",
        )
        if part
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · Rittman Hunter</title>
<link rel="icon" href="{brand.favicon_uri()}">
<style>{STYLE}</style>
</head>
<body>
<header class="topbar"><div class="wrap">
  <div class="brandmark">
    <img src="{brand.logo_uri()}" alt="Rittman Analytics">
    <span class="divider"></span>
    <span class="product">Hunter</span>
  </div>
  <nav>{nav}</nav>
</div></header>

{_hero(result, generated)}
{_checklist(result)}

<main><div class="wrap"><div class="grid">{panels}</div></div></main>

<footer><div class="wrap">
  <img src="{brand.logo_uri()}" alt="Rittman Analytics">
  <span>{esc(branding.attribution)}. Read from the repository, nothing written back.</span>
  <span class="meta">{esc(stamp)}</span>
</div></footer>
<script>{SEARCH_JS}</script>
<script src="{MERMAID_URL}" onerror="window.hunterDiagramsOffline=true"></script>
<script>{DIAGRAM_JS}</script>
</body>
</html>
"""
