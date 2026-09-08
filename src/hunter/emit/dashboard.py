"""The report front page, as a self-contained dashboard.

One HTML file with the stylesheet, the charts and the logo inlined. No network
request, nothing to install. It opens from a build artifact, a shared drive or
an email attachment and looks the same in all three.

There is one inline script, and it does one thing: filter the table list as
somebody types. Every row is already in the HTML, so with scripting switched
off the whole page still reads. Nothing else on the page depends on it.

The page is built to be read in this order, and each band answers one question:

    the number        how healthy is this repository
    the questions     do the layers agree with each other
    the alert strip   what has nobody decided
    the lanes         the same entities at every model level
    the table list    what have we got, and what stands behind each one
    the areas         where is the ground being lost
    the funnel        how much of the plan is real
    the grid          is this a few bad tables or a habit
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
from hunter.emit.charts import LaneCell, LaneRow, Slice, esc
from hunter.emit.plain import (
    DIMENSION_HEADINGS,
    severity_label,
    state_summary,
    top_fixes,
)
from hunter.enums import AlignmentState, Dimension, Presence, Severity
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

/* ---- alert strip ---- */
.alerts {{ background: {brand.PEACH_LIGHT}; border-bottom: 1px solid #f0a99f; padding: 26px 0; }}
.alerts h2 {{
  margin: 0 0 4px; font-size: 12px; text-transform: uppercase;
  letter-spacing: 0.09em; color: #8a2f1c; font-weight: 700;
}}
.alerts .lead {{ margin: 0 0 18px; font-size: 14px; color: #7c3a2a; max-width: 74ch; }}
.alert-grid {{
  display: grid; gap: 14px;
  grid-template-columns: repeat(auto-fit, minmax(268px, 1fr));
}}
.alert {{
  background: #fff; border-radius: var(--radius); padding: 18px 20px;
  border-left: 5px solid var(--peach);
}}
.alert .count {{
  font-size: 25px; font-weight: 700; letter-spacing: -0.02em; display: block;
}}
.alert .what {{ font-weight: 600; margin: 3px 0 7px; font-size: 14.5px; }}
.alert .why {{ margin: 0; font-size: 13px; color: #52525b; }}

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

/* ---- the sync questions ---- */
.sync {{ background: #fff; border-bottom: 1px solid var(--border); padding: 26px 0; }}
.sync h2 {{
  margin: 0 0 14px; font-size: 12px; text-transform: uppercase;
  letter-spacing: 0.09em; color: #6b7280; font-weight: 700;
}}
.sync-grid {{
  display: grid; gap: 14px;
  grid-template-columns: repeat(auto-fit, minmax(232px, 1fr));
}}
.q {{
  border: 1px solid var(--border); border-radius: var(--radius); padding: 16px 18px;
  border-top: 4px solid var(--border);
}}
.q.yes {{ border-top-color: #16a34a; }}
.q.mostly {{ border-top-color: #d97706; }}
.q.no {{ border-top-color: {brand.DESTRUCTIVE}; }}
.q .answer {{ font-size: 15px; font-weight: 700; margin: 0 0 2px; }}
.q.yes .answer {{ color: #15803d; }}
.q.mostly .answer {{ color: #b45309; }}
.q.no .answer {{ color: {brand.DESTRUCTIVE}; }}
.q .ask {{ margin: 0 0 8px; font-size: 14px; font-weight: 600; }}
.q .count {{
  margin: 0; font-size: 12.5px; color: #6b7280; font-family: {brand.MONO_STACK};
}}
.q .miss {{ margin: 6px 0 0; font-size: 12.5px; color: #52525b; }}

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


# ------------------------------------------------- the questions in the band


@dataclass(frozen=True)
class Question:
    """One plain question about whether two levels agree.

    ``done`` of ``total`` is the whole answer. ``missing`` names the ones that
    do not, because a fraction tells a reader there is a problem and a name
    tells them where it is.
    """

    ask: str
    done: int
    total: int
    missing: tuple[str, ...] = ()

    @property
    def verdict(self) -> str:
        """Green, amber or red. Amber is "nearly", which is 4 in 5 or better."""
        if self.total == 0:
            return "mostly"
        if self.done == self.total:
            return "yes"
        return "mostly" if self.done >= 0.8 * self.total else "no"

    @property
    def answer(self) -> str:
        short = self.total - self.done
        if self.total == 0:
            return "Nothing to compare"
        if short == 0:
            return "Yes, all of them"
        return f"No, {short} of {self.total} " + ("is" if short == 1 else "are") + " missing"


def _in_repo(row: AlignmentRow) -> bool:
    """Whether the code for this entity exists, switched on or off.

    A model behind a disabled flag is still written, reviewed and merged. Saying
    it is not built would report the same table as both missing and off-plan.
    """
    return row.repo in (Presence.PRESENT, Presence.DISABLED)


def sync_questions(result: RunResult) -> list[Question]:
    """The layer-by-layer agreement questions, in reading order.

    Each one is asked only where Hunter read the source it needs. A question
    nobody could answer is left off rather than answered "no".
    """
    rows = result.alignment.rows
    built = [row for row in rows if _in_repo(row)]
    project = result.project
    out: list[Question] = []

    if project.has_conceptual:
        wanted = [row for row in rows if row.conceptual is Presence.PRESENT]
        designed = [row for row in wanted if row.designed is Presence.PRESENT]
        out.append(
            Question(
                "Does every business entity have a design?",
                len(designed),
                len(wanted),
                tuple(sorted(row.label for row in wanted if row.designed is not Presence.PRESENT)),
            )
        )

    if project.has_dbml:
        planned = [row for row in rows if row.designed is Presence.PRESENT]
        out.append(
            Question(
                "Is every designed table built?",
                sum(1 for row in planned if _in_repo(row)),
                len(planned),
                tuple(
                    sorted(row.designed_name or row.label for row in planned if not _in_repo(row))
                ),
            )
        )
        out.append(
            Question(
                "Does every built table have a design?",
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

    if project.has_droughty and project.droughty and project.droughty.introspected:
        live = {name.lower() for name in project.droughty.introspected}
        out.append(
            Question(
                "Is every built table live in the warehouse?",
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
        )

    if project.has_lookml:
        out.append(
            Question(
                "Does every built table have a Looker view?",
                sum(1 for row in built if project.views_for_model(row.model_name or "")),
                len(built),
                tuple(
                    sorted(
                        row.model_name or row.label
                        for row in built
                        if not project.views_for_model(row.model_name or "")
                    )
                ),
            )
        )

    claimed = [row for row in rows if row.claim_matches_reality is not None]
    if claimed:
        agree = [row for row in claimed if row.claim_matches_reality]
        out.append(
            Question(
                "Does the business diagram match what is built?",
                len(agree),
                len(claimed),
                tuple(sorted(row.label for row in claimed if not row.claim_matches_reality)),
            )
        )

    return out


def _sync(result: RunResult) -> str:
    questions = sync_questions(result)
    if not questions:
        return ""
    cards = []
    for item in questions:
        miss = ""
        if item.missing:
            named = ", ".join(item.missing[:3])
            if len(item.missing) > 3:
                named += f" and {len(item.missing) - 3} more"
            miss = f"<p class='miss'>{esc(named)}</p>"
        cards.append(
            f"<div class='q {item.verdict}'>"
            f"<p class='ask'>{esc(item.ask)}</p>"
            f"<p class='answer'>{esc(item.answer)}</p>"
            f"<p class='count'>{item.done} of {item.total}</p>"
            f"{miss}</div>"
        )
    return f"""<div class="sync" id="sync">
  <div class="wrap">
    <h2>Do the layers agree</h2>
    <div class="sync-grid">{"".join(cards)}</div>
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


def _alerts(result: RunResult) -> str:
    """Systemic gaps and off-plan builds, above everything else.

    These are the entries where the answer is a decision rather than a task, so
    they sit above the score. A weighted mean turns "nobody owns anything" into
    a rounding error.
    """
    cards: list[str] = []
    for gap in result.score.systemic_gaps[:4]:
        cards.append(
            f"<div class='alert'><span class='count'>{gap.failed} of {gap.checked}</span>"
            f"<p class='what'>{esc(gap.plain_heading or DIMENSION_HEADINGS[gap.dimension])}</p>"
            f"<p class='why'>{esc(gap.consequence)}</p></div>"
        )

    off_plan = result.alignment.by_state(AlignmentState.BUILT_OFF_PLAN)
    if off_plan and len(cards) < 4:
        names = ", ".join(sorted(row.technical_name or row.label for row in off_plan)[:3])
        cards.append(
            f"<div class='alert'><span class='count'>{len(off_plan)}</span>"
            f"<p class='what'>Built with no design behind it</p>"
            f"<p class='why'>{esc(names)}. Either the design is out of date or these "
            f"were never agreed. Somebody has to say which.</p></div>"
        )

    if not cards:
        return ""
    return f"""<div class="alerts">
  <div class="wrap">
    <h2>Needs a decision, not a fix</h2>
    <p class="lead">Each of these was missing everywhere Hunter looked. One decision
       nobody has taken, not a list of separate defects.</p>
    <div class="alert-grid">{"".join(cards)}</div>
  </div>
</div>"""


def _areas(result: RunResult) -> str:
    rows = [
        Slice(
            label=DIMENSION_HEADINGS[entry.dimension],
            value=round(entry.score, 1),
            colour=brand.grade_colour(entry.grade),
            note=(
                f"carries {entry.effective_weight:.0f} of the 100 points"
                f" · {entry.finding_count} findings"
            ),
        )
        for entry in result.score.dimensions
        if entry.scored
    ]
    rows.sort(key=lambda row: row.value)
    if not rows:
        return ""

    skipped = [
        DIMENSION_HEADINGS[entry.dimension] for entry in result.score.dimensions if not entry.scored
    ]
    foot = ""
    if skipped:
        foot = (
            f"Not measured: {esc(', '.join(skipped))}. Excluded from the score rather "
            "than counted as zero, with its weight shared across the areas above."
        )
    return _card(
        "Where the ground is being lost",
        "Each area out of 100, weakest first. The weight is how much of the total it can move.",
        charts.bars(rows, maximum=100.0, width=700, label_width=260),
        span="two-thirds",
        foot=foot,
        anchor="areas",
    )


def _severity_mix(result: RunResult) -> str:
    order = [Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]
    counts = dict.fromkeys(order, 0)
    for finding in result.open_findings:
        if finding.severity in counts:
            counts[finding.severity] += 1
    slices = [
        Slice(severity_label(level), counts[level], brand.severity_colour(str(level)))
        for level in order
        if counts[level]
    ]
    if not slices:
        return ""
    total = sum(item.value for item in slices)
    return _card(
        "What kind of problem this is",
        "Open findings, by how much each one matters.",
        "<div class='split'>"
        f"<div class='chart'>{charts.donut(slices, centre_label=f'{total:g}')}</div>"
        f"<div class='side'>{charts.legend(slices)}</div>"
        "</div>",
        span="third",
        anchor="severity",
    )


def _funnel(result: RunResult) -> str:
    coverage = result.alignment.coverage
    stages = [
        Slice(
            "Asked for by the business",
            coverage.conceptual_entities,
            brand.PRIMARY,
            "never designed",
        ),
        Slice("Designed", coverage.designed_entities, brand.ACCENT, "designed, not built"),
        Slice("Built in the repository", coverage.built_entities, brand.SKY, "built, not deployed"),
    ]
    if result.alignment.warehouse_known:
        stages.append(Slice("Live in the warehouse", coverage.deployed_entities, "#16a34a"))
    stages = [stage for stage in stages if stage.value > 0]
    if len(stages) < 2:
        return ""

    foot = "The warehouse stage needs read access and is milestone M2, so it is not drawn."
    if result.alignment.warehouse_known:
        foot = ""
    return _card(
        "How much of the plan is real",
        "Every entity, from what the business asked for to what exists.",
        charts.funnel(stages, band=92),
        span="half",
        foot=foot,
        anchor="funnel",
    )


def _states(result: RunResult) -> str:
    summary = state_summary(result)
    if not summary:
        return ""
    palette = {
        "Designed and delivered": "#16a34a",
        "Built, not deployed": brand.SKY,
        "Built, switched off": brand.MUTED_INK,
        "Approved off-plan": brand.ACCENT,
        "Built off-plan": brand.PEACH,
        "Off-plan, not deployed": brand.PEACH,
        "Designed, not started": "#d97706",
        "On the business model only": brand.PRIMARY,
        "On the data flow diagram only": brand.BLUE_LIGHT,
    }
    slices = [
        Slice(label, count, palette.get(label, brand.MUTED_INK)) for label, count, _ in summary
    ]
    rows = "".join(
        f"<tr><td><span class='pill' style='background:{esc(item.colour)}'>"
        f"{esc(item.label)}</span></td>"
        f"<td class='num'>{item.value:g}</td>"
        f"<td class='objects'>{esc(meaning)}</td></tr>"
        for item, (_, _, meaning) in zip(slices, summary, strict=True)
    )
    return _card(
        "Every entity, and where it stands",
        "One state per entity.",
        charts.stacked(slices)
        + "<table><thead><tr><th>State</th><th>Count</th><th>What it means</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>",
        span="half",
        anchor="states",
    )


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
        "The three models, and what was built",
        "Read across one band to follow a single table from what the business asked "
        "for to what exists.",
        charts.model_lanes([lane[0] for lane in lanes], rows),
        foot=foot,
        anchor="models",
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


def _rule_grid(result: RunResult) -> str:
    """One square per rule, shaded by how much of what it checked it passed."""
    from hunter.checks.base import REGISTRY

    failures: dict[str, int] = {}
    for finding in result.open_findings:
        failures[finding.rule] = failures.get(finding.rule, 0) + 1

    cells: list[Slice] = []
    clean = amber = bad = unchecked = 0
    for rule in REGISTRY.all():
        if rule.about_coverage:
            continue
        rule_id = rule.id
        denominator = result.examined.get(rule_id)
        checked = denominator.checked if denominator else 0
        failed = failures.get(rule_id, 0)
        if checked == 0:
            colour, note = "#e8eaf0", "not applicable here"
            unchecked += 1
        else:
            share = 1.0 - (failed / checked)
            if share >= 0.999:
                colour, note = "#16a34a", f"passed all {checked}"
                clean += 1
            elif share >= 0.9:
                colour, note = "#a3d977", f"{failed} of {checked} failed"
                amber += 1
            elif share >= 0.5:
                colour, note = "#d97706", f"{failed} of {checked} failed"
                amber += 1
            else:
                colour, note = brand.DESTRUCTIVE, f"{failed} of {checked} failed"
                bad += 1
        # The rule id, not rule.title: a title is a template carrying
        # placeholders like {subject}, filled from a finding's own evidence.
        # There is no finding behind a square that passed, so a title here
        # would render as raw "{subject} is built but switched off".
        cells.append(Slice(rule_id, 1, colour, note))

    if not cells:
        return ""
    key = (
        "<div class='heat-key'>"
        f"<span><i class='swatch' style='background:#16a34a'></i>passed everything ({clean})</span>"
        f"<span><i class='swatch' style='background:#d97706'></i>failed somewhere ({amber})</span>"
        f"<span><i class='swatch' style='background:{brand.DESTRUCTIVE}'></i>"
        f"failed more than half ({bad})</span>"
        f"<span><i class='swatch' style='background:#e8eaf0'></i>"
        f"nothing to check ({unchecked})</span>"
        "</div>"
    )
    return _card(
        "Every rule at once",
        f"One square per rule, {len(cells)} of them. Hover a square for its numbers.",
        charts.heat_grid(cells, columns=16) + key,
        span="two-thirds",
        anchor="rules",
    )


def _findings_by_area(result: RunResult) -> str:
    counts: dict[Dimension, int] = {}
    for finding in result.open_findings:
        counts[finding.dimension] = counts.get(finding.dimension, 0) + 1
    grades = {entry.dimension: brand.grade_colour(entry.grade) for entry in result.score.dimensions}
    rows = sorted(
        (
            Slice(
                DIMENSION_HEADINGS[dimension],
                count,
                grades.get(dimension, brand.MUTED_INK),
            )
            for dimension, count in sorted(counts.items())
        ),
        key=lambda row: row.value,
    )
    if not rows:
        return ""
    return _card(
        "Where the findings are",
        "Open findings per area. A large count on a well-scored area means many small things.",
        charts.bars(rows, width=440, label_width=250, row_height=34),
        span="third",
        anchor="by-area",
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
    if not missing:
        return ""
    rows = "".join(
        f"<tr><td><code>{esc(item)}</code></td><td>{esc(UNAVAILABLE_REASONS[item])}</td></tr>"
        for item in missing
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
    ("#sync", "Do the layers agree"),
    ("#models", "The models"),
    ("#catalogue", "Every table"),
    ("#areas", "Areas"),
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
            _catalogue(result),
            _areas(result),
            _severity_mix(result),
            _funnel(result),
            _states(result),
            _rule_grid(result),
            _findings_by_area(result),
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
{_sync(result)}
{_alerts(result)}

<main><div class="wrap"><div class="grid">{panels}</div></div></main>

<footer><div class="wrap">
  <img src="{brand.logo_uri()}" alt="Rittman Analytics">
  <span>{esc(branding.attribution)}. Read from the repository, nothing written back.</span>
  <span class="meta">{esc(stamp)}</span>
</div></footer>
<script>{SEARCH_JS}</script>
</body>
</html>
"""
