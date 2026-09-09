"""Rittman Analytics theme for the generated report site.

The dashboard is built from scratch and needs none of this. These are the
overrides that make the detail pages behind it match, so a reader moving from
the front page into the evidence does not appear to change product.

Material exposes its palette as custom properties, so the whole theme is a
short list of colour swaps plus a few type corrections. Nothing here changes
layout: the less of Material this fights, the less of it breaks on upgrade.
"""

from __future__ import annotations

from hunter import brand

BRAND_CSS = f""":root {{
  --md-primary-fg-color:        {brand.PRIMARY};
  --md-primary-fg-color--light: {brand.ACCENT};
  --md-primary-fg-color--dark:  {brand.INK};
  --md-primary-bg-color:        #fff;
  --md-accent-fg-color:         {brand.ACCENT};
  --md-typeset-a-color:         {brand.PRIMARY};
  --md-default-fg-color:        {brand.INK};
  --md-code-bg-color:           {brand.MUTED};
  --md-text-font:               'Inter', -apple-system, BlinkMacSystemFont,
                                'Segoe UI', Roboto, sans-serif;
}}

[data-md-color-scheme="slate"] {{
  --md-default-bg-color:        {brand.INK};
  --md-primary-fg-color:        {brand.INK};
  --md-accent-fg-color:         {brand.SKY};
  --md-typeset-a-color:         {brand.SKY};
}}

.md-header {{
  background: #fff;
  color: {brand.INK};
  box-shadow: 0 1px 0 {brand.BORDER};
}}
.md-header__title {{ font-weight: 700; letter-spacing: -0.01em; }}
.md-header .md-icon, .md-header__button {{ color: {brand.INK}; }}
.md-tabs {{ background: {brand.INK}; }}

.md-typeset h1, .md-typeset h2 {{
  font-weight: 700;
  letter-spacing: -0.02em;
  color: {brand.INK};
}}

/* Tables carry most of the evidence, so they get the most attention. */
.md-typeset table:not([class]) {{ font-size: 13.5px; border: 1px solid {brand.BORDER}; }}
.md-typeset table:not([class]) th {{
  background: {brand.MUTED};
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 700;
  color: #6b7280;
}}

/* A link back to the dashboard, on every page. */
.hunter-back {{
  display: inline-block;
  margin-bottom: 18px;
  padding: 7px 14px;
  border-radius: 8px;
  background: {brand.PRIMARY};
  color: #fff !important;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
}}

/* The score line on the scorecard, so the grades read at a glance. */
.grade-a {{ color: {brand.GRADE_COLOURS["A"]}; font-weight: 700; }}
.grade-b {{ color: {brand.GRADE_COLOURS["B"]}; font-weight: 700; }}
.grade-c {{ color: {brand.GRADE_COLOURS["C"]}; font-weight: 700; }}
.grade-d {{ color: {brand.GRADE_COLOURS["D"]}; font-weight: 700; }}
.grade-e {{ color: {brand.GRADE_COLOURS["E"]}; font-weight: 700; }}
"""


# ---------------------------------------------------------------- documentation


DOCS_CSS = f"""/* Rittman Hunter documentation. Generated from hunter.brand and
   hunter.emit.theme by scripts/build_docs_pages.py. Do not edit by hand. */

/* ---- type: fewer sizes, more contrast between them ---- */
.md-typeset {{ font-size: 0.82rem; line-height: 1.65; }}
.md-typeset h1 {{
  font-size: 2.05rem; font-weight: 700; letter-spacing: -0.03em;
  line-height: 1.1; margin: 0 0 0.6rem;
}}
.md-typeset h2 {{
  font-size: 1.28rem; font-weight: 700; letter-spacing: -0.02em;
  margin: 2.6rem 0 0.7rem; padding-top: 1.3rem;
  border-top: 1px solid var(--md-default-fg-color--lightest);
}}
.md-typeset h2:first-of-type {{ border-top: 0; padding-top: 0; margin-top: 1.6rem; }}
.md-typeset h3 {{
  font-size: 0.98rem; font-weight: 700; letter-spacing: -0.01em; margin: 1.7rem 0 0.4rem;
}}
.md-typeset h1 + p {{ font-size: 0.95rem; color: #5b6472; max-width: 62ch; }}

/* ---- lede: the one-line answer under a page title ---- */
.md-typeset .lede {{
  font-size: 1.02rem; line-height: 1.5; color: #4b5563; max-width: 60ch;
  margin: 0 0 1.6rem;
}}

/* ---- hero, on the home page. The docs and the product share a look. ---- */
.md-typeset .hero {{
  background: {brand.INK}; color: #fff; border-radius: 16px;
  padding: 2.3rem 2.2rem; margin: 0 0 1.6rem;
}}
.md-typeset .hero h1 {{ color: #fff; font-size: 2.3rem; margin: 0 0 0.7rem; }}
.md-typeset .hero p {{
  color: rgba(255,255,255,0.68); font-size: 1rem; max-width: 64ch; margin: 0 0 1.4rem;
}}
/* The theme floats an "edit this page" button, which a full-width hero would
   sit underneath. Hidden on any page carrying one; every other page keeps it. */
.md-content:has(.hero) .md-content__button {{ display: none; }}
.md-typeset .hero .figures {{
  display: flex; gap: 2.2rem; flex-wrap: wrap; margin: 1.6rem 0 0;
  padding-top: 1.4rem; border-top: 1px solid rgba(255,255,255,0.13);
}}
.md-typeset .hero .figures div b {{
  display: block; font-size: 1.6rem; font-weight: 700; letter-spacing: -0.02em;
}}
.md-typeset .hero .figures div span {{
  font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.07em;
  color: rgba(255,255,255,0.5); font-weight: 600;
}}
.md-typeset .hero .md-button {{
  background: {brand.PRIMARY}; border-color: {brand.PRIMARY}; color: #fff;
}}
.md-typeset .hero .md-button:hover {{ background: #6b72ff; border-color: #6b72ff; }}
.md-typeset .hero .md-button--secondary {{
  background: transparent; border-color: rgba(255,255,255,0.3); color: #fff;
}}

/* ---- cards: navigation you can scan instead of read ---- */
.md-typeset .cards {{
  display: grid; gap: 0.85rem; margin: 1.4rem 0;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}}
.md-typeset .cards > * {{
  display: block; padding: 1.1rem 1.2rem; border-radius: 12px;
  border: 1px solid var(--md-default-fg-color--lightest);
  background: var(--md-default-bg-color); text-decoration: none; color: inherit;
}}
.md-typeset .cards > a:hover {{
  border-color: {brand.PRIMARY};
  box-shadow: 0 1px 3px rgba(21,29,45,0.07), 0 8px 20px rgba(82,90,255,0.09);
}}
.md-typeset .cards b {{
  display: block; font-size: 0.9rem; font-weight: 700; margin-bottom: 0.2rem;
  letter-spacing: -0.01em;
}}
.md-typeset .cards p {{ margin: 0; font-size: 0.76rem; color: #6b7280; line-height: 1.5; }}
.md-typeset .cards .tag {{
  display: inline-block; font-size: 0.6rem; font-weight: 700; letter-spacing: 0.06em;
  text-transform: uppercase; color: {brand.PRIMARY}; margin-bottom: 0.45rem;
}}

/* ---- steps: numbered, for anything with an order ---- */
.md-typeset ol.steps {{ counter-reset: step; list-style: none; margin: 1.3rem 0; padding: 0; }}
.md-typeset ol.steps > li {{
  counter-increment: step; position: relative; padding: 0 0 1.3rem 2.7rem;
  margin: 0; border-left: 2px solid var(--md-default-fg-color--lightest);
}}
.md-typeset ol.steps > li:last-child {{ border-left-color: transparent; padding-bottom: 0; }}
.md-typeset ol.steps > li::before {{
  content: counter(step); position: absolute; left: -0.85rem; top: -0.15rem;
  width: 1.7rem; height: 1.7rem; border-radius: 50%; background: {brand.PRIMARY};
  color: #fff; font-size: 0.76rem; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}}
.md-typeset ol.steps > li > b {{ display: block; font-size: 0.88rem; margin-bottom: 0.3rem; }}

/* ---- key: the one thing on a page that must not be missed ---- */
.md-typeset .key {{
  border-left: 4px solid {brand.PRIMARY}; background: {brand.BLUE_LIGHT};
  padding: 0.9rem 1.2rem; border-radius: 0 10px 10px 0; margin: 1.4rem 0;
  font-size: 0.82rem;
}}
.md-typeset .key > :first-child {{ margin-top: 0; }}
.md-typeset .key > :last-child {{ margin-bottom: 0; }}
.md-typeset .key b {{ color: {brand.INK}; }}

/* ---- tables carry most of the reference, so they get the attention ---- */
.md-typeset table:not([class]) {{
  font-size: 0.75rem; border: 1px solid var(--md-default-fg-color--lightest);
  border-radius: 10px; overflow: hidden; display: table; width: 100%;
}}
.md-typeset table:not([class]) th {{
  background: {brand.MUTED}; font-size: 0.64rem; text-transform: uppercase;
  letter-spacing: 0.06em; font-weight: 700; color: #6b7280; padding: 0.6rem 0.9rem;
}}
.md-typeset table:not([class]) td {{ padding: 0.6rem 0.9rem; vertical-align: top; }}
/* A two-column "label, explanation" table has no useful headings, and Markdown
   requires a header row, so several are written with empty cells. Hide the row
   only when every cell in it is empty: a partly-filled header is deliberate. */
.md-typeset table:not([class]) thead tr:not(:has(th:not(:empty))) {{ display: none; }}
.md-typeset table:not([class]) tr:last-child td {{ border-bottom: 0; }}

/* ---- collapsibles hold the reasoning, so the page holds the answer ---- */
.md-typeset details {{
  border: 0; border-left: 3px solid var(--md-default-fg-color--lightest);
  border-radius: 0; background: transparent; font-size: 0.78rem;
  box-shadow: none; margin: 1.2rem 0;
}}
.md-typeset details > summary {{
  background: transparent; font-weight: 600; font-size: 0.8rem; padding-left: 1.1rem;
}}
.md-typeset details > summary::before {{ display: none; }}
.md-typeset details[open] > summary {{ margin-bottom: 0.2rem; }}

/* ---- code ---- */
.md-typeset pre > code {{ font-size: 0.73rem; line-height: 1.6; }}
.md-typeset code {{ font-size: 0.76em; }}
.md-typeset .highlight {{ border-radius: 10px; }}

/* ---- nav ---- */
.md-nav__title {{ font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.07em; }}
.md-nav__link {{ font-size: 0.75rem; }}
.md-nav--secondary .md-nav__title {{ text-transform: none; letter-spacing: 0; }}

/* ---- footer ---- */
.md-footer-meta {{ background: {brand.INK}; }}
.md-copyright {{ font-size: 0.65rem; }}

/* ---- dark scheme ----
   Every colour above that is a literal rather than a theme variable has to be
   restated here, or it reads as low contrast on a dark ground. */
[data-md-color-scheme="slate"] {{
  --md-default-bg-color: {brand.INK};
}}
[data-md-color-scheme="slate"] .md-typeset h1,
[data-md-color-scheme="slate"] .md-typeset h2,
[data-md-color-scheme="slate"] .md-typeset h3 {{ color: #f1f3f8; }}
[data-md-color-scheme="slate"] .md-typeset h1 + p,
[data-md-color-scheme="slate"] .md-typeset .lede,
[data-md-color-scheme="slate"] .md-typeset .cards p {{ color: #9aa3b2; }}
[data-md-color-scheme="slate"] .md-typeset .hero {{
  background: #0d1420; border: 1px solid rgba(255,255,255,0.08);
}}
[data-md-color-scheme="slate"] .md-typeset .cards > * {{
  background: rgba(255,255,255,0.03); border-color: rgba(255,255,255,0.1);
}}
[data-md-color-scheme="slate"] .md-typeset .key {{
  background: rgba(82,90,255,0.14); color: #dfe3ec;
}}
[data-md-color-scheme="slate"] .md-typeset .key b {{ color: #fff; }}
[data-md-color-scheme="slate"] .md-typeset table:not([class]) th {{
  background: rgba(255,255,255,0.05); color: #9aa3b2;
}}
[data-md-color-scheme="slate"] .md-header {{
  background: #0d1420; box-shadow: 0 1px 0 rgba(255,255,255,0.08);
}}
[data-md-color-scheme="slate"] .md-header__title,
[data-md-color-scheme="slate"] .md-header .md-icon,
[data-md-color-scheme="slate"] .md-header__button,
[data-md-color-scheme="slate"] .md-header__source,
[data-md-color-scheme="slate"] .md-source,
[data-md-color-scheme="slate"] .md-source__repository {{ color: #f1f3f8; }}
[data-md-color-scheme="slate"] .md-source__facts {{ color: #9aa3b2; }}
/* The logo is a black wordmark, so it needs inverting on a dark header. */
[data-md-color-scheme="slate"] .md-header__button.md-logo img {{
  filter: invert(1) hue-rotate(180deg);
}}

@media screen and (max-width: 76.1875em) {{
  .md-typeset .hero {{ padding: 1.7rem 1.4rem; }}
  .md-typeset .hero h1 {{ font-size: 1.7rem; }}
}}
"""
