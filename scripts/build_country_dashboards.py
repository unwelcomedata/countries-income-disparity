#!/usr/bin/env python3
"""Build a per-country metric_dashboard for EVERY country + a review contact sheet.

Dev-only review surface (writes to artifacts/, gitignored) — this is how the owner
reviews all ~216 country dashboards and spots data-quality problems (e.g. the CAR
life-expectancy imputation artifact) BEFORE any per-country dropdown is published.

Outputs (under artifacts/country-dashboards/):
  - <ISO3>.png            one dashboard per country (shared metric_dashboard template)
  - review.html           scrollable contact sheet, flagged countries marked + jump-to-flagged
  - flags.json            {iso3: [flag strings]} from the data-quality scan

Run:  .venv/bin/python scripts/build_country_dashboards.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT.parent.parent / "shared"))

import chart_templates as ct  # noqa: E402
from colors import c  # noqa: E402
from viz import PRESETS  # noqa: E402

OUT = PROJECT / "artifacts" / "country-dashboards"
OUT.mkdir(parents=True, exist_ok=True)
WW, WH, _ = PRESETS["web"]
NAVY = c("navy")
SRC = "World Bank WDI + PIP (survey years vary)  \u00b7  @unwelcomedata"

# The six profile metrics (same as the US dashboard).
METRIC_DEFS = [
    ("life_expectancy", "Life expectancy", "years"),
    ("gdp_per_capita_ppp", "GDP per capita", "PPP int$"),
    ("gini_index", "Income inequality", "Gini"),
    ("fertility_rate", "Fertility rate", "births/woman"),
    ("unemployment_pct", "Unemployment", "% labor force"),
    ("urban_pct", "Urban population", "% of total"),
]


def load() -> tuple[pd.DataFrame, dict, dict]:
    con = duckdb.connect(str(PROJECT / "data" / "project.duckdb"), read_only=True)
    panel = con.execute(
        "SELECT iso_alpha3, country_name, year, life_expectancy, gdp_per_capita_ppp, "
        "gini_index, fertility_rate, unemployment_pct, urban_pct FROM countries_clean"
    ).df()
    # Per-country Gini welfare type (latest) — for the panel unit label.
    welfare = {
        r["country_code"]: r["welfare_type"]
        for _, r in con.execute(
            "SELECT country_code, welfare_type FROM ("
            "  SELECT country_code, welfare_type, row_number() OVER "
            "  (PARTITION BY country_code ORDER BY reporting_year DESC) rn "
            "  FROM pip_inequality WHERE welfare_type IS NOT NULL) WHERE rn=1"
        ).df().iterrows()
    }
    # Per-country Gini comparability break year = start of the 2nd spell.
    breaks = {
        r["country_code"]: int(r["spell_start"])
        for _, r in con.execute(
            "WITH ranked AS (SELECT country_code, min(reporting_year) spell_start, "
            "  row_number() OVER (PARTITION BY country_code ORDER BY min(reporting_year)) rn "
            "  FROM pip_inequality WHERE welfare_type IS NOT NULL "
            "  GROUP BY country_code, comparable_spell) "
            "SELECT country_code, spell_start FROM ranked WHERE rn=2"
        ).df().iterrows()
    }
    con.close()
    return panel, welfare, breaks


# Per-country panel suppressions: (iso3, column) -> short reason.
# These are series that tie back faithfully to the World Bank source but carry
# demographically IMPLAUSIBLE source values (not real events), so plotting the
# line would mislead. We suppress the panel and label WHY rather than show it.
#   CAF (Central African Republic) life expectancy: the WDI series whipsaws
#   between ~50 and impossible lows (2009=14.7, 2019=31.5, 2022=18.8) — a
#   modeling breakdown for a conflict state with weak vital registration, NOT a
#   real demographic event like Rwanda 1994. Confirmed vs raw indicators_long.
SUPPRESS: dict[tuple[str, str], str] = {
    ("CAF", "life_expectancy"): "source values implausible",
}


def metrics_for(iso3: str, sub: pd.DataFrame, welfare: dict, breaks: dict) -> list[dict]:
    """Build the metric config list for one country (fact-based annotations only)."""
    wt = welfare.get(iso3)
    out = []
    for col, name, unit in METRIC_DEFS:
        m = {"col": col, "name": name, "unit": unit}
        if (iso3, col) in SUPPRESS:
            # Blank the series so the template renders the panel as unavailable,
            # and carry the reason in the panel name. The template appends
            # "(no data)", giving e.g. "Life expectancy — suppressed: source
            # values implausible (no data)".
            m["col"] = f"__suppressed__{col}"
            m["name"] = f"{name} — suppressed: {SUPPRESS[(iso3, col)]}"
            sub[m["col"]] = pd.NA
            out.append(m)
            continue
        if col == "gini_index":
            m["unit"] = f"Gini ({wt}-based)" if wt else "Gini"
            # documented survey/comparability break for THIS country
            if iso3 in breaks and sub[col].notna().any():
                yr = breaks[iso3]
                yrs = sub.loc[sub[col].notna(), "year"]
                if yrs.min() < yr < yrs.max():
                    m["breaks"] = [(yr, f"survey change {yr} — pre/post not comparable")]
        if col in ("life_expectancy", "unemployment_pct"):
            # COVID is a universally safe, established marker where 2021/2020 exists.
            yr = 2021 if col == "life_expectancy" else 2020
            if (sub["year"] == yr).any() and sub.loc[sub["year"] == yr, col].notna().any():
                m["annot"] = [(yr, "COVID")]
        out.append(m)
    return out


def scan_flags(iso3: str, sub: pd.DataFrame) -> list[str]:
    """Data-quality heuristics — flag suspicious series for owner review."""
    flags = []
    # implausible single-year swings (imputation artifacts like CAR life-exp)
    plausible_max_yoy = {
        "life_expectancy": 6.0,       # >6yr change in one year is almost always an artifact
        "fertility_rate": 1.0,
        "unemployment_pct": 12.0,
        "urban_pct": 5.0,
    }
    for col, thr in plausible_max_yoy.items():
        if (iso3, col) in SUPPRESS:
            continue  # already adjudicated -> panel suppressed, don't re-flag as noise
        s = sub[["year", col]].dropna().sort_values("year")
        if len(s) >= 2:
            mx = s[col].diff().abs().max()
            if mx > thr:
                flags.append(f"{col}: max 1yr swing {mx:.1f} (> {thr:g})")
    # sparse coverage — metrics with very little data
    sparse = [col for col, _, _ in METRIC_DEFS if sub[col].notna().sum() < 5]
    if sparse:
        flags.append("sparse: " + ", ".join(sparse))
    # no Gini at all
    if sub["gini_index"].notna().sum() == 0:
        flags.append("no Gini data")
    return flags


def is_gini_only(flags: list[str]) -> bool:
    """True if a country is flagged ONLY because Gini data is missing/sparse.

    Missing Gini is acceptable (the dashboard's Gini panel just renders
    "(no data)"), so these countries are noise on the review sheet and are
    suppressed from review.html. A country is Gini-only iff every flag is either
    "no Gini data" or the sparse flag naming *exactly and only* gini_index.
    A sparse flag that also names other columns is NOT Gini-only — it signals
    other missing data worth reviewing.
    """
    if not flags:
        return False
    for f in flags:
        if f == "no Gini data":
            continue
        if f.startswith("sparse:"):
            cols = {c.strip() for c in f[len("sparse:"):].split(",")}
            if cols == {"gini_index"}:
                continue
        return False
    return True


def main() -> None:
    panel, welfare, breaks = load()
    countries = (panel[["iso_alpha3", "country_name"]].dropna()
                 .drop_duplicates().sort_values("country_name"))
    flags_all: dict[str, list[str]] = {}
    cards = []
    print(f"Rendering {len(countries)} country dashboards -> {OUT}")

    for _, row in countries.iterrows():
        iso3, name = row["iso_alpha3"], row["country_name"]
        sub = panel[panel.iso_alpha3 == iso3].copy()
        flags = scan_flags(iso3, sub)
        flags_all[iso3] = flags
        img = ct.metric_dashboard(
            df=sub, metrics=metrics_for(iso3, sub, welfare, breaks),
            title=f"{name} — key metrics over time",
            subtitle="Each panel 0-based (true scale). @unwelcomedata",
            source=SRC, line_color=NAVY, img_width=WW, web_mode=False,
        )
        img.save(OUT / f"{iso3}.png", format="PNG", optimize=True)
        cards.append((iso3, name, flags))

    (OUT / "flags.json").write_text(json.dumps(flags_all, indent=1))

    # Countries flagged ONLY for missing/sparse Gini are acceptable (their Gini
    # panel just shows "(no data)"), so drop them from the review sheet to cut noise.
    review_cards = [(iso3, name, flags) for iso3, name, flags in cards
                    if not is_gini_only(flags)]
    n_suppressed = len(cards) - len(review_cards)
    n_flagged = sum(1 for _, _, f in review_cards if f)
    _write_review_html(review_cards, n_flagged, n_suppressed, len(cards))
    print(f"Done. {len(cards)} dashboards rendered; {n_suppressed} Gini-only "
          f"countries suppressed from review; {len(review_cards)} shown "
          f"({n_flagged} flagged). Open {OUT / 'review.html'}")


def _write_review_html(cards: list[tuple[str, str, list[str]]], n_flagged: int,
                       n_suppressed: int = 0, n_total: int = 0) -> None:
    rows = []
    for iso3, name, flags in cards:
        flagged = bool(flags)
        badge = ("<span class='flag'>\u26a0 " + "; ".join(flags) + "</span>") if flagged else \
                "<span class='ok'>\u2713 no flags</span>"
        rows.append(
            f"<div class='card{' flagged' if flagged else ''}' data-flagged='{int(flagged)}'>"
            f"<h3>{name} <span class='iso'>{iso3}</span></h3>{badge}"
            f"<img loading='lazy' src='{iso3}.png' alt='{name}'></div>"
        )
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Country dashboards — review</title><style>
 body{{font-family:Inter,Helvetica,Arial,sans-serif;margin:0;background:#f6f7f8;color:#1c2530}}
 header{{position:sticky;top:0;background:#003049;color:#fff;padding:14px 20px;z-index:10}}
 header h1{{margin:0;font-size:18px}} header .meta{{font-size:13px;opacity:.85;margin-top:4px}}
 header button{{margin-top:8px;margin-right:8px;padding:6px 12px;border:0;border-radius:5px;cursor:pointer;font-size:13px}}
 .card{{background:#fff;margin:16px 20px;padding:12px 16px;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
 .card.flagged{{border-left:5px solid #EE9B00}}
 .card h3{{margin:0 0 6px;font-size:16px}} .iso{{color:#9aa4ae;font-weight:400;font-size:13px}}
 .flag{{color:#9B2226;font-weight:600;font-size:13px}} .ok{{color:#4a8;font-size:13px}}
 .card img{{width:100%;height:auto;margin-top:8px;border:1px solid #eee;border-radius:4px}}
 body.only-flagged .card:not(.flagged){{display:none}}
</style></head><body>
<header>
 <h1>Country dashboards — review contact sheet</h1>
 <div class="meta">{len(cards)} shown · <b>{n_flagged} flagged</b> for data-quality review · {n_suppressed} Gini-only countries suppressed{f' of {n_total} total' if n_total else ''} · dev-only (artifacts/)</div>
 <button onclick="document.body.classList.toggle('only-flagged')">Toggle: flagged only</button>
</header>
{''.join(rows)}
</body></html>"""
    (OUT / "review.html").write_text(html, encoding="utf-8")


def review_only() -> None:
    """Rebuild review.html from the existing flags.json WITHOUT re-rendering PNGs.

    Use when only the review-sheet logic changed (e.g. the Gini-only suppression
    rule) and the dashboards themselves are unchanged.
    """
    flags_all = json.loads((OUT / "flags.json").read_text())
    # country names come from the panel; load minimally.
    con = duckdb.connect(str(PROJECT / "data" / "project.duckdb"), read_only=True)
    names = {
        r["iso_alpha3"]: r["country_name"]
        for _, r in con.execute(
            "SELECT DISTINCT iso_alpha3, country_name FROM countries_clean "
            "WHERE iso_alpha3 IS NOT NULL"
        ).df().iterrows()
    }
    con.close()
    cards = sorted(
        ((iso3, names.get(iso3, iso3), flags) for iso3, flags in flags_all.items()),
        key=lambda c: c[1],
    )
    review_cards = [(iso3, name, flags) for iso3, name, flags in cards
                    if not is_gini_only(flags)]
    n_suppressed = len(cards) - len(review_cards)
    n_flagged = sum(1 for _, _, f in review_cards if f)
    _write_review_html(review_cards, n_flagged, n_suppressed, len(cards))
    print(f"review.html rebuilt: {n_suppressed} Gini-only suppressed; "
          f"{len(review_cards)} shown ({n_flagged} flagged).")


if __name__ == "__main__":
    if "--review-only" in sys.argv:
        review_only()
    else:
        main()
