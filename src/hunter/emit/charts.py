"""Charts, drawn as inline SVG.

No charting library and no JavaScript. Three reasons, in order of how much they
matter:

1. Every one of these has to render with no network. A report gets opened from
   a build artifact, a laptop with no connection and an email attachment, and a
   chart that silently fails to draw is worse than a table. The model diagrams
   are the one exception on the page: they need Mermaid, they are fetched at a
   pinned version, and they degrade to source text where it does not arrive.
2. The output has to be byte-identical between runs, because the whole site is
   compared against a committed golden file. A library that lays out at draw
   time cannot promise that.
3. Nothing here should read data at view time. The numbers are computed once,
   by rules, and drawn. There is no code path where a chart shows something no
   finding stands behind.

Every function returns a complete ``<svg>`` element. All arithmetic is rounded
to two decimal places, so the same inputs always produce the same string.
"""

from __future__ import annotations

import html
import math
from collections.abc import Sequence
from dataclasses import dataclass

from hunter import brand


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def _f(value: float) -> str:
    """Fixed precision, so two runs never differ by a floating-point tail."""
    return f"{value:.2f}".rstrip("0").rstrip(".") or "0"


@dataclass(frozen=True)
class Slice:
    """One band of a chart."""

    label: str
    value: float
    colour: str
    note: str = ""


# ---------------------------------------------------------------- score ring


def score_ring(score: float, grade: str, *, size: int = 200, label: str = "out of 100") -> str:
    """The headline number, as a ring that fills to the score.

    The ring starts at twelve o'clock and fills clockwise, so a glance at the
    gap tells you what is missing without reading the number.
    """
    radius = size / 2 - 16
    circumference = 2 * math.pi * radius
    filled = circumference * max(0.0, min(100.0, score)) / 100.0
    centre = size / 2
    colour = brand.score_colour(score)

    described = f"Score {_f(score)} out of 100, grade {esc(grade)}"
    return f"""<svg class="ring" viewBox="0 0 {size} {size}" width="{size}"
     height="{size}" role="img" aria-label="{described}">
  <circle cx="{_f(centre)}" cy="{_f(centre)}" r="{_f(radius)}" fill="none"
          stroke="rgba(255,255,255,0.14)" stroke-width="14"/>
  <circle cx="{_f(centre)}" cy="{_f(centre)}" r="{_f(radius)}" fill="none"
          stroke="{colour}" stroke-width="14" stroke-linecap="round"
          stroke-dasharray="{_f(filled)} {_f(circumference - filled)}"
          transform="rotate(-90 {_f(centre)} {_f(centre)})"/>
  <text x="{_f(centre)}" y="{_f(centre - 4)}" class="ring-value"
        text-anchor="middle">{_f(score)}</text>
  <text x="{_f(centre)}" y="{_f(centre + 22)}" class="ring-label"
        text-anchor="middle">{esc(label)}</text>
</svg>"""


# ----------------------------------------------------------- horizontal bars


def bars(
    rows: Sequence[Slice],
    *,
    width: int = 560,
    row_height: int = 40,
    maximum: float | None = None,
    suffix: str = "",
    label_width: int = 210,
) -> str:
    """One bar per row, longest bar meaning most.

    Labels sit outside the bar rather than on it. A label inside a short bar
    either overflows or gets truncated, and a truncated rule name is no use to
    the person who has to fix it. A row's note goes under its label on the left,
    where there is room, rather than beside the figure on the right, where the
    column is only wide enough for the figure itself.
    """
    if not rows:
        return ""
    top = maximum if maximum is not None else max((row.value for row in rows), default=1.0)
    top = top or 1.0
    value_width = 62
    track = width - label_width - value_width
    height = row_height * len(rows)
    has_notes = any(row.note for row in rows)

    parts = [
        f'<svg class="bars" viewBox="0 0 {width} {height}" width="100%" '
        f'height="{height}" role="img">'
    ]
    for index, row in enumerate(rows):
        y = index * row_height
        centre = y + row_height / 2
        label_y = centre + (-1 if has_notes else 4)
        length = max(2.0, track * (row.value / top))
        parts.append(
            f'  <text x="0" y="{_f(label_y)}" class="bar-label">{esc(row.label)}</text>'
            f'\n  <rect x="{label_width}" y="{_f(centre - 9)}" width="{_f(track)}"'
            ' height="18" rx="4" class="bar-track"/>'
            f'\n  <rect x="{label_width}" y="{_f(centre - 9)}" width="{_f(length)}"'
            f' height="18" rx="4" fill="{row.colour}"/>'
            f'\n  <text x="{width}" y="{_f(centre + 4)}" text-anchor="end" '
            f'class="bar-value">{_f(row.value)}{esc(suffix)}</text>'
        )
        if row.note:
            parts.append(
                f'  <text x="0" y="{_f(centre + 12)}" class="bar-note">{esc(row.note)}</text>'
            )
    parts.append("</svg>")
    return "\n".join(parts)


# -------------------------------------------------------------- stacked bar


def stacked(slices: Sequence[Slice], *, width: int = 560, height: int = 26) -> str:
    """Everything in one bar, sized by share. For a mix, not a ranking."""
    total = sum(item.value for item in slices)
    if total <= 0:
        return ""
    parts = [
        f'<svg class="stack" viewBox="0 0 {width} {height}" width="100%" '
        f'height="{height}" role="img" preserveAspectRatio="none">'
    ]
    x = 0.0
    for item in slices:
        span = width * item.value / total
        parts.append(
            f'  <rect x="{_f(x)}" y="0" width="{_f(span)}" height="{height}" '
            f'fill="{item.colour}"><title>{esc(item.label)}: {_f(item.value)}</title></rect>'
        )
        x += span
    parts.append("</svg>")
    return "\n".join(parts)


# -------------------------------------------------------------------- donut


def donut(slices: Sequence[Slice], *, size: int = 190, centre_label: str = "") -> str:
    """Shares of a whole, with a figure in the middle.

    Drawn with dash offsets rather than arc paths, which keeps the arithmetic
    to one multiplication per slice and cannot produce a malformed path.
    """
    total = sum(item.value for item in slices)
    if total <= 0:
        return ""
    radius = size / 2 - 14
    circumference = 2 * math.pi * radius
    centre = size / 2

    parts = [
        f'<svg class="donut" viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img">'
    ]
    offset = 0.0
    for item in slices:
        span = circumference * item.value / total
        parts.append(
            f'  <circle cx="{_f(centre)}" cy="{_f(centre)}" r="{_f(radius)}" fill="none" '
            f'stroke="{item.colour}" stroke-width="22" '
            f'stroke-dasharray="{_f(span)} {_f(circumference - span)}" '
            f'stroke-dashoffset="{_f(-offset)}" '
            f'transform="rotate(-90 {_f(centre)} {_f(centre)})">'
            f"<title>{esc(item.label)}: {_f(item.value)}</title></circle>"
        )
        offset += span
    if centre_label:
        parts.append(
            f'  <text x="{_f(centre)}" y="{_f(centre + 7)}" class="donut-centre" '
            f'text-anchor="middle">{esc(centre_label)}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


# -------------------------------------------------------------------- funnel


def funnel(stages: Sequence[Slice], *, width: int = 620, band: int = 74) -> str:
    """Where things fall out between one stage and the next.

    Each band is a trapezoid narrowing towards the next stage's value, so the
    slope itself is the drop. The drop is also written out, because a slope is
    a feeling and a number is a fact.
    """
    stages = [stage for stage in stages if stage.value >= 0]
    if len(stages) < 2:
        return ""
    top = max(stage.value for stage in stages) or 1.0
    height = band * len(stages)
    centre = width / 2
    min_width = 90.0

    def span(value: float) -> float:
        return max(min_width, (width - 240) * value / top)

    parts = [
        f'<svg class="funnel" viewBox="0 0 {width} {height}" width="100%" '
        f'height="{height}" role="img">'
    ]
    for index, stage in enumerate(stages):
        y = index * band
        this = span(stage.value)
        nxt = span(stages[index + 1].value) if index + 1 < len(stages) else this
        y2 = y + band - 14
        points = " ".join(
            [
                f"{_f(centre - this / 2)},{_f(y)}",
                f"{_f(centre + this / 2)},{_f(y)}",
                f"{_f(centre + nxt / 2)},{_f(y2)}",
                f"{_f(centre - nxt / 2)},{_f(y2)}",
            ]
        )
        parts.append(
            f'  <polygon points="{points}" fill="{stage.colour}" fill-opacity="0.92"/>'
            f'\n  <text x="{_f(centre)}" y="{_f(y + 26)}" class="funnel-value" '
            f'text-anchor="middle">{_f(stage.value)}</text>'
            f'\n  <text x="{_f(centre)}" y="{_f(y + 44)}" class="funnel-label" '
            f'text-anchor="middle">{esc(stage.label)}</text>'
        )
        if index + 1 < len(stages):
            dropped = stage.value - stages[index + 1].value
            if dropped > 0:
                parts.append(
                    f'  <text x="{width - 8}" y="{_f(y2 + 6)}" class="funnel-drop" '
                    f'text-anchor="end">-{_f(dropped)} {esc(stages[index + 1].note)}</text>'
                )
    parts.append("</svg>")
    return "\n".join(parts)


# ----------------------------------------------------------------- heat grid


def heat_grid(cells: Sequence[Slice], *, columns: int = 14, cell: int = 26, gap: int = 4) -> str:
    """One square per rule, shaded by how much of what it checked it passed.

    Seventy-seven rules in one block. The point is the shape of the block: a
    field of green with three red squares is a different repository from an
    even wash of amber, and no table shows that in one look.
    """
    if not cells:
        return ""
    rows = math.ceil(len(cells) / columns)
    width = columns * (cell + gap)
    height = rows * (cell + gap)

    parts = [
        f'<svg class="heat" viewBox="0 0 {width} {height}" width="100%" '
        f'height="{height}" role="img">'
    ]
    for index, item in enumerate(cells):
        x = (index % columns) * (cell + gap)
        y = (index // columns) * (cell + gap)
        parts.append(
            f'  <rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="5" '
            f'fill="{item.colour}"><title>{esc(item.label)}: {esc(item.note)}</title></rect>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


# ------------------------------------------------------------- mini elements


def meter(part: float, whole: float, *, colour: str = brand.PRIMARY, width: int = 120) -> str:
    """A one-line bar for "63 of 63". Sits inline in a table cell."""
    share = 0.0 if whole <= 0 else max(0.0, min(1.0, part / whole))
    return (
        f'<svg class="meter" viewBox="0 0 {width} 8" width="{width}" height="8" '
        f'preserveAspectRatio="none" role="img" aria-label="{_f(part)} of {_f(whole)}">'
        f'<rect x="0" y="0" width="{width}" height="8" rx="4" class="bar-track"/>'
        f'<rect x="0" y="0" width="{_f(width * share)}" height="8" rx="4" fill="{colour}"/>'
        "</svg>"
    )


def legend(slices: Sequence[Slice]) -> str:
    """Swatches and labels. Every chart above needs one, none of them draws it."""
    items = "".join(
        f'<li><span class="swatch" style="background:{item.colour}"></span>'
        f"<b>{esc(item.label)}</b><em>{_f(item.value)}</em></li>"
        for item in slices
    )
    return f'<ul class="legend">{items}</ul>'


# ------------------------------------------------------------- model lanes


@dataclass(frozen=True)
class LaneCell:
    """One entity at one level: present with a name, or absent."""

    present: bool
    name: str = ""
    note: str = ""


@dataclass(frozen=True)
class LaneRow:
    """One entity across every level, in lane order."""

    label: str
    cells: tuple[LaneCell, ...]
    group: str = ""


def model_lanes(
    headings: Sequence[str],
    rows: Sequence[LaneRow],
    *,
    width: int = 1080,
    row_height: int = 34,
    header: int = 40,
) -> str:
    """The same entities drawn at every level, side by side.

    One column per level, one band per entity. A filled box means the entity
    exists at that level; an outlined box means it does not. The connector
    between two columns is the answer to "does this level agree with the next
    one": solid where both sides exist, red and dashed where the left exists
    and the right does not.

    Reading down a column gives the model at that level. Reading across a band
    gives one entity's whole chain, and the break is where the colour changes.
    """
    if not rows or not headings:
        return ""

    lanes = len(headings)
    gap = 56
    lane_width = (width - gap * (lanes - 1)) / lanes
    groups = [row.group for row in rows]
    show_groups = len({group for group in groups if group}) > 1

    height = header
    tops: list[float] = []
    last_group = None
    for row in rows:
        if show_groups and row.group != last_group:
            height += 24
            last_group = row.group
        tops.append(height)
        height += row_height

    parts = [
        f'<svg class="lanes" viewBox="0 0 {width} {_f(height)}" width="100%" '
        f'height="{_f(height)}" role="img">'
    ]

    for index, heading in enumerate(headings):
        x = index * (lane_width + gap)
        parts.append(
            f'  <rect x="{_f(x)}" y="0" width="{_f(lane_width)}" height="{_f(height)}" '
            f'rx="10" class="lane-bed"/>'
            f'\n  <text x="{_f(x + 12)}" y="24" class="lane-head">{esc(heading)}</text>'
        )

    last_group = None
    for row, top in zip(rows, tops, strict=True):
        if show_groups and row.group != last_group:
            last_group = row.group
            parts.append(
                f'  <text x="0" y="{_f(top - 8)}" class="lane-group">'
                f"{esc(row.group.replace('_', ' '))}</text>"
            )
        for index, cell in enumerate(row.cells):
            x = index * (lane_width + gap)
            klass = "lane-box" if cell.present else "lane-box off"
            text_class = "lane-text" if cell.present else "lane-text off"
            shown = cell.name if cell.present else "not here"
            title = f"{row.label}: {esc(headings[index])} — "
            title += esc(cell.note or (cell.name if cell.present else "absent"))
            parts.append(
                f'  <rect x="{_f(x + 6)}" y="{_f(top)}" width="{_f(lane_width - 12)}" '
                f'height="{row_height - 8}" rx="6" class="{klass}">'
                f"<title>{title}</title></rect>"
                f'\n  <text x="{_f(x + 16)}" y="{_f(top + (row_height - 8) / 2)}" '
                f'class="{text_class}">{esc(shown)}</text>'
            )
            if index + 1 < len(row.cells):
                nxt = row.cells[index + 1]
                start = x + lane_width - 6
                end = x + lane_width + gap + 6
                mid = top + (row_height - 8) / 2
                if cell.present and nxt.present:
                    link = "lane-link ok"
                elif cell.present:
                    link = "lane-link broken"
                elif nxt.present:
                    # The right side exists and the left does not, so this
                    # thing appeared without the level above it agreeing to it.
                    link = "lane-link unplanned"
                else:
                    link = "lane-link none"
                parts.append(
                    f'  <line x1="{_f(start)}" y1="{_f(mid)}" x2="{_f(end)}" '
                    f'y2="{_f(mid)}" class="{link}"/>'
                )
    parts.append("</svg>")
    return "\n".join(parts)
