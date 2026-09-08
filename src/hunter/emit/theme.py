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
