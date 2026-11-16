"""Synthetic theory-of-change diagrams with known answers, for the import experiment (task 054, 5).

Each diagram is data (boxes with their layer and place, arrows, assumption
notes), drawn to SVG and rendered to PNG with PyMuPDF; the same data is the
answer key. Four, from easy to hard:

1. ``simple``: five boxes in one row, left to right, with column headings.
2. ``columns``: twelve boxes in five headed columns, many-to-many arrows that cross.
3. ``vertical``: bottom-up (impact at the top), dashed assumption notes on arrows.
4. ``messy``: no headings (a colour legend instead), curved arrows, small text,
   a labelled arrow, and two arrows joining before a box.

Run: ``uv run --project ../../../backend python import_diagrams.py`` (writes
``datasets/import_synthetic/<name>.svg|png|json``).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

import fitz  # PyMuPDF

OUT = Path(__file__).parent / "datasets" / "import_synthetic"

COLOURS = {
    "input": "#dbe8f7",
    "output": "#d9f0e6",
    "outcome_short": "#fff1cc",
    "outcome_long": "#ffe0c2",
    "impact": "#f5d5e6",
    "failure_outcome": "#f3d0cb",
}


@dataclass
class Box:
    id: str
    text: str
    layer: str
    x: float
    y: float
    w: float = 170
    h: float = 64


@dataclass
class Diagram:
    name: str
    title: str
    width: int
    height: int
    boxes: list[Box]
    arrows: list[tuple[str, str]]
    headings: list[tuple[str, float]] = field(default_factory=list)  # (text, x centre)
    assumptions: list[tuple[str, tuple[str, str], float, float]] = field(default_factory=list)
    vertical: bool = False
    curved: bool = False
    legend: bool = False
    font: int = 14
    labels: dict[tuple[str, str], str] = field(default_factory=dict)
    merge: tuple[tuple[str, str], str] | None = None  # two sources join, then one arrow


def _wrap(text: str, width: float, font: int) -> list[str]:
    per_line = max(8, int(width / (font * 0.55)))
    lines, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > per_line and line:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return [*lines, line]


def _box_svg(box: Box, font: int) -> str:
    lines = _wrap(box.text, box.w - 12, font)
    top = box.y + box.h / 2 - (len(lines) - 1) * font * 0.6
    spans = "".join(
        f'<tspan x="{box.x + box.w / 2}" y="{top + i * font * 1.2:.1f}">{escape(line)}</tspan>'
        for i, line in enumerate(lines)
    )
    return (
        f'<rect x="{box.x}" y="{box.y}" width="{box.w}" height="{box.h}" rx="8" '
        f'fill="{COLOURS[box.layer]}" stroke="#333" stroke-width="1.2"/>'
        f'<text font-family="Helvetica, Arial" font-size="{font}" text-anchor="middle" '
        f'dominant-baseline="middle" fill="#111">{spans}</text>'
    )


def _ends(a: Box, b: Box, vertical: bool) -> tuple[float, float, float, float]:
    if vertical:  # bottom-up: from the top of a to the bottom of b
        return a.x + a.w / 2, a.y, b.x + b.w / 2, b.y + b.h
    return a.x + a.w, a.y + a.h / 2, b.x, b.y + b.h / 2


def _head(x0: float, y0: float, x2: float, y2: float) -> str:
    """A filled arrowhead at (x2, y2), pointing away from (x0, y0) (PyMuPDF ignores SVG markers)."""
    dx, dy = x2 - x0, y2 - y0
    n = math.hypot(dx, dy) or 1
    ux, uy = dx / n, dy / n
    bx, by = x2 - 11 * ux, y2 - 11 * uy
    return (
        f'<path d="M{x2:.1f},{y2:.1f} L{bx - 5 * uy:.1f},{by + 5 * ux:.1f} '
        f'L{bx + 5 * uy:.1f},{by - 5 * ux:.1f} z" fill="#333"/>'
    )


def render(d: Diagram) -> str:
    by = {b.id: b for b in d.boxes}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{d.width}" height="{d.height}">',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" '
        'orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="#333"/></marker></defs>',
        f'<rect width="{d.width}" height="{d.height}" fill="white"/>',
        f'<text x="{d.width / 2}" y="34" font-family="Helvetica, Arial" font-size="22" '
        f'font-weight="bold" text-anchor="middle">{escape(d.title)}</text>',
    ]
    for text, x in d.headings:
        parts.append(
            f'<text x="{x}" y="72" font-family="Helvetica, Arial" font-size="15" '
            f'font-weight="bold" text-anchor="middle" fill="#1f3a68">{escape(text)}</text>'
        )
    merged = set(d.merge[0]) if d.merge else set()
    for a, b in d.arrows:
        if a in merged and d.merge and b == d.merge[1]:
            continue
        x1, y1, x2, y2 = _ends(by[a], by[b], d.vertical)
        if d.curved:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - 40
            path = f'<path d="M{x1},{y1} Q{mx},{my} {x2},{y2}" '
            parts.append(path + 'fill="none" stroke="#333" stroke-width="1.5"/>' + _head(mx, my, x2, y2))
        else:
            path = f'<path d="M{x1},{y1} L{x2},{y2}" '
            parts.append(path + 'fill="none" stroke="#333" stroke-width="1.5"/>' + _head(x1, y1, x2, y2))
        if (a, b) in d.labels:
            parts.append(
                f'<text x="{(x1 + x2) / 2}" y="{max(y1, y2) + 34}" font-family="Helvetica, Arial" '
                f'font-size="{d.font}" font-style="italic" text-anchor="middle">'
                f"{escape(d.labels[(a, b)])}</text>"
            )
    if d.merge:
        (s1, s2), target = d.merge
        t = by[target]
        jx, jy = t.x - 40, t.y + t.h / 2
        for s in (s1, s2):
            x1, y1, _, _ = _ends(by[s], t, d.vertical)
            parts.append(f'<path d="M{x1},{y1} L{jx},{jy}" fill="none" stroke="#333" stroke-width="1.5"/>')
        parts.append(
            f'<path d="M{jx},{jy} L{t.x},{jy}" fill="none" stroke="#333" stroke-width="1.5"/>'
            + _head(jx, jy, t.x, jy)
        )
    for box in d.boxes:
        parts.append(_box_svg(box, d.font))
    for text, _edge, x, y in d.assumptions:
        lines = _wrap(text, 200, d.font - 2)
        h = 14 + len(lines) * (d.font - 2) * 1.2
        spans = "".join(
            f'<tspan x="{x + 8}" y="{y + 16 + i * (d.font - 2) * 1.2:.1f}">{escape(line)}</tspan>'
            for i, line in enumerate(lines)
        )
        parts.append(
            f'<rect x="{x}" y="{y}" width="215" height="{h:.0f}" fill="#fafafa" stroke="#888" '
            f'stroke-dasharray="5 4"/><text font-family="Helvetica, Arial" font-size="{d.font - 2}" '
            f'fill="#444">{spans}</text>'
        )
    if d.legend:
        names = {
            "input": "Activities",
            "output": "Outputs",
            "outcome_short": "Short-term outcomes",
            "outcome_long": "Long-term outcomes",
            "impact": "Impact",
        }
        for i, (layer, name) in enumerate(names.items()):
            x = 30 + i * 190
            parts.append(
                f'<rect x="{x}" y="{d.height - 40}" width="18" height="18" fill="{COLOURS[layer]}" '
                f'stroke="#333"/><text x="{x + 26}" y="{d.height - 26}" font-family="Helvetica, Arial" '
                f'font-size="13">{name}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)


def diagrams() -> list[Diagram]:
    cols = [110, 330, 550, 770, 990]
    heads = ["Inputs", "Activities", "Outputs", "Outcomes", "Impact"]
    simple = Diagram(
        name="simple",
        title="Minimum unit pricing for alcohol",
        width=1100,
        height=240,
        headings=list(zip(heads, cols, strict=True)),
        boxes=[
            Box("b1", "Legislation sets a 50p minimum price per unit", "input", 25, 110),
            Box("b2", "Retailers reprice cheap, strong alcohol", "input", 245, 110),
            Box("b3", "Cheapest drinks cost more", "output", 465, 110),
            Box("b4", "Heavier drinkers buy fewer units", "outcome_short", 685, 110),
            Box("b5", "Fewer alcohol-related deaths", "impact", 905, 110),
        ],
        arrows=[("b1", "b2"), ("b2", "b3"), ("b3", "b4"), ("b4", "b5")],
    )
    columns = Diagram(
        name="columns",
        title="Restricting less healthy food advertising to children",
        width=1150,
        height=560,
        headings=list(zip(["Inputs", "Outputs", "Short-term outcomes", "Long-term outcomes", "Impact"], [110, 340, 570, 800, 1030], strict=True)),
        boxes=[
            Box("i1", "9pm TV watershed for less healthy food adverts", "input", 25, 110),
            Box("i2", "Ban on paid online adverts for less healthy food", "input", 25, 250),
            Box("i3", "Ofcom guidance and enforcement", "input", 25, 390),
            Box("o1", "Fewer covered adverts shown before 9pm", "output", 255, 140),
            Box("o2", "Fewer paid adverts online", "output", 255, 330),
            Box("s1", "Children see fewer food adverts", "outcome_short", 485, 110),
            Box("s2", "Fewer requests to parents for snacks", "outcome_short", 485, 250),
            Box("s3", "Children eat fewer advert-prompted snacks", "outcome_short", 485, 390),
            Box("l1", "Households buy fewer less healthy products", "outcome_long", 715, 180),
            Box("l2", "Children consume less excess energy", "outcome_long", 715, 350),
            Box("m1", "Fewer children living with obesity", "impact", 945, 260),
            Box("f1", "Marketing moves to influencers", "failure_outcome", 485, 480, 170, 56),
        ],
        arrows=[
            ("i1", "o1"),
            ("i2", "o2"),
            ("i3", "o1"),
            ("i3", "o2"),
            ("o1", "s1"),
            ("o2", "s1"),
            ("s1", "s2"),
            ("s1", "s3"),
            ("s2", "l1"),
            ("s3", "l2"),
            ("l1", "l2"),
            ("l2", "m1"),
            ("o2", "f1"),
        ],
    )
    vertical = Diagram(
        name="vertical",
        title="Changing Futures: support for adults facing multiple disadvantage",
        width=1000,
        height=900,
        vertical=True,
        boxes=[
            Box("m1", "People live safe, stable and fulfilling lives", "impact", 380, 100, 240),
            Box("l1", "Fewer crises and emergency admissions", "outcome_long", 200, 260),
            Box("l2", "Stable housing is sustained", "outcome_long", 520, 260),
            Box("s1", "People trust their keyworker", "outcome_short", 200, 430),
            Box("s2", "Services share plans and information", "outcome_short", 520, 430),
            Box("p1", "Each person has one named keyworker", "output", 200, 600),
            Box("p2", "Local partners agree a joint plan", "output", 520, 600),
            Box("a1", "Fund keyworkers in 15 areas", "input", 200, 770),
            Box("a2", "Bring local services together", "input", 520, 770),
        ],
        arrows=[
            ("a1", "p1"),
            ("a2", "p2"),
            ("p1", "s1"),
            ("p2", "s2"),
            ("s1", "l1"),
            ("s2", "l2"),
            ("s1", "l2"),
            ("l1", "m1"),
            ("l2", "m1"),
        ],
        assumptions=[
            ("Assumption: caseloads stay small enough to build trust", ("p1", "s1"), 15, 520),
            ("Assumption: partners keep funding after the programme", ("p2", "s2"), 760, 520),
        ],
    )
    messy = Diagram(
        name="messy",
        title="School breakfast clubs and attainment",
        width=1180,
        height=520,
        curved=True,
        legend=True,
        font=12,
        boxes=[
            Box("a1", "Fund free breakfast clubs in schools in deprived areas", "input", 20, 150, 160, 70),
            Box("a2", "Train staff to run clubs", "input", 20, 300, 160, 56),
            Box("p1", "Clubs open 8am every school day", "output", 240, 150, 150, 56),
            Box("p2", "More pupils eat breakfast", "output", 240, 300, 150, 56),
            Box("s1", "Pupils arrive on time", "outcome_short", 470, 120, 150, 56),
            Box("s2", "Better concentration in morning lessons", "outcome_short", 470, 260, 150, 64),
            Box("l1", "Attendance rises", "outcome_long", 720, 140, 150, 56),
            Box("l2", "Higher reading and maths progress", "outcome_long", 720, 290, 150, 64),
            Box("m1", "Narrower attainment gap at age 11", "impact", 970, 220, 170, 64),
        ],
        arrows=[
            ("a1", "p1"),
            ("a2", "p1"),
            ("p1", "p2"),
            ("p1", "s1"),
            ("p2", "s2"),
            ("s1", "l1"),
            ("s2", "l2"),
            ("l1", "m1"),
            ("l2", "m1"),
        ],
        labels={("p2", "s2"): "if pupils are hungry at home"},
        merge=(("l1", "l2"), "m1"),
    )
    return [simple, columns, vertical, messy]


def key(d: Diagram) -> dict[str, object]:
    return {
        "title": d.title,
        "boxes": [{"id": b.id, "text": b.text, "layer": b.layer} for b in d.boxes],
        "arrows": [list(a) for a in d.arrows],
        "assumptions": [{"text": t, "on": list(e)} for t, e, _, _ in d.assumptions],
        "arrow_labels": [{"on": list(e), "text": t} for e, t in d.labels.items()],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for d in diagrams():
        svg = render(d)
        (OUT / f"{d.name}.svg").write_text(svg)
        doc = fitz.open(stream=svg.encode(), filetype="svg")
        doc[0].get_pixmap(dpi=110).save(OUT / f"{d.name}.png")
        (OUT / f"{d.name}.json").write_text(json.dumps(key(d), indent=1))
        print(d.name, "ok")


if __name__ == "__main__":
    main()
