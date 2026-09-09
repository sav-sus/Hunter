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
    the data flow     the DAG from raw sources through each layer to Looker
    the readiness     is each built table finished: described, owned, tested, in Looker
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
from hunter.config.register import RegisterModel
from hunter.emit import charts
from hunter.emit.charts import esc
from hunter.enums import (
    ALIGNMENT_STATE_LABELS,
    AlignmentState,
    BuildStatus,
    Persistence,
    PersistenceSignal,
    Presence,
)
from hunter.model.align import AlignmentRow
from hunter.model.entities import Model
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
  --shadow: 0 1px 2px rgba(21,29,45,0.06), 0 8px 24px rgba(21,29,45,0.06);
  --shadow-soft: 0 1px 2px rgba(21,29,45,0.05), 0 4px 12px rgba(21,29,45,0.05);
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

/* ---- coloured header bands, shared by the first cards and the checklist ---- */
.band {{
  --tone: {brand.PRIMARY};
  background: var(--tone); color: #fff; padding: 12px 20px; margin: -22px -24px 18px;
  border-radius: var(--radius) var(--radius) 0 0; display: flex; align-items: center;
  justify-content: space-between; gap: 12px; flex-wrap: wrap;
}}
.band h2 {{ margin: 0; font-size: 14px; font-weight: 700; letter-spacing: -0.01em; color: #fff; }}
.band-note {{ font-size: 12px; opacity: 0.8; }}

/* ---- the first card ---- */
.hero .band {{ display: block; padding: 22px 24px 20px; }}
.eyebrow {{
  margin: 0 0 8px; font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.12em;
  color: rgba(255,255,255,0.6); font-weight: 700; display: flex; gap: 10px; align-items: center;
}}
.eyebrow .client {{
  text-transform: none; letter-spacing: 0; font-weight: 600; color: #fff;
  background: rgba(255,255,255,0.12); padding: 2px 9px; border-radius: 6px; font-size: 12px;
}}
.hero h1 {{
  margin: 0 0 8px; font-size: 44px; line-height: 1; font-weight: 800; color: #fff;
  letter-spacing: -0.035em; font-family: {brand.MONO_STACK}; word-break: break-all;
}}
.stamp {{ margin: 0; color: rgba(255,255,255,0.6); font-size: 13px; }}
.hero-body {{
  display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 18px 44px;
  align-items: start; padding: 8px 0 4px;
}}
.hero-score {{
  display: flex; flex-direction: column; align-items: center; text-align: center;
  justify-content: center; gap: 4px; padding-right: 44px; border-right: 1px solid var(--border);
  align-self: stretch;
}}
.hero-ring {{ margin-bottom: 12px; }}
.hero-rest {{ min-width: 0; align-self: stretch; display: flex; flex-direction: column; }}
.hero-verdict {{ margin: 10px 0 6px; font-size: 17px; font-weight: 700; letter-spacing: -0.015em; }}
@media (max-width: 860px) {{
  .hero-body {{ grid-template-columns: 1fr; }}
  .hero-score {{
    padding-right: 0; border-right: 0; border-bottom: 1px solid var(--border);
    padding-bottom: 14px;
  }}
}}
.ring-value {{ font: 800 44px/1 {brand.FONT_STACK}; fill: var(--ink); letter-spacing: -0.03em; }}
.ring-label {{ font: 500 12px/1 {brand.FONT_STACK}; fill: #6b7280; }}
.ring-track {{ stroke: #eceef4; }}
.verdict {{ margin: 0; display: flex; align-items: center; justify-content: center; gap: 8px; }}
.grade {{
  font-weight: 700; font-size: 13px; padding: 4px 11px; border-radius: 6px; color: #fff;
  letter-spacing: 0.02em;
}}
.hero-sub {{ margin: 0; color: #6b7280; font-size: 12.5px; max-width: 30ch; line-height: 1.5; }}
.delta {{ font-size: 12.5px; font-weight: 600; padding: 4px 9px; border-radius: 6px; }}
.delta.up {{ background: {brand.GREEN_LIGHT}; color: #15803d; }}
.delta.down {{ background: {brand.PEACH_LIGHT}; color: #9f1d1d; }}
.delta.flat {{ background: var(--muted); color: #52525b; }}

/* the tiles */
.tiles {{
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); grid-auto-rows: 1fr;
  gap: 16px; flex: 1;
}}
@media (max-width: 860px) {{
  .tiles {{ grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); }}
}}
.tile {{
  display: flex; flex-direction: column; min-height: 118px;
  background: #fff; border: 1px solid rgba(21,29,45,0.06); border-radius: 12px;
  padding: 18px 18px 16px; box-shadow: var(--shadow-soft);
}}
.tile b {{
  display: block; font-size: 30px; font-weight: 800; letter-spacing: -0.03em; line-height: 1;
}}
.tile span {{
  display: block; font-size: 12.5px; color: #6b7280; margin-top: 8px; font-weight: 500;
  line-height: 1.4;
}}
.tile .bar {{
  display: block; height: 4px; border-radius: 2px; background: #eceef4; margin-top: auto;
  padding-top: 0; overflow: hidden;
}}
.tile span + .bar {{ margin-top: auto; }}
.tile span {{ margin-bottom: 16px; }}
.tile .bar u {{ display: block; height: 100%; text-decoration: none; }}
.tile.yes .bar u {{ background: #16a34a; }}
.tile.mostly .bar u {{ background: #d97706; }}
.tile.no .bar u {{ background: {brand.DESTRUCTIVE}; }}

/* the journey strip */
.journey {{
  grid-column: 1 / -1; margin-top: 6px; padding-top: 22px; border-top: 1px solid var(--border);
}}
.journey-title {{
  margin: 0 0 16px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.09em;
  color: #6b7280; font-weight: 700; display: flex; justify-content: space-between; gap: 12px;
  flex-wrap: wrap;
}}
.journey-title span {{ text-transform: none; letter-spacing: 0; font-weight: 500; color: #9aa1ad; }}
.journey-row {{
  display: flex; align-items: center; gap: 10px; flex-wrap: nowrap; overflow-x: auto;
  padding: 6px 0 10px;
}}
.stage {{ flex: 0 0 auto; min-width: 88px; }}
.stage b {{
  display: block; font-size: 30px; line-height: 1; font-weight: 800; letter-spacing: -0.03em;
}}
.stage span {{
  display: block; margin-top: 6px; font-size: 12px; color: #6b7280; font-weight: 500;
  max-width: 12ch; line-height: 1.3;
}}
.hop {{
  flex: 1 1 96px; min-width: 88px; position: relative; height: 46px;
  display: flex; align-items: flex-start; justify-content: center;
}}
.hop::before {{
  content: ""; position: absolute; left: 0; right: 10px; top: 38px; height: 2px;
  background: #16a34a;
}}
.hop::after {{
  content: ""; position: absolute; right: 4px; top: 33px; width: 0; height: 0;
  border-left: 8px solid #16a34a; border-top: 6px solid transparent;
  border-bottom: 6px solid transparent;
}}
.hop.loss::before {{ background: {brand.DESTRUCTIVE}; }}
.hop.loss::after {{ border-left-color: {brand.DESTRUCTIVE}; }}
.hop em {{
  font-style: normal; font-size: 10.5px; font-weight: 700; color: #9f1d1d;
  background: {brand.PEACH_LIGHT}; padding: 3px 7px; border-radius: 6px; position: relative;
  z-index: 1; max-width: calc(100% - 6px); text-align: center; line-height: 1.2;
}}
.hop em.none {{ color: #15803d; background: {brand.GREEN_LIGHT}; font-weight: 600; }}
@media (max-width: 720px) {{
  .hero h1 {{ font-size: 32px; }}
  .stage b {{ font-size: 28px; }}
}}

/* ---- cards ---- */
main {{ padding: 30px 0 12px; }}
.grid {{ display: grid; gap: 18px; grid-template-columns: repeat(12, 1fr); }}
.card {{
  background: #fff; border: 1px solid rgba(21,29,45,0.04); border-radius: var(--radius);
  padding: 22px 24px; grid-column: span 12; min-width: 0; box-shadow: var(--shadow);
}}
.card.half {{ grid-column: span 6; }}
.card.third {{ grid-column: span 4; }}
.card.two-thirds {{ grid-column: span 8; }}
@media (max-width: 940px) {{
  .card.half, .card.third, .card.two-thirds {{ grid-column: span 12; }}
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
tbody tr:hover td {{ background: #fafbfe; }}
td {{ padding: 11px 12px 11px 0; border-bottom: 1px solid #f1f2f6; vertical-align: top; }}
tr:last-child td {{ border-bottom: 0; }}
td.num {{ font-family: {brand.MONO_STACK}; font-weight: 700; white-space: nowrap; }}
.pill {{
  display: inline-block; font-size: 11px; font-weight: 700; padding: 3px 9px;
  border-radius: 6px; color: #fff; white-space: nowrap; letter-spacing: 0.01em;
}}
.chip {{
  display: inline-block; font-style: normal; font: 600 11px/1 {brand.FONT_STACK};
  padding: 4px 7px; border-radius: 5px; margin: 2px 4px 2px 0; white-space: nowrap;
}}
.chip.gap {{ background: {brand.PEACH_LIGHT}; color: #9f1d1d; }}
.chip.ready {{ background: {brand.GREEN_LIGHT}; color: #15803d; }}
.chip.grey {{ background: var(--muted); color: #52525b; }}
.chip.status-verified {{ background: {brand.GREEN_LIGHT}; color: #15803d; }}
.chip.status-permanent {{ background: {brand.BLUE_LIGHT}; color: #3730a3; }}
.chip.status-temporary {{ background: #fff1d6; color: #92400e; }}
.chip.status-not-determined {{ background: var(--muted); color: #52525b; }}

/* ---- roadmap ---- */
.lanes {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }}
.lane {{
  background: var(--muted); border-radius: 12px; padding: 12px;
  border-top: 3px solid var(--tone, {brand.MUTED_INK});
}}
.lane h3 {{
  display: flex; justify-content: space-between; align-items: baseline; gap: 8px;
  font-size: 13px; margin: 0 0 2px;
}}
.lane h3 b {{ font-family: {brand.MONO_STACK}; font-size: 15px; color: var(--tone, var(--ink)); }}
.lane .meaning {{ font-size: 11.5px; color: #6b7280; margin: 0 0 10px; line-height: 1.4; }}
.lane ul {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }}
.lane li {{
  background: #fff; border-radius: 8px; padding: 8px 10px; font-size: 12px;
  box-shadow: var(--shadow-soft);
}}
.lane li .tname {{ margin-bottom: 2px; }}
.lane li .objects {{ display: block; }}
.lane li .when {{ display: block; font-size: 11px; color: #6b7280; margin-top: 4px; }}
.lane .empty {{ margin: 0; font-size: 12px; color: #9ca3af; }}
.roadmap .finder {{ margin-bottom: 12px; }}
.tname {{
  --tone: {brand.PRIMARY};
  display: inline-block; font: 700 12.5px/1.2 {brand.MONO_STACK}; color: var(--ink);
  padding: 4px 8px; border-radius: 6px; background: var(--muted);
  border-left: 3px solid var(--tone); margin-bottom: 4px;
}}
td .objects {{ display: block; }}
.area-tabs {{ margin-bottom: 12px; }}
.area-tabs .tab {{ --tone: {brand.MUTED_INK}; }}
.area-tabs .tab .dot {{ width: 8px; height: 8px; margin-right: 6px; }}
.area-tabs .tab.on .dot {{ background: #fff; }}
code {{
  font-family: {brand.MONO_STACK}; font-size: 12px; background: var(--muted);
  padding: 1.5px 5px; border-radius: 4px;
}}
.objects {{ color: #6b7280; font-size: 12px; }}

/* ---- the checklist ---- */
.card.cl {{ --tone: {brand.PRIMARY}; padding: 0 16px 6px; }}
.card.cl .band {{ margin: 0 -16px 4px; }}
.cl ul {{ padding: 0; }}
.badge {{
  font-size: 10.5px; font-weight: 700; padding: 3px 8px; border-radius: 6px;
  white-space: nowrap; font-family: {brand.MONO_STACK}; letter-spacing: 0.03em;
}}
.badge.yes {{ background: rgba(255,255,255,0.92); color: #15803d; }}
.badge.mostly {{ background: rgba(255,255,255,0.92); color: #b45309; }}
.badge.no {{ background: rgba(255,255,255,0.92); color: #b91c1c; }}
.cl ul {{ list-style: none; margin: 0; }}
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
.cl li.yes .tick::before {{ content: "✓"; }}
.cl li.mostly .tick {{ background: #d97706; }}
.cl li.mostly .tick::before {{ content: "!"; }}
.cl li.no .tick {{ background: {brand.DESTRUCTIVE}; }}
.cl li.no .tick::before {{ content: "✗"; }}
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
  overflow: auto; max-height: 720px; border: 1px solid rgba(21,29,45,0.05); border-radius: 12px;
  background: #fafbfe; padding: 18px; box-shadow: inset 0 1px 3px rgba(21,29,45,0.04);
}}
.canvas pre.mermaid {{
  margin: 0; font: 12px/1.5 {brand.MONO_STACK}; color: #52525b; white-space: pre;
}}
.canvas pre.mermaid[data-processed] {{ font: inherit; color: inherit; }}
.canvas svg {{ display: block; height: auto; }}
.pane .heat-key {{ margin-top: 12px; }}
.pane .heat-key .swatch {{ width: 14px; height: 14px; border-radius: 3px; }}
.selector {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }}
.selector .select {{
  flex: 1 1 360px; min-width: 240px; font: 500 13.5px/1.4 {brand.MONO_STACK};
  padding: 9px 12px; border: 1px solid var(--border); border-radius: 9px; color: var(--ink);
}}
.selector .select:focus {{ outline: 2px solid var(--primary); outline-offset: -1px; }}
.selector .clear {{
  font: 600 13px/1 {brand.FONT_STACK}; color: var(--ink); background: #fff;
  border: 1px solid var(--border); border-radius: 7px; padding: 9px 12px; cursor: pointer;
}}
.selector .sel-help {{ flex: 1 1 100%; margin: 0; font-size: 12.5px; color: #6b7280; }}
.offline {{
  margin: 0 0 12px; padding: 10px 14px; border-radius: 9px; font-size: 13px;
  background: #fdebc8; color: #92400e;
}}

/* ---- modelling alignment ---- */
.align .finder {{ margin-bottom: 12px; }}
.align-stats {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; }}
.align-stats .stat {{
  display: flex; align-items: baseline; gap: 8px; padding: 8px 12px; border-radius: 10px;
  border: 1px solid rgba(21,29,45,0.05); background: #fff; font-size: 12.5px; color: #52525b;
  box-shadow: var(--shadow-soft);
}}
.align-stats .stat b {{
  font-size: 17px; letter-spacing: -0.02em; font-family: {brand.MONO_STACK};
}}
.align-stats .stat.yes b {{ color: #15803d; }}
.align-stats .stat.mostly b {{ color: #b45309; }}
.align-stats .stat.no b {{ color: {brand.DESTRUCTIVE}; }}
.align-head, .arow > summary {{ display: grid; align-items: center; column-gap: 0; }}
.align-head {{
  padding: 8px 10px; border-bottom: 1px solid var(--border); font-size: 11px;
  text-transform: uppercase; letter-spacing: 0.07em; color: #6b7280; font-weight: 700;
}}
.align-head .st {{ text-align: right; }}
.align-group {{
  --tone: {brand.MUTED_INK};
  display: flex; justify-content: space-between; align-items: baseline; gap: 12px;
  padding: 14px 10px 4px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.07em;
  color: var(--tone); font-weight: 700;
}}
.dot {{
  display: inline-block; width: 9px; height: 9px; border-radius: 3px; background: var(--tone);
  margin-right: 7px; vertical-align: 0;
}}
.align-group em {{ color: #9aa1ad; }}
.align-group em {{ font-style: normal; text-transform: none; letter-spacing: 0; font-weight: 500; }}
.arow {{ border-bottom: 1px solid #f1f2f6; position: relative; }}
.arow > summary {{
  padding: 7px 10px 7px 26px; cursor: pointer; list-style: none; position: relative;
}}
.arow > summary::-webkit-details-marker {{ display: none; }}
.arow > summary::before {{
  content: ""; position: absolute; left: 9px; top: 50%; width: 6px; height: 6px;
  border-right: 2px solid #9aa1ad; border-bottom: 2px solid #9aa1ad;
  transform: translateY(-60%) rotate(-45deg); transition: transform 0.15s;
}}
.arow > summary:hover {{ background: #fafbfe; }}
.arow[open] {{
  background: #f7f8fc; border-radius: 10px; border-bottom-color: transparent;
  box-shadow: inset 0 0 0 2px var(--primary); margin: 6px 0;
}}
.arow[open] > summary {{ border-bottom: 1px dashed #d3d7e0; }}
.arow[open] > summary::before {{
  transform: translateY(-30%) rotate(45deg); border-color: var(--primary);
}}
.cell {{
  display: block; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  padding: 6px 10px; border-radius: 6px; border: 1.5px solid var(--primary);
  font: 600 12px/1.2 {brand.MONO_STACK}; color: var(--ink); background: #fff;
}}
.cell.off {{
  border: 1.5px dashed #d3d7e0; color: #b0b6c2; font: 400 12px/1.2 {brand.FONT_STACK};
}}
.lane-link {{ display: block; height: 2px; margin: 0 4px; position: relative; }}
.lane-link::after {{
  content: ""; position: absolute; right: -1px; top: -3px; border-left: 6px solid;
  border-top: 4px solid transparent; border-bottom: 4px solid transparent;
}}
.lane-link.ok {{ background: #16a34a; }}
.lane-link.ok::after {{ border-left-color: #16a34a; }}
.lane-link.broken {{
  background: repeating-linear-gradient(90deg, {brand.DESTRUCTIVE} 0 5px, transparent 5px 9px);
}}
.lane-link.broken::after {{ border-left-color: {brand.DESTRUCTIVE}; }}
.lane-link.unplanned {{
  background: repeating-linear-gradient(90deg, #d97706 0 2px, transparent 2px 6px);
}}
.lane-link.unplanned::after {{ border-left-color: #d97706; }}
.lane-link.none {{ background: #e2e5ec; }}
.lane-link.none::after {{ display: none; }}
.arow .pill {{ justify-self: end; max-width: 100%; overflow: hidden; text-overflow: ellipsis; }}
.arow-detail {{ padding: 8px 26px 18px; font-size: 13.5px; }}
.arow-detail p {{ margin: 8px 0; max-width: 90ch; }}
.arow-detail dl {{
  display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px 22px;
  margin: 14px 0 0;
}}
.arow-detail dl > div {{ min-width: 0; }}
.arow-detail dt {{
  font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: #6b7280;
  font-weight: 700; white-space: nowrap;
}}
.arow-detail dd {{ margin: 3px 0 0; font-size: 13px; overflow-wrap: anywhere; }}

/* ---- the conceptual model as cards ---- */
.erd-group h4 em {{
  font-style: normal; text-transform: none; letter-spacing: 0; font-weight: 500; color: #9aa1ad;
  margin-left: 10px;
}}
.ents {{ display: flex; flex-wrap: wrap; gap: 12px; }}
.ent {{
  --state: {brand.MUTED_INK};
  min-width: 170px; background: #fff; border-radius: 10px; padding: 12px 14px 10px;
  border: 1px solid rgba(21,29,45,0.06); border-top: 4px solid var(--state);
  box-shadow: var(--shadow-soft); transition: opacity 0.15s;
}}
.ent b {{ display: block; font-size: 15px; font-weight: 700; letter-spacing: -0.01em; }}
.ent span {{
  display: block; font-size: 11.5px; color: var(--state); font-weight: 700; margin-top: 4px;
}}
.ent code {{ display: inline-block; margin-top: 8px; font-size: 11px; }}
.ent.dim {{ opacity: 0.18; }}
.ent.hit {{ box-shadow: 0 0 0 3px var(--primary); }}

/* ---- Mermaid drawings take the page's look ---- */
.canvas svg {{ font-family: {brand.FONT_STACK}; }}
.canvas svg .node rect, .canvas svg .node polygon {{ rx: 8; ry: 8; }}
.canvas svg .node .label {{ font-weight: 600; }}
.canvas svg .cluster rect {{
  rx: 12; ry: 12; fill: #fafbfe !important; stroke: #e2e5ec !important;
}}
.canvas svg .cluster-label, .canvas svg .cluster-label .nodeLabel {{
  font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em;
  color: #6b7280; fill: #6b7280;
}}
.canvas svg .edgePath path, .canvas svg .flowchart-link {{
  stroke: #9aa1ad !important; stroke-width: 1.5px;
}}
.canvas svg .marker {{ fill: #9aa1ad !important; stroke: #9aa1ad !important; }}

/* ---- the physical model as cards ---- */
.canvas.html {{ overflow: auto; position: relative; }}
.erd {{ position: relative; }}
.erd-lines {{
  position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none;
  overflow: visible;
}}
.erd-lines path {{ fill: none; stroke: #9aa1ad; stroke-width: 1.5; }}
.erd-lines circle {{ fill: #fff; stroke: #9aa1ad; stroke-width: 1.5; }}
.erd-lines line {{ stroke: #9aa1ad; stroke-width: 1.5; }}
.erd-group {{ margin-bottom: 22px; }}
.erd-group h4 {{
  margin: 0 0 10px; font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.08em;
}}
.erd-cards {{ display: flex; flex-wrap: wrap; gap: 26px 34px; align-items: flex-start; }}
.erd-card {{
  min-width: 260px; max-width: 360px; border-radius: 9px; overflow: hidden; background: #fff;
  box-shadow: 0 1px 2px rgba(21,29,45,0.08), 0 6px 18px rgba(21,29,45,0.06);
  border: 1px solid var(--border); transition: opacity 0.15s;
}}
.erd-card header {{ padding: 10px 14px; color: #fff; }}
.erd-card header b {{ display: block; font: 700 13px/1.2 {brand.MONO_STACK}; }}
.erd-card header .grain {{ display: block; font-size: 11.5px; opacity: 0.85; margin-top: 3px; }}
.erd-row {{
  display: flex; align-items: center; gap: 10px; padding: 7px 14px; font-size: 13px;
  border-top: 1px solid #f1f2f6;
}}
.erd-row:hover {{ background: #f7f8fc; }}
.erd-row .nm {{ flex: 1; font-family: {brand.MONO_STACK}; font-size: 12.5px; }}
.erd-row.pk .nm {{ font-weight: 700; }}
.erd-row .ty {{ color: #6b7280; font: 400 11.5px/1 {brand.MONO_STACK}; }}
.erd-row .bd em {{
  font-style: normal; font: 700 9.5px/1 {brand.FONT_STACK}; padding: 3px 5px; border-radius: 4px;
  margin-left: 3px; letter-spacing: 0.04em;
}}
.erd-row .bd .pk {{ background: #fdebc8; color: #92400e; }}
.erd-row .bd .fk {{ background: {brand.BLUE_LIGHT}; color: #3730a3; }}
.erd-row .bd .nn {{ background: var(--muted); color: #52525b; }}
.erd-card.dim, .canvas svg .dim {{ opacity: 0.18; }}
.erd-card.hit {{ box-shadow: 0 0 0 3px var(--primary); }}
.canvas svg g.hit rect, .canvas svg g.hit polygon, .canvas svg g.hit path.basic {{
  stroke: var(--primary) !important; stroke-width: 3px !important;
}}

/* ---- searchable catalogue ---- */
.finder {{
  display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 14px;
}}
.finder input {{
  flex: 1 1 260px; min-width: 200px; font: 400 14px/1.4 {brand.FONT_STACK};
  padding: 9px 12px; border: 1px solid var(--border); border-radius: 9px; color: var(--ink);
  background: #fff; box-shadow: inset 0 1px 2px rgba(21,29,45,0.04);
}}
.finder input:focus {{ outline: 2px solid var(--primary); outline-offset: -1px; }}
.finder .tally {{ font-size: 12.5px; color: #6b7280; font-family: {brand.MONO_STACK}; }}
.finder .toggle {{
  display: flex; align-items: center; gap: 6px; font-size: 13px; color: #52525b;
  white-space: nowrap;
}}
.finder .toggle input {{ flex: 0 0 auto; min-width: 0; width: 15px; height: 15px; margin: 0; }}
td.gaps {{ max-width: 34ch; }}
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


# --------------------------------------------------------------------- hero


@dataclass(frozen=True)
class Stage:
    """One step on the way from what was asked for to what people can use."""

    label: str
    count: int
    dropped: int = 0
    drop_label: str = ""


def journey(result: RunResult) -> list[Stage]:
    """The plan-to-reality path, one count per level Hunter could see.

    The levels are not strictly nested: a table can be built with no design
    behind it. So each drop is counted on its own terms and labelled in words,
    rather than read off as the difference between two neighbouring counts.
    """
    rows = result.alignment.rows
    project = result.project
    built = [row for row in rows if _in_repo(row)]
    stages: list[Stage] = []

    if project.has_conceptual:
        asked = [row for row in rows if row.conceptual is Presence.PRESENT]
        undesigned = sum(1 for row in asked if row.designed is not Presence.PRESENT)
        stages.append(Stage("Asked for by the business", len(asked), undesigned, "not designed"))
    if project.has_dbml:
        designed = [row for row in rows if row.designed is Presence.PRESENT]
        unbuilt = sum(1 for row in designed if not _in_repo(row))
        stages.append(Stage("Designed", len(designed), unbuilt, "not built"))

    introspected = project.droughty.introspected if project.droughty else {}
    live = {name.lower() for name in introspected}
    not_live = sum(1 for row in built if (row.model_name or "").lower() not in live)
    without_view = sum(1 for row in built if not project.views_for_model(row.model_name or ""))

    if live:
        stages.append(Stage("Built", len(built), not_live, "not live"))
        stages.append(
            Stage(
                "Live in the warehouse",
                len(built) - not_live,
                without_view if project.has_lookml else 0,
                "not in Looker",
            )
        )
    else:
        stages.append(
            Stage("Built", len(built), without_view if project.has_lookml else 0, "not in Looker")
        )
    if project.has_lookml:
        stages.append(Stage("Reachable in Looker", len(built) - without_view))
    return stages


def _journey(result: RunResult) -> str:
    stages = journey(result)
    if len(stages) < 2:
        return ""
    parts = []
    for index, stage in enumerate(stages):
        parts.append(
            f"<div class='stage'><b>{stage.count}</b><span>{esc(stage.label)}</span></div>"
        )
        if index + 1 < len(stages):
            drop = (
                f"<em>&minus;{stage.dropped} {esc(stage.drop_label)}</em>"
                if stage.dropped
                else "<em class='none'>all carried through</em>"
            )
            parts.append(f"<div class='hop{' loss' if stage.dropped else ''}'>{drop}</div>")
    return (
        "<div class='journey' id='journey'>"
        "<p class='journey-title'>From what the business asked for to what people can use"
        "<span>each drop counted on its own terms</span></p>"
        f"<div class='journey-row'>{''.join(parts)}</div>"
        "</div>"
    )


def _tile(value: str, label: str, part: int, whole: int, *, invert: bool = False) -> str:
    """One headline figure with a thin bar under it.

    ``invert`` is for counts where zero is the good answer, such as tables
    built with no design behind them.
    """
    share = 0.0 if whole <= 0 else max(0.0, min(1.0, part / whole))
    good = (1.0 - share) if invert else share
    tone = "yes" if good >= 0.999 else "mostly" if good >= 0.8 else "no"
    width = f"{share * 100:.1f}".rstrip("0").rstrip(".")
    return (
        f"<div class='tile {tone}'><b>{esc(value)}</b><span>{esc(label)}</span>"
        f"<i class='bar'><u style='width:{width}%'></u></i></div>"
    )


def _hero(result: RunResult, generated: dt.datetime) -> str:
    """The first card: whose repository, how healthy, and the four figures."""
    score = result.score
    branding = result.config.branding
    repo = result.meta.get("repo") or branding.site_name
    commit = result.meta.get("commit")
    rows = result.alignment.rows
    built = [row for row in rows if _in_repo(row)]
    sections = checklist(result)
    checks = [check for section in sections for check in section.checks]
    holding = sum(1 for check in checks if check.holds)

    delta_html = ""
    if score.delta is not None:
        direction = "up" if score.delta > 0 else "down" if score.delta < 0 else "flat"
        sign = "+" if score.delta > 0 else ""
        delta_html = f"<span class='delta {direction}'>{sign}{score.delta:g} since last time</span>"

    stamp = [f"Scored {generated.day} {generated:%B %Y}"]
    if commit:
        stamp.append(f"commit {esc(str(commit)[:8])}")
    stamp.append("read from the repository, nothing written back")

    tiles = [_tile(f"{holding} of {len(checks)}", "checks hold", holding, len(checks))]
    if result.project.has_conceptual:
        asked = [row for row in rows if row.conceptual is Presence.PRESENT]
        delivered = sum(1 for row in asked if _in_repo(row))
        tiles.append(
            _tile(f"{delivered} of {len(asked)}", "business entities built", delivered, len(asked))
        )
    if result.project.has_lookml:
        reachable = sum(1 for row in built if result.project.views_for_model(row.model_name or ""))
        tiles.append(
            _tile(
                f"{reachable} of {len(built)}",
                "built tables reachable in Looker",
                reachable,
                len(built),
            )
        )
    if result.project.has_dbml:
        off_plan = sum(1 for row in built if row.designed is not Presence.PRESENT)
        tiles.append(
            _tile(
                str(off_plan), "built with no design behind it", off_plan, len(built), invert=True
            )
        )

    client = (
        f"<span class='client'>{esc(branding.client_name)}</span>" if branding.client_name else ""
    )
    grade_colour = brand.grade_colour(score.grade)
    return f"""<section class="card hero" id="top">
  <header class="band" style="--tone:{brand.INK}">
    <p class="eyebrow">Analytics repository health {client}</p>
    <h1>{esc(repo)}</h1>
    <p class="stamp">{" &middot; ".join(stamp)}</p>
  </header>
  <div class="hero-body">
    <div class="hero-score">
      <div class="hero-ring">{charts.score_ring(score.total, score.grade)}</div>
      <p class="verdict"><span class="grade" style="background:{grade_colour}">
         Grade {esc(score.grade)}</span>{delta_html}</p>
      <p class="hero-verdict">{esc(score.interpretation)}</p>
      <p class="hero-sub">{len(built)} built tables, {len(rows)} entities tracked,
         {len(checks)} statements checked.</p>
    </div>
    <div class="hero-rest">
      <div class="tiles">{"".join(tiles)}</div>
    </div>
    {_journey(result)}
  </div>
</section>"""


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
    for index, section in enumerate(sections):
        colour = ERD_PALETTE[index % len(ERD_PALETTE)]
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
        ident = " id='checklist'" if index == 0 else ""
        cards.append(
            f"<section class='card third cl'{ident} style='--tone:{colour}'>"
            f"<header class='band'><h2>{esc(section.title)}</h2>"
            f"<span class='badge {tone}'>{section.passed} of {total} hold</span></header>"
            f"<ul>{''.join(items)}</ul></section>"
        )
    return "".join(cards)


# ------------------------------------------------------------------- panels


#: The chain, in the order a table travels along it. Each entry is the lane
#: heading, the attribute on an alignment row, and the source that has to have
#: been read for the lane to mean anything.
LANES: tuple[tuple[str, str, str], ...] = (
    ("Conceptual · the business model", "conceptual", "conceptual"),
    ("Logical · the data flow", "logical", "logical"),
    ("Physical · the DBML design", "designed", "dbml"),
    ("Built · in the repository", "repo", "manifest"),
)

#: What to do about an entity in each state, in one sentence. This is the
#: column a product owner reads: the state says where it stands, this says who
#: moves it.
NEXT_STEP: dict[AlignmentState, str] = {
    AlignmentState.DESIGNED_AND_DELIVERED: "Nothing. It is where it should be.",
    AlignmentState.BUILT_NOT_DEPLOYED: "Deploy it, or record why it is waiting.",
    AlignmentState.BUILT_DISABLED: (
        "Switch it on or remove it. Code that is kept but switched off still costs "
        "review time and delivers nothing."
    ),
    AlignmentState.DESIGNED_NOT_STARTED: (
        "Build it, or take it off the design if it is no longer wanted."
    ),
    AlignmentState.LIVE_WITHOUT_CODE: (
        "Find out what produces it, then bring it into the repository or retire it."
    ),
    AlignmentState.BUILT_OFF_PLAN: (
        "Write the design entry, or approve it in the register with a reason and a review date."
    ),
    AlignmentState.APPROVED_OFF_PLAN: (
        "Accepted for now. The design entry is still owed by the review date."
    ),
    AlignmentState.OFF_PLAN_NOT_DEPLOYED: (
        "Decide whether it is wanted before it reaches production."
    ),
    AlignmentState.UNTRACKED_TABLE: (
        "Nobody here owns it. Claim it or drop it from the warehouse."
    ),
    AlignmentState.CONCEPTUAL_ONLY: (
        "Design it, or agree with the business that it is not needed yet."
    ),
    AlignmentState.LOGICAL_ONLY: (
        "It is on the data flow diagram alone. Add it to the business model and the design, "
        "or take it off the diagram."
    ),
    AlignmentState.NOT_PRESENT: "Nothing to do.",
}

#: Pill colour per state, shared by the alignment rows and the catalogue.
STATE_TONE: dict[AlignmentState, str] = {
    AlignmentState.DESIGNED_AND_DELIVERED: "#16a34a",
    AlignmentState.BUILT_NOT_DEPLOYED: brand.SKY,
    AlignmentState.BUILT_DISABLED: brand.MUTED_INK,
    AlignmentState.APPROVED_OFF_PLAN: brand.ACCENT,
    AlignmentState.BUILT_OFF_PLAN: brand.PEACH,
    AlignmentState.OFF_PLAN_NOT_DEPLOYED: brand.PEACH,
    AlignmentState.LIVE_WITHOUT_CODE: brand.DESTRUCTIVE,
    AlignmentState.UNTRACKED_TABLE: brand.DESTRUCTIVE,
    AlignmentState.DESIGNED_NOT_STARTED: "#d97706",
    AlignmentState.CONCEPTUAL_ONLY: brand.PRIMARY,
    AlignmentState.LOGICAL_ONLY: brand.BLUE_LIGHT,
    AlignmentState.NOT_PRESENT: brand.MUTED_INK,
}

#: Lane pairs and the words for a break between them, left to right.
LANE_NAMES = {
    "conceptual": lambda row: row.label,
    "logical": lambda row: row.label,
    "designed": lambda row: row.designed_name or row.key,
    "repo": lambda row: row.model_name or row.key,
}


def _link_class(left: bool, right: bool) -> str:
    if left and right:
        return "lane-link ok"
    if left:
        return "lane-link broken"
    if right:
        return "lane-link unplanned"
    return "lane-link none"


def _alignment_stats(result: RunResult, lanes: list[tuple[str, str, str]]) -> str:
    """The headline reading of the alignment card, as a handful of chips."""
    rows = result.alignment.rows
    project = result.project
    chips: list[tuple[str, str, str]] = []
    if project.has_conceptual:
        asked = [row for row in rows if row.conceptual is Presence.PRESENT]
        through = sum(1 for row in asked if _in_repo(row))
        tone = "yes" if through == len(asked) else "mostly" if through >= 0.8 * len(asked) else "no"
        chips.append((f"{through} of {len(asked)}", "asked for and now in the repository", tone))
    counts = result.alignment.state_counts()
    bad = [
        (AlignmentState.BUILT_OFF_PLAN, "built with no design"),
        (AlignmentState.CONCEPTUAL_ONLY, "asked for, never designed"),
        (AlignmentState.DESIGNED_NOT_STARTED, "designed, not started"),
        (AlignmentState.BUILT_DISABLED, "built, switched off"),
        (AlignmentState.LOGICAL_ONLY, "on the flow diagram only"),
        (AlignmentState.LIVE_WITHOUT_CODE, "live without code"),
    ]
    for state, label in bad:
        if counts.get(state):
            chips.append((str(counts[state]), label, "no"))
    stale = len(result.alignment.stale_claims())
    if stale:
        chips.append((str(stale), "diagram colours out of date", "no"))
    if not chips:
        return ""
    return (
        "<div class='align-stats'>"
        + "".join(
            f"<div class='stat {tone}'><b>{esc(value)}</b><span>{esc(label)}</span></div>"
            for value, label, tone in chips
        )
        + "</div>"
    )


def _alignment_detail(result: RunResult, row: AlignmentRow) -> str:
    """What one entity's row opens to: meaning, next step, and the facts."""
    project = result.project
    facts: list[tuple[str, str]] = [("Owner", row.owner or "nobody named")]
    if row.grain:
        facts.append(("One row is", row.grain))
    if row.model_name:
        views = project.views_for_model(row.model_name)
        facts.append(("Looker views", ", ".join(view.name for view in views) if views else "none"))
        introspected = project.droughty.introspected if project.droughty else {}
        if introspected:
            live = {name.lower() for name in introspected}
            facts.append(("In the warehouse", "yes" if row.model_name.lower() in live else "no"))
    if row.design_file:
        facts.append(("Designed in", row.design_file))
    if row.claimed_status:
        verdict = "agrees" if row.claim_matches_reality else "disagrees"
        facts.append(
            ("Diagram says", f"{row.claimed_status}, which {verdict} with what Hunter found")
        )
    for note in row.notes:
        facts.append(("Note", note))
    dl = "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in facts)
    return (
        "<div class='arow-detail'>"
        f"<p><b>Where it stands.</b> {esc(row.state_meaning)}</p>"
        f"<p><b>Do next.</b> {esc(NEXT_STEP[row.state])}</p>"
        f"<dl>{dl}</dl></div>"
    )


def _alignment(result: RunResult) -> str:
    """The business, logical and physical models against what is built.

    One row per entity, one column per level. A filled cell means the entity
    exists at that level. The connector between two columns is the answer to
    "does this level agree with the next": green where both exist, red where the
    left exists and the right does not, amber the other way round. Every row
    opens to what the state means and what to do about it.
    """
    available = {
        "conceptual": result.project.has_conceptual,
        "logical": any(row.logical is not Presence.UNKNOWN for row in result.alignment.rows),
        "dbml": result.project.has_dbml,
        "manifest": result.project.has_manifest,
    }
    lanes = [lane for lane in LANES if available.get(lane[2])]
    if len(lanes) < 2:
        return ""

    columns = " 34px ".join("minmax(0, 1fr)" for _ in lanes) + " 190px"
    grid = f"style='grid-template-columns:{columns}'"
    head_cells = []
    for index, (heading, _, _) in enumerate(lanes):
        head_cells.append(f"<span>{esc(heading)}</span>")
        if index + 1 < len(lanes):
            head_cells.append("<i></i>")
    head_cells.append("<span class='st'>Where it stands</span>")
    head = f"<div class='align-head' {grid}>{''.join(head_cells)}</div>"

    body: list[str] = []
    last_group: str | None = None
    grouped = result.alignment.by_domain()
    show_groups = len(grouped) > 1
    tones = _area_tones(result)
    for row in result.alignment.rows:
        group = row.domain or "ungrouped"
        if show_groups and group != last_group:
            last_group = group
            members = grouped[group]
            done = sum(1 for item in members if item.state is AlignmentState.DESIGNED_AND_DELIVERED)
            tone = tones.get(group, brand.MUTED_INK)
            body.append(
                f"<div class='align-group' data-group='{esc(group)}' style='--tone:{tone}'>"
                f"<span><i class='dot'></i>{esc(group.replace('_', ' '))}</span>"
                f"<em>{done} of {len(members)} designed and delivered</em></div>"
            )
        cells: list[str] = []
        present = [getattr(row, attr) is Presence.PRESENT for _, attr, _ in lanes]
        searchable = {row.label, row.state_label, group.replace("_", " "), row.owner or ""}
        for index, (_, attr, _) in enumerate(lanes):
            name = LANE_NAMES[attr](row)
            if present[index]:
                searchable.add(name)
                cells.append(f"<span class='cell on'>{esc(name)}</span>")
            else:
                cells.append("<span class='cell off'>not here</span>")
            if index + 1 < len(lanes):
                cells.append(f"<i class='{_link_class(present[index], present[index + 1])}'></i>")
        cells.append(
            f"<span class='pill' style='background:{STATE_TONE[row.state]}'>"
            f"{esc(row.state_label)}</span>"
        )
        find = " ".join(sorted(part for part in searchable if part)).lower()
        body.append(
            f"<details class='arow' data-group='{esc(group)}' data-find=\"{esc(find)}\">"
            f"<summary {grid}>{''.join(cells)}</summary>"
            f"{_alignment_detail(result, row)}</details>"
        )

    finder = (
        "<div class='finder'>"
        "<input type='search' class='find' autocomplete='off'"
        " placeholder='Find an entity, table, area, owner or state'"
        " aria-label='Find in the alignment'>"
        f"<span class='tally'>{len(result.alignment.rows)} entities</span>"
        "</div>"
    )
    return _card(
        "Modelling alignment",
        "The conceptual, logical and physical models against what is built. Read "
        "across one band to follow a single table; open a row for what to do about it.",
        f"<div class='align'>{finder}{_alignment_stats(result, lanes)}{head}{''.join(body)}"
        "<p class='empty' hidden>Nothing matches that.</p></div>",
        foot=(
            "Green means the two levels agree. Red is a break: the level on the left "
            "has it, the level on the right does not. Amber is the other way round, "
            "something built that the level above never asked for."
        ),
        anchor="alignment",
    )


#: The library that draws the model diagrams, pinned to one version so the same
#: source renders the same way next year. This is the only thing on the page
#: fetched from anywhere. Without it the diagram source is shown as text and
#: everything else on the page is unaffected.
#: The diagram renderer is bundled into the page from the package, so the file
#: has no external reference at all. brand.mermaid_js() checks the pinned build.
MERMAID_VERSION = brand.MERMAID_VERSION

#: The model diagrams, in the order a stakeholder reads them.
DIAGRAMS: tuple[tuple[str, str, str], ...] = (
    (
        "conceptual",
        "Conceptual",
        "What the business asked for, in its own words, by area. Under each entity is "
        "where it stands; hover for what that means.",
    ),
    (
        "logical",
        "Logical",
        "The data flow diagram as the team drew it: where data comes from, which "
        "entities it becomes, and what reads them. Colour is Hunter's, from the "
        "same states as the conceptual model.",
    ),
    (
        "physical",
        "Physical",
        "The designed tables from the DBML, by area. Under each name is what one row "
        "means; hover a table for what it is for, and a column for its note. Lines "
        "join a foreign key to the key it points at.",
    ),
)


def _swatch(style: str) -> str:
    """An HTML swatch for a Mermaid style string such as ``fill:#x,stroke:#y``."""
    parts = dict(item.split(":", 1) for item in style.split(",") if ":" in item)
    fill = parts.get("fill", "#fff")
    stroke = parts.get("stroke", "#999")
    dashed = "dashed" if "stroke-dasharray" in parts else "solid"
    return (
        f"<i class='swatch' style='background:{esc(fill)};border:1.5px {dashed} {esc(stroke)}'></i>"
    )


def _diagram_legend(result: RunResult, *, furniture: bool = False) -> str:
    """The colour key, as HTML under the canvas rather than drawn in the diagram.

    Drawn inside the diagram it read as one more area. Here it is plainly a key.
    """
    from hunter.emit import mermaid

    states = sorted(result.alignment.state_counts(), key=lambda state: state.value)
    items = [
        f"<span>{_swatch(mermaid.STATE_STYLE[state])}{esc(ALIGNMENT_STATE_LABELS[state])}</span>"
        for state in states
    ]
    if furniture:
        items.append(f"<span>{_swatch(mermaid.STYLE_SOURCE)}data source</span>")
        dashboard = _swatch(mermaid.LOGICAL_FURNITURE_STYLE["dashboard__"])
        items.append(f"<span>{dashboard}report or dashboard</span>")
    if not items:
        return ""
    return f"<div class='heat-key'>{''.join(items)}</div>"


@dataclass(frozen=True)
class Pane:
    """One tab in a tabbed card: a key, a label, one line of context, source."""

    key: str
    label: str
    blurb: str
    source: str
    extra: str = ""
    #: Ready-made HTML for the canvas instead of Mermaid source. The physical
    #: model uses this: it needs no library, so it draws offline too.
    html: str = ""


def _tabbed(
    anchor: str,
    title: str,
    sub: str,
    panes: list[Pane],
    *,
    tools: str = "",
    find: str = "",
) -> str:
    """A card whose body is a set of Mermaid diagrams behind tabs.

    Every diagram's source is in the HTML. The script draws a tab the first
    time it is opened, because the library measures text and a hidden element
    measures as nothing. If the library never arrives, the source stays visible
    as text and a note says so.
    """
    if not panes:
        return ""
    tabs_hidden = " hidden" if len(panes) == 1 else ""
    tabs = "".join(
        f"<button type='button' class='tab{' on' if index == 0 else ''}' "
        f"data-pane='{esc(pane.key)}' aria-selected='{'true' if index == 0 else 'false'}'>"
        f"{esc(pane.label)}</button>"
        for index, pane in enumerate(panes)
    )
    body = "".join(
        f"<div class='pane' data-key='{esc(pane.key)}'{'' if index == 0 else ' hidden'}>"
        f"<p class='blurb'>{esc(pane.blurb)}</p>"
        + (
            f"<div class='canvas html'>{pane.html}</div>"
            if pane.html
            else f"<div class='canvas'><pre class='mermaid'>{esc(pane.source.strip())}</pre></div>"
        )
        + f"{pane.extra}</div>"
        for index, pane in enumerate(panes)
    )
    if find:
        tools = (
            "<div class='finder'>"
            f"<input type='search' class='find' autocomplete='off' placeholder='{esc(find)}'"
            " aria-label='Find in this diagram'><span class='tally find-tally'></span></div>"
        ) + tools
    controls = (
        "<div class='zoom' hidden>"
        "<button type='button' data-zoom='out' aria-label='Zoom out'>&minus;</button>"
        "<button type='button' data-zoom='reset'>Fit</button>"
        "<button type='button' data-zoom='in' aria-label='Zoom in'>+</button>"
        "</div>"
    )
    offline = (
        "<noscript><p class='offline'>Scripting is switched off in this browser, so the "
        "diagram source is shown as text rather than drawn.</p></noscript>"
        "<p class='offline' hidden>The bundled diagram library did not start in this "
        "browser, so the diagram source is shown as text rather than drawn.</p>"
    )
    return _card(
        title,
        sub,
        f"<div class='tabbed'><div class='tabs' role='tablist'{tabs_hidden}>{tabs}{controls}</div>"
        f"{tools}{offline}{body}</div>",
        anchor=anchor,
    )


def _empty_diagram(source: str) -> bool:
    return source.strip() in ("", "erDiagram", "flowchart TB", "flowchart LR")


#: Colours for areas and sections, cycling. The same area gets the same colour
#: on the physical model, the alignment card and the readiness table, so a
#: reader learns it once.
ERD_PALETTE = (brand.PRIMARY, "#2f6690", "#7c5cbf", "#0f766e", "#b45309", "#9f1239")


def _area_tones(result: RunResult) -> dict[str, str]:
    """Area name to colour, in a stable order."""
    prefixes = tuple(layer.prefix for layer in result.config.layers if layer.prefix)

    def plain(name: str) -> str:
        for prefix in prefixes:
            if name.startswith(prefix):
                return name[len(prefix) :] or name
        return name

    areas = {plain(row.domain) for row in result.alignment.rows if row.domain}
    areas |= {plain(entity.domain) for entity in result.project.designed.values() if entity.domain}
    return {area: ERD_PALETTE[index % len(ERD_PALETTE)] for index, area in enumerate(sorted(areas))}


def _column_role(column: object) -> str:
    name = str(getattr(column, "name", "")).lower()
    if getattr(column, "is_primary_key", False):
        return "pk"
    if name.endswith("_fk"):
        return "fk"
    if name.endswith(("_dt", "_ts")):
        return "date"
    return "attr"


def _conceptual_cards(result: RunResult) -> str:
    """The business model as entity cards, one section per area, coloured by state.

    What the business asked for, in its own words, with where each thing stands
    written under it. Needs no library, so it draws offline.
    """
    rows = [row for row in result.alignment.rows if row.conceptual is Presence.PRESENT]
    if not rows:
        return ""
    tones = _area_tones(result)
    grouped: dict[str, list[AlignmentRow]] = {}
    for row in rows:
        grouped.setdefault(row.domain or "ungrouped", []).append(row)
    groups = []
    for area, members in sorted(grouped.items()):
        colour = tones.get(area, brand.MUTED_INK)
        cards = "".join(
            f"<div class='ent' style='--state:{STATE_TONE[row.state]}'"
            f' data-find="{esc(row.label.lower())} {esc(row.state_label.lower())}"'
            f" title='{esc(row.state_meaning)}'>"
            f"<b>{esc(row.label)}</b><span>{esc(row.state_label)}</span>"
            + (f"<code>{esc(row.technical_name)}</code>" if row.technical_name else "")
            + "</div>"
            for row in sorted(members, key=lambda item: item.label)
        )
        done = sum(1 for row in members if row.state is AlignmentState.DESIGNED_AND_DELIVERED)
        groups.append(
            f"<section class='erd-group'><h4 style='color:{colour}'><i class='dot'"
            f" style='--tone:{colour}'></i>{esc(area.replace('_', ' '))}"
            f"<em>{done} of {len(members)} designed and delivered</em></h4>"
            f"<div class='ents'>{cards}</div></section>"
        )
    return f"<div class='concept'>{''.join(groups)}</div>"


def _physical_erd(result: RunResult) -> str:
    """The DBML design as table cards, grouped by area, relationships drawn.

    Each card carries the table name, what one row means, and its columns with
    type and key badges. The description sits behind a hover, as does each
    column's note, so the picture stays a picture. Relationship lines are drawn
    by the page once the cards have a position; without scripting the cards
    still show and each foreign key names what it points at.
    """
    from hunter.emit.mermaid import describe

    project = result.project
    if not project.designed:
        return ""
    by_domain: dict[str, list] = {}
    for entity in sorted(project.designed.values(), key=lambda item: item.name):
        by_domain.setdefault(entity.domain or "ungrouped", []).append(entity)
    grains = {row.designed_name: row.grain for row in result.alignment.rows if row.designed_name}
    refs: dict[tuple[str, str], tuple[str, str]] = {}
    for ref in project.designed_refs:
        for from_col, to_col in zip(ref.from_columns, ref.to_columns or [""], strict=False):
            refs[(ref.from_table, from_col)] = (ref.to_table, to_col)

    prefixes = tuple(layer.prefix for layer in result.config.layers if layer.prefix)

    def area(name: str) -> str:
        for prefix in prefixes:
            if name.startswith(prefix):
                return name[len(prefix) :] or name
        return name

    tones = _area_tones(result)
    groups = []
    for domain, entities in sorted(by_domain.items()):
        colour = tones.get(area(domain), brand.MUTED_INK)
        cards = []
        for entity in entities:
            grain = grains.get(entity.name) or entity.grain_note or ""
            about = describe(entity.note, limit=400)
            rows = []
            for column in entity.columns:
                role = _column_role(column)
                target = refs.get((entity.name, column.name))
                ref_attr = f" data-ref='{esc(target[0])}.{esc(target[1])}'" if target else ""
                badges = []
                if role == "pk":
                    badges.append("<em class='pk'>PK</em>")
                if role == "fk" or target:
                    badges.append("<em class='fk'>FK</em>")
                if getattr(column, "is_not_null", False) and role != "pk":
                    badges.append("<em class='nn'>NN</em>")
                note = column.note or ""
                if target:
                    note = f"{note} Points at {target[0]}.{target[1]}.".strip()
                rows.append(
                    f"<div class='erd-row {role}' data-col='{esc(column.name)}'{ref_attr}"
                    f" title='{esc(note)}'>"
                    f"<span class='nm'>{esc(column.name)}</span>"
                    f"<span class='ty'>{esc(column.data_type or '')}</span>"
                    f"<span class='bd'>{''.join(badges)}</span></div>"
                )
            cards.append(
                f"<div class='erd-card' data-table='{esc(entity.name)}'"
                f' data-find="{esc(entity.name.lower())}">'
                f"<header style='background:{colour}' title='{esc(about)}'>"
                f"<b>{esc(entity.name)}</b>"
                + (f"<span class='grain'>{esc(grain)}</span>" if grain else "")
                + f"</header>{''.join(rows)}</div>"
            )
        groups.append(
            f"<section class='erd-group'><h4 style='color:{colour}'>"
            f"{esc(area(domain).replace('_', ' '))}</h4>"
            f"<div class='erd-cards'>{''.join(cards)}</div></section>"
        )
    return (
        "<div class='erd'><svg class='erd-lines' aria-hidden='true'></svg>"
        + "".join(groups)
        + "</div>"
    )


def _diagrams(result: RunResult) -> str:
    """The models as diagrams a stakeholder can switch between, search and zoom."""
    from hunter.emit import mermaid

    alignment = result.alignment
    panes: list[Pane] = []
    conceptual = _conceptual_cards(result)
    if conceptual:
        key, label, blurb = DIAGRAMS[0]
        panes.append(Pane(key, label, blurb, "", extra=_diagram_legend(result), html=conceptual))
    logical = mermaid.decorate_logical(result.logical_source, alignment)
    if not _empty_diagram(logical):
        key, label, blurb = DIAGRAMS[1]
        panes.append(
            Pane(key, label, blurb, logical, extra=_diagram_legend(result, furniture=True))
        )
    physical = _physical_erd(result)
    if physical:
        key, label, blurb = DIAGRAMS[-1]
        panes.append(Pane(key, label, blurb, "", html=physical))
    return _tabbed(
        "diagrams",
        "Model diagrams",
        "Conceptual is what the business asked for, logical is how data flows, "
        "physical is the designed tables. Type to find something; use the buttons to zoom.",
        panes,
        find="Find a table or entity in this diagram",
    )


#: How many areas get a tab of their own on the data flow card.
DAG_TAB_LIMIT = 8


def _dag(result: RunResult) -> str:
    """The path data takes, from raw sources through every layer to Looker.

    Each pane carries the DAG as JSON as well as drawn, so the selector can
    redraw a subset in the browser using dbt's own selection syntax.
    """
    from hunter.emit import mermaid

    project, graph, alignment = result.project, result.graph, result.alignment
    if not project.models:
        return ""
    # Areas are the business areas the alignment knows, not every prefix a
    # model name carries: staging models are named for their source system.
    domains = sorted({row.domain for row in alignment.rows if row.domain})
    specs: list[tuple[str, str, mermaid.PipelineSpec]] = []
    if len(domains) != 1:
        specs.append(("all", "All areas", mermaid.pipeline_spec(project, graph, alignment)))
    for domain in domains[:DAG_TAB_LIMIT]:
        specs.append(
            (
                f"dag-{domain}",
                domain.replace("_", " "),
                mermaid.pipeline_spec(project, graph, alignment, domain=domain),
            )
        )
    blurb = (
        "Raw sources on the left, then each layer, then the Looker views and the "
        "explores people open. Red: built with no design. Amber dashed: nothing tests "
        "it. Grey rounded: a temporary working step."
    )
    panes = [
        Pane(
            key,
            label,
            blurb,
            mermaid.render_pipeline(spec),
            extra=f"<script type='application/json' class='dag-spec'>{spec.to_json()}</script>",
        )
        for key, label, spec in specs
        if spec.nodes
    ]
    names = sorted(
        {node.label for _, _, spec in specs for node in spec.nodes if node.kind == "model"}
    )
    options = "".join(f"<option value='{esc(name)}'>" for name in names)
    selector = (
        "<div class='selector' hidden>"
        "<input type='text' list='dag-names' class='select' autocomplete='off' spellcheck='false'"
        " placeholder='Select tables the dbt way: +name+  2+name  name+1'"
        " aria-label='Select tables'>"
        "<button type='button' class='clear'>Clear</button>"
        "<span class='tally sel-tally'></span>"
        f"<datalist id='dag-names'>{options}</datalist>"
        "<p class='sel-help'>+name shows everything that feeds it, name+ everything that "
        "reads from it, +name+ both. A number limits the steps: 1+name is direct parents "
        "only. * matches many names.</p>"
        "</div>"
    )
    sub = "How data moves through the repository, area by area. Type a table name to follow it."
    if len(domains) > DAG_TAB_LIMIT:
        rest = len(domains) - DAG_TAB_LIMIT
        sub += f" {rest} smaller areas are on the lineage page of the full report."
    return _tabbed("dag", "Data flow", sub, panes, tools=selector)


#: What one cell in the readiness table can say. "partial" is some but not
#: all; "unknown" is a level Hunter had no source for.
MARKS: dict[str, tuple[str, str, str]] = {
    "yes": ("yes", "&#10003;", "yes"),
    "no": ("no", "&#10007;", "no"),
    "partial": ("off", "&#9679;", "partly"),
    "unknown": ("dash", "&#8211;", "Hunter had nothing to read"),
}


# ------------------------------------------------------------------ roadmap


def _status_note(model: Model | None, entry: RegisterModel | None) -> str:
    """Where a status came from, in words a reader can check."""
    if model is None:
        return ""
    if model.persistence_signal is PersistenceSignal.REGISTER and entry is not None:
        if model.persistence is Persistence.VERIFIED and entry.verified_by:
            when = (
                f" on {entry.verified_on.day} {entry.verified_on:%B %Y}"
                if entry.verified_on
                else ""
            )
            return f"verified by {entry.verified_by}{when}"
        if entry.review_by:
            return (
                f"declared in the register, review by {entry.review_by.day} {entry.review_by:%B %Y}"
            )
        return "declared in the register"
    return "worked out from the " + str(model.persistence_signal).replace("_", " ")


def _status_chip(status: str, note: str = "") -> str:
    klass = status.replace(" ", "-")
    title = f" title='{esc(note)}'" if note else ""
    return f"<em class='chip status-{klass}'{title}>{esc(status)}</em>"


@dataclass(frozen=True)
class RoadmapItem:
    """One entity on the roadmap: where it is, who owns it, what happens next."""

    label: str
    technical_name: str | None
    owner: str | None
    status: str
    state_label: str
    next_step: str
    domain: str

    @property
    def searchable(self) -> str:
        parts = [self.label, self.technical_name or "", self.owner or "", self.status, self.domain]
        return " ".join(part for part in parts if part).lower()


@dataclass(frozen=True)
class Lane:
    """One column of the roadmap."""

    key: str
    title: str
    meaning: str
    tone: str
    items: tuple[RoadmapItem, ...]


ROADMAP_LANES: tuple[tuple[str, str, str, str], ...] = (
    ("planned", "Planned", "Agreed with the business or designed. No code yet.", brand.MUTED_INK),
    ("building", "Being built", "Code exists but is switched off or not yet live.", "#d97706"),
    (
        "live",
        "Live",
        "Built and in use. The chip says whether it is confirmed to stay.",
        "#16a34a",
    ),
    (
        "temporary",
        "Temporary by design",
        "Working steps and one-off tables. Each carries a review date so none becomes "
        "permanent by accident.",
        "#b45309",
    ),
    (
        "phasing_out",
        "Being phased out",
        "Marked deprecated in the register. Still running until its review date.",
        brand.PEACH,
    ),
    (
        "retired",
        "Retired",
        "Declared retired. Kept on the roadmap so the history is visible.",
        "#6b7280",
    ),
)

_STATUS_LANE: dict[BuildStatus, str] = {
    BuildStatus.PLANNED: "planned",
    BuildStatus.BUILDING: "building",
    BuildStatus.LIVE: "live",
    BuildStatus.DEPRECATED: "phasing_out",
    BuildStatus.RETIRED: "retired",
}

_STATE_LANE: dict[AlignmentState, str | None] = {
    AlignmentState.CONCEPTUAL_ONLY: "planned",
    AlignmentState.LOGICAL_ONLY: "planned",
    AlignmentState.DESIGNED_NOT_STARTED: "planned",
    AlignmentState.BUILT_NOT_DEPLOYED: "building",
    AlignmentState.BUILT_DISABLED: "building",
    AlignmentState.OFF_PLAN_NOT_DEPLOYED: "building",
    AlignmentState.DESIGNED_AND_DELIVERED: "live",
    AlignmentState.BUILT_OFF_PLAN: "live",
    AlignmentState.APPROVED_OFF_PLAN: "live",
    AlignmentState.LIVE_WITHOUT_CODE: "live",
    AlignmentState.UNTRACKED_TABLE: "live",
    AlignmentState.NOT_PRESENT: None,
}


def _lane_for(row: AlignmentRow, entry: RegisterModel | None, model: Model | None) -> str | None:
    """A person's declaration first, then the table's own status, then the chain."""
    if entry is not None and entry.status is not None:
        return _STATUS_LANE[entry.status]
    if (
        model is not None
        and model.persistence is Persistence.TEMPORARY
        and model.persistence_signal is PersistenceSignal.REGISTER
    ):
        return "temporary"
    return _STATE_LANE[row.state]


def _when(date: dt.date | None) -> str:
    return f"{date.day} {date:%B %Y}" if date else ""


def _next_step(
    lane: str, row: AlignmentRow, entry: RegisterModel | None, model: Model | None
) -> str:
    """What happens next, from the register where it says, otherwise from the chain."""
    review = _when(entry.review_by) if entry and entry.review_by else ""
    if lane == "temporary":
        return f"review by {review}" if review else "no review date set"
    if lane == "phasing_out":
        return f"review by {review}" if review else "no end date recorded"
    if lane == "planned":
        if row.state is AlignmentState.DESIGNED_NOT_STARTED:
            return "designed, waiting to be built"
        return "agreed, not designed yet"
    if lane == "building":
        if row.state is AlignmentState.BUILT_DISABLED:
            return "switched off by a project variable"
        return "built, not yet in production"
    if lane == "live":
        if model is not None and model.persistence is Persistence.VERIFIED:
            return _status_note(model, entry)
        if row.state is AlignmentState.APPROVED_OFF_PLAN:
            return f"approved off-plan, review by {review}" if review else "approved off-plan"
        if row.state is AlignmentState.BUILT_OFF_PLAN:
            return "built with no design: add one, or approve it in the register"
        if model is not None and model.persistence is Persistence.PERSISTENT:
            return "assumed permanent; mark it verified once someone has checked it"
        return ALIGNMENT_STATE_LABELS[row.state].lower()
    return ""


def roadmap_lanes(result: RunResult) -> list[Lane]:
    """Every entity Hunter tracks, placed in one lane.

    The register decides first: a person saying a table is deprecated outranks
    the chain saying it is live. A table declared temporary in the register is
    a working step or a one-off, and gets its own lane so the review dates are
    in one place. Everything else is placed by where it sits in the alignment
    chain. Tables the register marks temporary outside the alignment layers,
    such as integration steps, are added too, because their review dates are
    what stops them becoming permanent by accident.
    """
    project = result.project
    register = result.register
    buckets: dict[str, list[RoadmapItem]] = {key: [] for key, *_ in ROADMAP_LANES}
    placed: set[str] = set()

    for row in result.alignment.rows:
        model = project.any_model(row.model_name) if row.model_name else None
        entry = register.entry(row.model_name) if row.model_name else None
        lane = _lane_for(row, entry, model)
        if lane is None:
            continue
        if row.model_name:
            placed.add(row.model_name)
        buckets[lane].append(
            RoadmapItem(
                label=row.label,
                technical_name=row.technical_name,
                owner=(model.owner if model else None) or row.owner,
                status=model.persistence.label if model else "",
                state_label=row.state_label,
                next_step=_next_step(lane, row, entry, model),
                domain=row.domain or (model.domain if model else None) or "",
            )
        )

    for name, entry in register.models.items():
        model = project.any_model(name)
        if model is None or name in placed:
            continue
        if entry.status is not None:
            lane = _STATUS_LANE[entry.status]
        elif model.persistence is Persistence.TEMPORARY:
            lane = "temporary"
        else:
            continue
        review = _when(entry.review_by) if entry.review_by else ""
        buckets[lane].append(
            RoadmapItem(
                label=entry.business_name or name.split("__")[-1].replace("_", " "),
                technical_name=name,
                owner=model.owner or entry.owner,
                status=model.persistence.label,
                state_label="Outside the modelled layers",
                next_step=f"review by {review}" if review else "no review date set",
                domain=entry.domain or model.domain or "",
            )
        )

    lanes = []
    for key, title, meaning, tone in ROADMAP_LANES:
        items = sorted(buckets[key], key=lambda item: (item.domain, item.label))
        lanes.append(Lane(key=key, title=title, meaning=meaning, tone=tone, items=tuple(items)))
    return lanes


def _roadmap(result: RunResult) -> str:
    """Where every table is on its way from an idea to retirement."""
    lanes = roadmap_lanes(result)
    if not any(lane.items for lane in lanes):
        return ""
    tones = _area_tones(result)
    columns = []
    for lane in lanes:
        if lane.items:
            items = []
            for item in lane.items:
                tone = tones.get(item.domain, brand.MUTED_INK)
                sub = " · ".join(
                    part
                    for part in (
                        item.technical_name or "",
                        f"owner: {item.owner}" if item.owner else "",
                    )
                    if part
                )
                chip = _status_chip(item.status) if item.status else ""
                items.append(
                    f'<li data-find="{esc(item.searchable)}">'
                    f"<b class='tname' style='--tone:{tone}'>{esc(item.label)}</b>"
                    f"{chip}"
                    f"<span class='objects'>{esc(sub)}</span>"
                    f"<span class='when'>{esc(item.next_step)}</span></li>"
                )
            body = f"<ul>{''.join(items)}</ul>"
        else:
            body = "<p class='empty'>Nothing here</p>"
        columns.append(
            f"<div class='lane' style='--tone:{lane.tone}' data-lane='{lane.key}'>"
            f"<h3>{esc(lane.title)}<b>{len(lane.items)}</b></h3>"
            f"<p class='meaning'>{esc(lane.meaning)}</p>{body}</div>"
        )
    built = [item for lane in lanes for item in lane.items if item.status]
    verified = sum(1 for item in built if item.status == "verified")
    temporary = sum(1 for item in built if item.status == "temporary")
    stats = (
        "<div class='align-stats'>"
        f"<div class='stat {'yes' if verified == len(built) else 'mostly' if verified else 'no'}'>"
        f"<b>{verified} of {len(built)}</b><span>built tables confirmed to stay</span></div>"
        f"<div class='stat'><b>{temporary}</b><span>temporary by design</span></div>"
        "</div>"
    )
    total = sum(len(lane.items) for lane in lanes)
    finder = (
        "<div class='finder'>"
        "<input type='search' class='find' autocomplete='off'"
        " placeholder='Find a table, an entity, an owner, an area or a status'"
        " aria-label='Find on the roadmap'>"
        f"<span class='tally'>{total} tables</span>"
        "</div>"
    )
    return _card(
        "Roadmap: what is planned, live, temporary and on its way out",
        "Every table Hunter tracks, in one lane. The register decides first; the chain from "
        "design to build decides the rest.",
        f"<div class='roadmap'>{finder}{stats}<div class='lanes'>{''.join(columns)}</div>"
        "<p class='empty' hidden>Nothing matches that.</p></div>",
        anchor="roadmap",
    )


def _mark(state: str, title: str | None = None) -> str:
    klass, glyph, default = MARKS[state]
    return f"<span class='mark {klass}' title='{esc(title or default)}'>{glyph}</span>"


@dataclass(frozen=True)
class ReadinessRow:
    """One built table, and what it still needs to be fully ready.

    Ready means: described, every column described, a named owner, a key
    tested for uniqueness and nulls, a LookML view, Droughty's tests applied,
    and live in the warehouse, for each of those Hunter could check.
    """

    name: str
    business: str
    domain: str
    switched_off: bool
    status: str
    status_note: str
    description: str
    columns_described: tuple[int, int]
    owner: str
    key_tests: str
    test_count: int
    lookml: str
    droughty: str
    warehouse: str
    gaps: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.gaps

    @property
    def searchable(self) -> str:
        parts = [
            self.name,
            self.business,
            self.domain,
            self.status,
            "ready" if self.ready else "gaps",
            *self.gaps,
        ]
        return " ".join(part for part in parts if part).lower()


def readiness_rows(result: RunResult) -> list[ReadinessRow]:
    """Every built table in the alignment layers, sorted by area then name."""
    project = result.project
    introspected = project.droughty.introspected if project.droughty else {}
    live = {name.lower() for name in introspected}
    droughty = project.droughty
    covered = droughty.covered_models if droughty else set()
    droughty_missing = {
        finding.subject
        for finding in result.open_findings
        if finding.rule == "droughty.generated_test_missing"
    }

    rows: list[ReadinessRow] = []
    for row in result.alignment.rows:
        if not row.model_name or not _in_repo(row):
            continue
        model = project.any_model(row.model_name)
        if model is None:
            continue
        gaps: list[str] = []
        switched_off = row.repo is Presence.DISABLED
        if switched_off:
            gaps.append("switched off")

        description = "yes" if model.has_description else "no"
        if description == "no":
            gaps.append("no description")

        total = len(model.columns)
        described = sum(1 for column in model.columns if column.has_description)
        if total and described < total:
            gaps.append(f"{total - described} of {total} columns undescribed")

        owner = "yes" if (model.owner or row.owner) else "no"
        if owner == "no":
            gaps.append("no owner")

        tests = project.tests_for(model.name)
        kinds = {test.kind for test in tests if test.is_key_test and test.is_enforced}
        if {"unique", "not_null"} <= kinds:
            key_tests = "yes"
        elif kinds:
            key_tests = "partial"
            gaps.append(
                "key tested for " + ("uniqueness only" if "unique" in kinds else "nulls only")
            )
        else:
            key_tests = "no"
            gaps.append("no tests" if not tests else "no key tests")

        if project.has_lookml:
            lookml = "yes" if project.views_for_model(model.name) else "no"
            if lookml == "no":
                gaps.append("no LookML view")
        else:
            lookml = "unknown"

        if droughty is not None and (covered or droughty_missing):
            if model.name not in covered:
                droughty_state = "no"
                gaps.append("not covered by Droughty")
            elif model.name in droughty_missing:
                droughty_state = "partial"
                gaps.append("Droughty tests not applied")
            else:
                droughty_state = "yes"
        else:
            droughty_state = "unknown"

        if live:
            warehouse = "yes" if model.name.lower() in live else "no"
            if warehouse == "no":
                gaps.append("not in the warehouse")
        else:
            warehouse = "unknown"

        rows.append(
            ReadinessRow(
                name=model.name,
                business=row.business_name or "",
                domain=row.domain or model.domain or "",
                switched_off=switched_off,
                status=model.persistence.label,
                status_note=_status_note(model, result.register.entry(model.name)),
                description=description,
                columns_described=(described, total),
                owner=owner,
                key_tests=key_tests,
                test_count=len(tests),
                lookml=lookml,
                droughty=droughty_state,
                warehouse=warehouse,
                gaps=tuple(gaps),
            )
        )
    rows.sort(key=lambda item: (item.domain or "~", item.name))
    return rows


def _readiness(result: RunResult) -> str:
    """Every built table against what dbt and Looker expect of it, searchable.

    The alignment card says whether a table should exist. This one says whether
    a table that does exist is finished: documented, owned, tested, reachable
    in Looker, and matching what Droughty found. The last column names every
    gap, so a row is a to-do list.
    """
    rows = readiness_rows(result)
    if not rows:
        return ""
    knows_lookml = any(row.lookml != "unknown" for row in rows)
    knows_droughty = any(row.droughty != "unknown" for row in rows)
    knows_warehouse = any(row.warehouse != "unknown" for row in rows)
    ready = sum(1 for row in rows if row.ready)

    heads = ["Table", "Status", "Described", "Columns described", "Owner", "Key tests"]
    if knows_lookml:
        heads.append("LookML view")
    if knows_droughty:
        heads.append("Droughty")
    if knows_warehouse:
        heads.append("In the warehouse")
    heads.append("What it still needs")

    tones = _area_tones(result)
    areas = sorted({row.domain for row in rows if row.domain})
    body = []
    for row in rows:
        described, total = row.columns_described
        if total == 0:
            columns = _mark("unknown", "no columns in the manifest")
        elif described == total:
            columns = _mark("yes", f"all {total} columns described")
        elif described:
            columns = _mark("partial", f"{described} of {total} columns described")
        else:
            columns = _mark("no", f"none of {total} columns described")
        tone = tones.get(row.domain, brand.MUTED_INK)
        label = f"<b class='tname' style='--tone:{tone}'>{esc(row.name)}</b>"
        sub = " · ".join(part for part in (row.business, row.domain.replace("_", " ")) if part)
        if sub:
            label += f"<span class='objects'>{esc(sub)}</span>"
        if row.switched_off:
            label += "<em class='chip grey'>switched off</em>"
        key_title = {
            "yes": f"unique and not null tested · {row.test_count} tests in all",
            "partial": f"only one of the two key tests · {row.test_count} tests in all",
            "no": "no test proves the key" if row.test_count else "no tests at all",
        }[row.key_tests]
        cells = [
            f"<td>{label}</td>",
            f"<td>{_status_chip(row.status, row.status_note)}</td>",
            f"<td>{_mark(row.description)}</td>",
            f"<td>{columns} <span class='objects'>{described}/{total}</span></td>",
            f"<td>{_mark(row.owner)}</td>",
            f"<td>{_mark(row.key_tests, key_title)}</td>",
        ]
        if knows_lookml:
            cells.append(f"<td>{_mark(row.lookml)}</td>")
        if knows_droughty:
            cells.append(f"<td>{_mark(row.droughty)}</td>")
        if knows_warehouse:
            cells.append(f"<td>{_mark(row.warehouse)}</td>")
        if row.ready:
            cells.append("<td><em class='chip ready'>Ready</em></td>")
        else:
            chips = "".join(f"<em class='chip gap'>{esc(gap)}</em>" for gap in row.gaps)
            cells.append(f"<td class='gaps'>{chips}</td>")
        body.append(
            f"<tr data-find=\"{esc(row.searchable)}\" data-gaps='{0 if row.ready else 1}'"
            f" data-area='{esc(row.domain)}'>{''.join(cells)}</tr>"
        )
    tabs = ""
    if len(areas) > 1:
        buttons = ["<button type='button' class='tab on' data-area=''>All areas</button>"]
        buttons += [
            f"<button type='button' class='tab' data-area='{esc(area)}'"
            f" style='--tone:{tones.get(area, brand.MUTED_INK)}'>"
            f"<i class='dot'></i>{esc(area.replace('_', ' '))}</button>"
            for area in areas
        ]
        tabs = f"<div class='tabs area-tabs' id='table-areas'>{''.join(buttons)}</div>"

    header = "".join(f"<th>{esc(head)}</th>" for head in heads)
    finder = (
        "<div class='finder'>"
        "<input type='search' id='table-search' autocomplete='off'"
        " placeholder='Find a table, an area or a gap, such as \"no owner\"'"
        " aria-label='Search the table list'>"
        "<label class='toggle'><input type='checkbox' id='table-gaps'>"
        " only tables with gaps</label>"
        f"<span class='tally' id='table-tally'>{len(rows)} tables</span>"
        "</div>"
    )
    stats = (
        "<div class='align-stats'>"
        f"<div class='stat {'yes' if ready == len(rows) else 'mostly' if ready else 'no'}'>"
        f"<b>{ready} of {len(rows)}</b><span>built tables ready: described, owned, tested, "
        "in Looker</span></div></div>"
    )
    key = (
        "<div class='heat-key'>"
        "<span><em class='chip status-verified'>verified</em> confirmed to stay by a named "
        "person</span>"
        "<span><em class='chip status-permanent'>permanent</em> meant to stay</span>"
        "<span><em class='chip status-temporary'>temporary</em> a working step or a one-off"
        "</span>"
        "<span><b class='mark yes'>&#10003;</b> in place</span>"
        "<span><b class='mark off'>&#9679;</b> partly</span>"
        "<span><b class='mark no'>&#10007;</b> missing</span>"
        "<span><b class='mark dash'>&#8211;</b> Hunter had nothing to read</span>"
        "</div>"
    )
    return _card(
        "Built tables: what each one still needs",
        "One row per table in the repository. The alignment card says whether a table "
        "should exist; this says whether it is finished.",
        tabs + finder + stats + "<div class='scroller'><table id='table-list'>"
        f"<thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
        "<p class='empty' id='table-empty' hidden>Nothing matches that.</p>" + key,
        anchor="readiness",
    )


# --------------------------------------------------------------------- page


NAV = [
    ("#top", "Score"),
    ("#checklist", "Checklist"),
    ("#alignment", "Modelling alignment"),
    ("#diagrams", "Diagrams"),
    ("#dag", "Data flow"),
    ("#roadmap", "Roadmap"),
    ("#readiness", "Table readiness"),
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
  var gapsOnly = document.getElementById('table-gaps');
  var areaTabs = document.getElementById('table-areas');
  var area = '';
  function filter() {
    var needle = box.value.trim().toLowerCase();
    var onlyGaps = !!(gapsOnly && gapsOnly.checked);
    var shown = 0;
    for (var i = 0; i < rows.length; i++) {
      var hit = (!needle || rows[i].getAttribute('data-find').indexOf(needle) !== -1)
        && (!onlyGaps || rows[i].getAttribute('data-gaps') === '1')
        && (!area || rows[i].getAttribute('data-area') === area);
      rows[i].hidden = !hit;
      if (hit) { shown++; }
    }
    if (tally) {
      tally.textContent = (shown === rows.length && !needle && !onlyGaps && !area)
        ? rows.length + ' tables'
        : shown + ' of ' + rows.length + ' tables';
    }
    if (empty) { empty.hidden = shown !== 0; }
  }
  box.addEventListener('input', filter);
  if (gapsOnly) { gapsOnly.addEventListener('change', filter); }
  if (areaTabs) {
    areaTabs.addEventListener('click', function (event) {
      var tab = event.target.closest('.tab');
      if (!tab) { return; }
      area = tab.getAttribute('data-area') || '';
      Array.prototype.forEach.call(areaTabs.querySelectorAll('.tab'), function (t) {
        t.classList.toggle('on', t === tab);
      });
      filter();
    });
  }
})();
"""

#: Tabs and zoom for every tabbed diagram card. Each diagram is drawn the first time
#: its tab is opened, because the library measures text and a hidden element
#: measures as nothing. The library is bundled into the page; if it still failed
#: to start, the source stays as text and a note says so.
DIAGRAM_JS = """
(function () {
  var groups = document.querySelectorAll('.tabbed');
  if (!groups.length) { return; }
  var ready = typeof window.mermaid !== 'undefined';
  if (ready) {
    window.mermaid.initialize({ startOnLoad: false, theme: 'base', securityLevel: 'antiscript',
      themeVariables: {
        fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif', fontSize: '13px',
        primaryColor: '#ffffff', primaryBorderColor: '#525aff', primaryTextColor: '#151d2d',
        lineColor: '#9aa1ad', clusterBkg: '#fafbfe', clusterBorder: '#e2e5ec',
        edgeLabelBackground: '#ffffff', tertiaryColor: '#fafbfe'
      } });
  }
  var renders = 0;
  var SHAPES = { box: ['["', '"]'], round: ['("', '")'], cylinder: ['[("', '")]'],
                 parallelogram: ['[/"', '"/]'], hexagon: ['{{"', '"}}'] };
  function esc(text) {
    return String(text).replace(/"/g, "'").replace(/\\n/g, ' ').trim();
  }
  function assemble(spec, keep) {
    var kept = {};
    var nodes = spec.nodes.filter(function (n) { return !keep || keep[n.id]; });
    nodes.forEach(function (n) { kept[n.id] = true; });
    var lines = ['flowchart LR'];
    spec.groups.forEach(function (g) {
      var members = nodes.filter(function (n) { return n.group === g.id; });
      if (!members.length) { return; }
      lines.push('  subgraph ' + g.id + '["' + esc(g.label) + '"]');
      members.forEach(function (n) {
        var shape = SHAPES[n.shape] || SHAPES.box;
        lines.push('    ' + n.id + shape[0] + esc(n.label) + shape[1]);
      });
      lines.push('  end');
    });
    spec.edges.forEach(function (e) {
      if (kept[e[0]] && kept[e[1]]) { lines.push('  ' + e[0] + ' --> ' + e[1]); }
    });
    nodes.forEach(function (n) { if (n.style) { lines.push('  style ' + n.id + ' ' + n.style); } });
    return lines.join('\\n') + '\\n';
  }
  function walk(spec, seeds, direction, depth) {
    var next = {}, seen = {};
    spec.edges.forEach(function (e) {
      var from = direction === 'up' ? e[1] : e[0], to = direction === 'up' ? e[0] : e[1];
      (next[from] = next[from] || []).push(to);
    });
    var frontier = Object.keys(seeds), steps = 0;
    while (frontier.length && (depth === null || steps < depth)) {
      var fresh = [];
      frontier.forEach(function (id) {
        (next[id] || []).forEach(function (n) {
          if (!seen[n] && !seeds[n]) { seen[n] = true; fresh.push(n); }
        });
      });
      frontier = fresh; steps++;
    }
    return seen;
  }
  function select(spec, text) {
    var m = /^\\s*(?:(\\d*)\\+)?([^+\\s]+)(?:\\+(\\d*))?\\s*$/.exec(text);
    if (!m) { return null; }
    var up = m[1] !== undefined, down = m[3] !== undefined;
    var upDepth = m[1] ? parseInt(m[1], 10) : null, downDepth = m[3] ? parseInt(m[3], 10) : null;
    var name = m[2].toLowerCase();
    var seeds = {};
    var exact = spec.nodes.filter(function (n) { return n.label.toLowerCase() === name; });
    if (exact.length) { exact.forEach(function (n) { seeds[n.id] = true; }); }
    else {
      var pattern = name.replace(/[.+?^${}()|[\\]\\\\]/g, '\\\\$&').replace(/\\*/g, '.*');
      var re = new RegExp('^' + pattern + '$');
      var loose = spec.nodes.filter(function (n) {
        var l = n.label.toLowerCase();
        return re.test(l) || (name.indexOf('*') === -1 && l.indexOf(name) !== -1);
      });
      loose.forEach(function (n) { seeds[n.id] = true; });
    }
    if (!Object.keys(seeds).length) { return {}; }
    var keep = {};
    Object.keys(seeds).forEach(function (id) { keep[id] = true; });
    function add(found) { Object.keys(found).forEach(function (id) { keep[id] = true; }); }
    if (up) { add(walk(spec, seeds, 'up', upDepth)); }
    if (down) { add(walk(spec, seeds, 'down', downDepth)); }
    return keep;
  }
  // ---- the alignment card: filter rows as you type
  var align = document.querySelector('.align');
  if (align) {
    var abox = align.querySelector('.find');
    var arows = Array.prototype.slice.call(align.querySelectorAll('details.arow'));
    var agroups = Array.prototype.slice.call(align.querySelectorAll('.align-group'));
    var atally = align.querySelector('.tally');
    var aempty = align.querySelector('.empty');
    abox.addEventListener('input', function () {
      var needle = abox.value.trim().toLowerCase();
      var shown = 0, byGroup = {};
      arows.forEach(function (row) {
        var hit = !needle || row.getAttribute('data-find').indexOf(needle) !== -1;
        row.hidden = !hit;
        if (hit) { shown++; byGroup[row.getAttribute('data-group')] = true; }
      });
      agroups.forEach(function (g) {
        g.hidden = !!needle && !byGroup[g.getAttribute('data-group')];
      });
      if (atally) {
        atally.textContent = (needle ? shown + ' of ' + arows.length : arows.length) + ' entities';
      }
      if (aempty) { aempty.hidden = shown !== 0; }
    });
  }
  // ---- the roadmap card: filter the lane items as you type
  var roadmap = document.querySelector('.roadmap');
  if (roadmap) {
    var rbox = roadmap.querySelector('.find');
    var ritems = Array.prototype.slice.call(roadmap.querySelectorAll('.lane li[data-find]'));
    var rlanes = Array.prototype.slice.call(roadmap.querySelectorAll('.lane'));
    var rtally = roadmap.querySelector('.tally');
    var rempty = roadmap.querySelector('.empty');
    rbox.addEventListener('input', function () {
      var needle = rbox.value.trim().toLowerCase();
      var shown = 0;
      ritems.forEach(function (item) {
        var hit = !needle || item.getAttribute('data-find').indexOf(needle) !== -1;
        item.hidden = !hit;
        if (hit) { shown++; }
      });
      rlanes.forEach(function (lane) {
        var count = lane.querySelectorAll('li[data-find]:not([hidden])').length;
        var badge = lane.querySelector('h3 b');
        if (badge) { badge.textContent = count; }
      });
      if (rtally) {
        rtally.textContent = (needle ? shown + ' of ' + ritems.length : ritems.length) + ' tables';
      }
      if (rempty) { rempty.hidden = shown !== 0; }
    });
  }
  // ---- relationship lines for the physical model cards
  function drawErd(erd) {
    var svg = erd.querySelector('.erd-lines');
    if (!svg) { return; }
    var origin = erd.getBoundingClientRect();
    var z = parseFloat(erd.style.zoom || '1') || 1;
    var parts = [];
    Array.prototype.forEach.call(erd.querySelectorAll('.erd-row[data-ref]'), function (row) {
      var ref = row.getAttribute('data-ref').split('.');
      var card = erd.querySelector('.erd-card[data-table="' + ref[0] + '"]');
      if (!card) { return; }
      var target = card.querySelector('.erd-row[data-col="' + ref[1] + '"]')
        || card.querySelector('header');
      var a = row.getBoundingClientRect(), b = target.getBoundingClientRect();
      var ay = (a.top + a.height / 2 - origin.top) / z;
      var by = (b.top + b.height / 2 - origin.top) / z;
      // Leave from whichever side of each row is nearest the other, so a line
      // never crosses the card it came from. Same-side pairs bow outward.
      var sides = [
        [a.right, b.left, 1, -1], [a.left, b.right, -1, 1],
        [a.left, b.left, -1, -1], [a.right, b.right, 1, 1]
      ];
      var best = sides[0], gap = Infinity;
      sides.forEach(function (s) {
        var d = Math.abs(s[0] - s[1]) + (s[2] === s[3] ? 80 : 0);
        if (d < gap) { gap = d; best = s; }
      });
      var ax = (best[0] - origin.left) / z, bx = (best[1] - origin.left) / z;
      var reach = Math.max(36, Math.abs(bx - ax) / 2);
      var c1 = ax + best[2] * reach, c2 = bx + best[3] * reach;
      parts.push('<path d="M' + ax + ' ' + ay + ' C' + c1 + ' ' + ay + ' '
        + c2 + ' ' + by + ' ' + bx + ' ' + by + '"/>');
      parts.push('<circle cx="' + ax + '" cy="' + ay + '" r="3.5"/>');
      parts.push('<line x1="' + bx + '" y1="' + (by - 6) + '" x2="' + bx + '" y2="'
        + (by + 6) + '"/>');
    });
    svg.setAttribute('viewBox', '0 0 ' + (erd.scrollWidth) + ' ' + (erd.scrollHeight));
    svg.setAttribute('width', erd.scrollWidth); svg.setAttribute('height', erd.scrollHeight);
    svg.innerHTML = parts.join('');
  }
  window.addEventListener('resize', function () {
    Array.prototype.forEach.call(document.querySelectorAll('.pane:not([hidden]) .erd'), drawErd);
  });
  // ---- find within a diagram: dim what does not match
  function highlight(p, needle) {
    var targets = p.querySelectorAll(
      '.erd-card, .ent, .canvas svg g.node, .canvas svg g[id^="entity-"]');
    var hits = 0;
    Array.prototype.forEach.call(targets, function (el) {
      var text = (el.getAttribute('data-find') || el.textContent || '').toLowerCase();
      var hit = !!needle && text.indexOf(needle) !== -1;
      el.classList.toggle('dim', !!needle && !hit);
      el.classList.toggle('hit', hit);
      if (hit) { hits++; }
    });
    var edges = p.querySelectorAll(
      '.canvas svg .edgePaths, .canvas svg .edgeLabels, .canvas svg .relationshipLine, '
      + '.canvas svg .relationshipLabelBox, .erd-lines');
    Array.prototype.forEach.call(edges, function (el) { el.classList.toggle('dim', !!needle); });
    return hits;
  }
  Array.prototype.forEach.call(groups, function (group) {
    var tabs = group.querySelectorAll('.tab');
    var zoom = group.querySelector('.zoom');
    var note = group.querySelector('.offline');
    var selector = group.querySelector('.selector');
    var finder = group.querySelector('.finder .find');
    var findTally = group.querySelector('.find-tally');
    var scale = {};
    var current = null;
    function refind() {
      if (!finder || !current) { return; }
      var p = pane(current);
      var needle = finder.value.trim().toLowerCase();
      var hits = p ? highlight(p, needle) : 0;
      if (findTally) { findTally.textContent = needle ? hits + ' found' : ''; }
    }
    if (finder) { finder.addEventListener('input', refind); }
    if (!ready && note && group.querySelector('pre.mermaid')) { note.hidden = false; }
    if (ready && selector) { selector.hidden = false; }
    function pane(key) { return group.querySelector('.pane[data-key="' + key + '"]'); }
    function specOf(key) {
      var p = pane(key);
      var holder = p ? p.querySelector('script.dag-spec') : null;
      if (!holder) { return null; }
      try { return JSON.parse(holder.textContent); } catch (err) { return null; }
    }
    function redraw(key, keep) {
      var p = pane(key), spec = specOf(key);
      if (!ready || !p || !spec) { return; }
      var canvas = p.querySelector('.canvas');
      var tally = selector ? selector.querySelector('.sel-tally') : null;
      var models = spec.nodes.filter(function (n) { return n.kind === 'model'; }).length;
      var shown = keep
        ? spec.nodes.filter(function (n) { return keep[n.id] && n.kind === 'model'; }).length
        : models;
      if (tally) {
        tally.textContent = keep ? shown + ' of ' + models + ' tables' : models + ' tables';
      }
      if (keep && !shown) {
        canvas.innerHTML = "<p class='empty'>Nothing matches that selection.</p>";
        return;
      }
      renders++;
      window.mermaid.render('hunter-dag-' + renders, assemble(spec, keep)).then(function (out) {
        canvas.innerHTML = out.svg;
        scale[key] = fit(key); apply(key);
      }).catch(function () { if (note) { note.hidden = false; } });
    }
    function applySelection() {
      if (!selector || !current) { return; }
      var text = selector.querySelector('.select').value;
      if (!text.trim()) { redraw(current, null); return; }
      var keep = select(specOf(current) || { nodes: [], edges: [], groups: [] }, text);
      redraw(current, keep || {});
    }
    if (selector) {
      var timer = null;
      selector.querySelector('.select').addEventListener('input', function () {
        clearTimeout(timer); timer = setTimeout(applySelection, 250);
      });
      selector.querySelector('.clear').addEventListener('click', function () {
        selector.querySelector('.select').value = ''; applySelection();
      });
    }
    function natural(svg) {
      var box = svg.viewBox && svg.viewBox.baseVal;
      return (box && box.width) || svg.getBoundingClientRect().width || 800;
    }
    function fit(key) {
      var p = pane(key);
      var svg = p ? p.querySelector('.canvas svg') : null;
      var canvas = p ? p.querySelector('.canvas') : null;
      if (!svg || !canvas) { return 1; }
      // Shrink to fit the canvas, but never so far that labels stop being
      // readable; past that point the canvas scrolls sideways instead.
      var room = canvas.clientWidth - 36;
      return Math.max(0.8, Math.min(1, room > 0 ? room / natural(svg) : 1));
    }
    function apply(key) {
      var p = pane(key);
      var erd = p ? p.querySelector('.erd') : null;
      if (erd) {
        erd.style.zoom = String(scale[key] || 1);
        drawErd(erd);
        return;
      }
      var svg = p ? p.querySelector('.canvas svg') : null;
      if (!svg) { return; }
      svg.style.maxWidth = 'none';
      svg.style.width = (natural(svg) * (scale[key] || 1)) + 'px';
    }
    function draw(key) {
      var p = pane(key);
      if (!p) { return; }
      if (p.querySelector('.erd')) {
        if (!(key in scale)) { scale[key] = 1; }
        apply(key); refind();
        if (zoom) { zoom.hidden = false; }
        return;
      }
      if (!ready) { return; }
      var pre = p.querySelector('pre.mermaid');
      if (!pre || pre.getAttribute('data-processed')) { apply(key); refind(); return; }
      window.mermaid.run({ nodes: [pre] }).then(function () {
        scale[key] = fit(key); apply(key); refind();
        if (zoom) { zoom.hidden = false; }
      }).catch(function () { if (note) { note.hidden = false; } });
    }
    function show(key) {
      current = key;
      for (var i = 0; i < tabs.length; i++) {
        var k = tabs[i].getAttribute('data-pane');
        var on = k === key;
        tabs[i].classList.toggle('on', on);
        tabs[i].setAttribute('aria-selected', on ? 'true' : 'false');
        var p = pane(k);
        if (p) { p.hidden = !on; }
      }
      draw(key);
      if (selector && selector.querySelector('.select').value.trim()) { applySelection(); }
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
        else if (what === 'out') { s = Math.max(0.2, s / 1.25); }
        else { s = fit(current); }
        scale[current] = s;
        apply(current);
      });
    }
    if (tabs.length) { show(tabs[0].getAttribute('data-pane')); }
  });
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
            _hero(result, generated),
            _checklist(result),
            _alignment(result),
            _diagrams(result),
            _dag(result),
            _roadmap(result),
            _readiness(result),
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

<main><div class="wrap"><div class="grid">{panels}</div></div></main>

<footer><div class="wrap">
  <img src="{brand.logo_uri()}" alt="Rittman Analytics">
  <span>{esc(branding.attribution)}. Read from the repository, nothing written back.</span>
  <span class="meta">{esc(stamp)}</span>
</div></footer>
<script>{SEARCH_JS}</script>
<script>{brand.mermaid_js()}</script>
<script>{DIAGRAM_JS}</script>
</body>
</html>
"""
