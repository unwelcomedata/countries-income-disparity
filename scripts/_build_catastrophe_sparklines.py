"""Compute faithful life-expectancy sparkline geometry for the catastrophe panels
of the countries infographic (tall + social), straight from the real series in
data/project.duckdb, and rewrite the polyline/circle elements in both SVGs.

Every point is value-derived: x = year scaled across the panel x-box, y = life
expectancy scaled (panel min->bottom, panel max->top) within the panel y-box.
The red dot is placed on the ACTUAL marked-year data point (the crisis low shown
in the published chart). No hand-eyeballed coordinates.

Usage: .venv/bin/python scripts/_build_catastrophe_sparklines.py
Then re-render PNGs with scripts/_render_infographic.py.
"""
import re
from pathlib import Path

import duckdb

PROJECT = Path(__file__).resolve().parents[1]
DOCS = PROJECT / "docs"
DB = PROJECT / "data" / "project.duckdb"

# marked crisis year per country (matches the published 04-viz / 06-viz-social chart)
PANELS = [
    ("Cambodia", "Cambodia", 1977),
    ("Rwanda", "Rwanda", 1994),
    ("Timor-Leste", "Timor-Leste", 1978),
    ("Syrian Arab Republic", "Syria", 2015),
]

# Panel geometry per canvas: for each country, the x-box (x_left,x_right) the
# sparkline spans and the y-box (y_top,y_bottom) it maps into. Taken from the
# existing hand-authored panels so layout/spacing is unchanged — only the SHAPE
# becomes data-faithful. Order matches PANELS.
TALL_BOXES = [  # (x_left, x_right, y_top, y_bottom)
    (340, 620, 1430, 1486),   # Cambodia
    (340, 620, 1574, 1630),   # Rwanda
    (340, 620, 1716, 1766),   # Timor-Leste
    (340, 620, 1858, 1906),   # Syria
]
SOCIAL_BOXES = [
    (1030, 1230, 346, 380),   # Cambodia
    (1030, 1230, 402, 436),   # Rwanda
    (1030, 1230, 460, 492),   # Timor-Leste
    (1030, 1230, 520, 544),   # Syria
]


def series(con, entity):
    rows = con.execute(
        "select year, life_expectancy from countries_clean "
        "where country_name=? and life_expectancy is not null order by year",
        [entity],
    ).fetchall()
    return [(int(y), float(v)) for y, v in rows]


def compute(rows, mark_year, box):
    x_left, x_right, y_top, y_bottom = box
    yrs = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    ymin, ymax = min(yrs), max(yrs)
    vmin, vmax = min(vals), max(vals)
    span = (vmax - vmin) or 1.0

    def px(yr):
        return x_left + (yr - ymin) / (ymax - ymin) * (x_right - x_left)

    def py(v):
        # higher life-exp -> higher on canvas (smaller y)
        return y_bottom - (v - vmin) / span * (y_bottom - y_top)

    pts = " ".join(f"{px(yr):.0f},{py(v):.0f}" for yr, v in rows)
    mv = dict(rows)[mark_year]
    dot = (px(mark_year), py(mv))
    return pts, dot


def rewrite(svg_path, boxes):
    text = svg_path.read_text(encoding="utf-8")
    con = duckdb.connect(str(DB), read_only=True)
    try:
        for (entity, label, mark), box in zip(PANELS, boxes):
            rows = series(con, entity)
            pts, (dx, dy) = compute(rows, mark, box)
            # Replace the polyline immediately following this country's name label,
            # and the circle right after it. Anchor on the country label comment.
            # We match the country's <!-- Name --> block's polyline + circle.
            block_re = re.compile(
                r"(<!-- " + re.escape(label) + r" -->.*?<polyline points=\")[^\"]*(\"[^>]*/>\s*<circle cx=\")[^\"]*(\" cy=\")[^\"]*(\")",
                re.DOTALL,
            )
            new_text, n = block_re.subn(
                lambda m: f"{m.group(1)}{pts}{m.group(2)}{dx:.0f}{m.group(3)}{dy:.0f}{m.group(4)}",
                text,
            )
            if n != 1:
                raise SystemExit(f"FAILED to match {label} in {svg_path.name} (matched {n})")
            text = new_text
    finally:
        con.close()
    svg_path.write_text(text, encoding="utf-8")
    print(f"rewrote sparklines in {svg_path.name}")


if __name__ == "__main__":
    rewrite(DOCS / "infographic_countries.svg", TALL_BOXES)
    rewrite(DOCS / "infographic_countries_social.svg", SOCIAL_BOXES)
