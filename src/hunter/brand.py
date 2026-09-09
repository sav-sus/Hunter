"""Rittman Analytics brand: the palette, the typeface and the logo.

Every colour here is lifted from the design tokens published at
rittmananalytics.com, so nothing is an approximation of the brand. The names
match the site's own CSS variables, which makes them checkable against the
source rather than a matter of taste.

The logo ships inside the package and is inlined into generated HTML as a data
URI. A report is opened from a laptop, a build artifact or an email attachment,
so it has to render with no network and no neighbouring files.
"""

from __future__ import annotations

import base64
import functools
from pathlib import Path

ASSETS = Path(__file__).parent / "assets"

# ---- palette, from the published design tokens ----

#: Rittman Analytics blue. The one colour that carries the brand.
PRIMARY = "#525aff"
ACCENT = "#ad93f1"
SKY = "#88d7fb"
PEACH = "#ff9a75"
LIME = "#99ff99"

BLUE_LIGHT = "#e0e0ff"
PURPLE_LIGHT = "#e8e0fa"
SKY_LIGHT = "#e1f6fe"
PEACH_LIGHT = "#ffc2bd"
GREEN_LIGHT = "#d6ffd6"

#: The near-black navy the site uses for text and for dark surfaces.
INK = "#151d2d"
MUTED = "#f7f7f7"
MUTED_INK = "#94a3b8"
BORDER = "#e5e7eb"
DESTRUCTIVE = "#ef4444"
WHITE = "#ffffff"

FONT_STACK = (
    "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
    "'Helvetica Neue', Arial, sans-serif"
)
MONO_STACK = "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace"

#: A grade is the one judgement the report makes on its own, so the colour has
#: to be unambiguous. Green through to red, taken from the brand where the brand
#: has a colour for it and from a plain warning scale where it does not.
GRADE_COLOURS = {
    "A": "#16a34a",
    "B": "#65a30d",
    "C": "#d97706",
    "D": PEACH,
    "E": DESTRUCTIVE,
}

SEVERITY_COLOURS = {
    "critical": "#b91c1c",
    "high": DESTRUCTIVE,
    "medium": "#d97706",
    "low": SKY,
    "suggestion": MUTED_INK,
}

#: Ordered so a chart of several series stays legible. Brand colours first.
SERIES = [PRIMARY, ACCENT, SKY, PEACH, "#16a34a", "#d97706", MUTED_INK, "#0ea5e9"]


def grade_colour(grade: str) -> str:
    return GRADE_COLOURS.get(grade.upper(), MUTED_INK)


def severity_colour(severity: str) -> str:
    return SEVERITY_COLOURS.get(str(severity).lower(), MUTED_INK)


def score_colour(score: float) -> str:
    """The colour for a 0 to 100 figure, on the same scale as the grades."""
    for threshold, grade in ((90, "A"), (80, "B"), (70, "C"), (60, "D")):
        if score >= threshold:
            return GRADE_COLOURS[grade]
    return GRADE_COLOURS["E"]


@functools.lru_cache(maxsize=4)
def data_uri(filename: str) -> str:
    """A packaged asset as a data URI, so generated HTML needs no files beside it."""
    path = ASSETS / filename
    suffix = {".png": "image/png", ".ico": "image/x-icon", ".svg": "image/svg+xml"}
    mime = suffix.get(path.suffix, "application/octet-stream")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def logo_uri() -> str:
    return data_uri("rittman-analytics.png")


def favicon_uri() -> str:
    return data_uri("favicon.ico")
