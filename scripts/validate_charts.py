#!/usr/bin/env python3
"""Pre-publish data-validation gate for countries-income-disparity (serious tier).

Re-derives, straight from the DuckDB source and the published exports, exactly what
each of the 7 published charts shows, and asserts:

  * export-vs-DB match       — countries_latest export == the latest-snapshot the
                               charts are built from (no drift).
  * headline chart facts     — c1/c4 top/bottom rankings per survey pool; the
                               scatter correlation coefficients the subtitles claim
                               (r ≈ -0.51 income / -0.23 consumption); the four
                               catastrophe low points AT THEIR MARKED YEARS; the US
                               world-rank percentiles.
  * social/web parity        — the two output sets cover the same chart filenames,
                               and every web chart is the web canvas (1664 wide).

Exit 0 + "safe to publish" only if every check passes. Any mismatch exits non-zero.

Run:  .venv/bin/python scripts/validate_charts.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

PROJECT = Path(__file__).resolve().parent.parent
DB = PROJECT / "data" / "project.duckdb"
LATEST_PARQUET = PROJECT / "data" / "processed" / "countries_latest.parquet"
LATEST_EXPORT = PROJECT / "export" / "countries_latest_v1.csv"
SOCIAL = PROJECT / "outputs" / "social"
WEB = PROJECT / "outputs" / "web"

# Published chart PNGs (social); each must have a matching web render.
CHART_NAMES = [
    "c1_most_unequal_by_metric",
    "c4_most_equal_by_metric",
    "c6_wealth_vs_inequality_income",
    "c7_wealth_vs_inequality_consumption",
    "catastrophe_life_expectancy",
    "us_dashboard",
    "us_world_rank",
]
# Web-only browse grids that also live in outputs/web (not posted, but part of the page).
WEB_ONLY = ["browse_fertility", "browse_life_expectancy", "browse_unemployment"]

# Catastrophe panels: (iso2, name, marked year, expected life-exp at that year).
# NOTE: the chart marks the EVENT year (mark_x), which is NOT necessarily the
# series' global minimum — Syria's true min is 1960 (~52.7), but the marked
# civil-war low is 2015. Assert the value at the marked year.
CATASTROPHE = [
    ("KH", "Cambodia", 1977, 11.295),
    ("RW", "Rwanda", 1994, 12.158),
    ("TL", "Timor-Leste", 1978, 22.933),
    ("SY", "Syria", 2015, 63.265),
]

# Expected US world-rank percentiles (100th = highest). Gini ranked vs income pool only.
US_PCT = {
    "gdp_per_capita_ppp": 95.0,
    "gini_index": 79.0,       # vs income-based countries only
    "life_expectancy": 74.0,
    "fertility_rate": 39.0,
    "unemployment_pct": 38.0,
}

# Expected scatter correlations (subtitle claims).
EXPECT_R_INCOME = -0.51
EXPECT_R_CONSUMPTION = -0.23

# Headline ranking facts (country, gini) the charts display, per pool.
C1_CONSUMPTION_TOP3 = [("Namibia", 59.1), ("Botswana", 54.9), ("Eswatini", 54.6)]
C1_INCOME_TOP3 = [("Colombia", 54.4), ("Brazil", 50.3), ("Panama", 49.7)]
C4_CONSUMPTION_BOT3 = [("Belarus", 24.4), ("Kiribati", 24.7), ("India", 25.5)]
C4_INCOME_BOT3 = [("Slovak Republic", 23.8), ("Slovenia", 24.7), ("Czechia", 25.7)]

TOL = 0.05  # tolerance for a value rounded to 1 dp


class Checker:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.passes = 0

    def check(self, ok: bool, msg: str) -> None:
        if ok:
            self.passes += 1
        else:
            self.failures.append(msg)

    def approx(self, got: float, want: float, msg: str, tol: float = TOL) -> None:
        self.check(got is not None and abs(float(got) - want) <= tol,
                   f"{msg}: got {got}, want {want} (±{tol})")


def _rank3(df: pd.DataFrame, ascending: bool) -> list[tuple[str, float]]:
    d = df.nsmallest(3, "gini_index") if ascending else df.nlargest(3, "gini_index")
    return list(zip(d["country_name"], d["gini_index"].round(1)))


def main() -> int:
    c = Checker()
    con = duckdb.connect(str(DB), read_only=True)

    # ---- export-vs-DB: the latest snapshot the charts use == published export ----
    snap = pd.read_parquet(LATEST_PARQUET)
    exp = pd.read_csv(LATEST_EXPORT)
    c.check(len(snap) == len(exp),
            f"latest export row count: parquet {len(snap)} != csv {len(exp)}")
    # Gini values must match between the chart-source parquet and the published CSV.
    j = snap[["iso_alpha3", "gini_index"]].merge(
        exp[["iso_alpha3", "gini_index"]], on="iso_alpha3", suffixes=("_p", "_c"))
    drift = j[(j["gini_index_p"].notna() | j["gini_index_c"].notna())
              & (j["gini_index_p"].fillna(-1) - j["gini_index_c"].fillna(-1)).abs().gt(1e-6)]
    c.check(len(drift) == 0, f"export drift: {len(drift)} Gini values differ parquet vs csv")

    g = snap.dropna(subset=["gini_index"])
    income = g[g["gini_welfare_type"] == "income"]
    consumption = g[g["gini_welfare_type"] == "consumption"]

    # ---- c1 / c4 headline rankings ----
    for label, got, want in [
        ("c1 consumption top3", _rank3(consumption, False), C1_CONSUMPTION_TOP3),
        ("c1 income top3", _rank3(income, False), C1_INCOME_TOP3),
        ("c4 consumption bottom3", _rank3(consumption, True), C4_CONSUMPTION_BOT3),
        ("c4 income bottom3", _rank3(income, True), C4_INCOME_BOT3),
    ]:
        names_ok = [n for n, _ in got] == [n for n, _ in want]
        vals_ok = all(abs(gv - wv) <= TOL for (_, gv), (_, wv) in zip(got, want))
        c.check(names_ok and vals_ok, f"{label}: got {got}, want {want}")

    # ---- scatter correlations (closes the Grok "not independently recomputed" note) ----
    def corr(df: pd.DataFrame) -> float:
        d = df.dropna(subset=["gdp_per_capita_ppp", "gini_index"])
        return round(float(np.corrcoef(d["gdp_per_capita_ppp"], d["gini_index"])[0, 1]), 2)
    c.approx(corr(income), EXPECT_R_INCOME, "c6 income scatter r", tol=0.005)
    c.approx(corr(consumption), EXPECT_R_CONSUMPTION, "c7 consumption scatter r", tol=0.005)

    # ---- catastrophe low points AT MARKED YEARS ----
    for iso2, name, year, want in CATASTROPHE:
        row = con.execute(
            "SELECT life_expectancy FROM countries_clean "
            "WHERE iso_alpha2 = ? AND year = ?", [iso2, year]
        ).fetchone()
        got = row[0] if row else None
        c.approx(got, want, f"catastrophe {name} life-exp @ {year}", tol=0.01)

    # ---- US world-rank percentiles ----
    income_pool = snap[snap["gini_welfare_type"] == "income"]

    def us_pct(col: str, pool: pd.DataFrame | None) -> float | None:
        s = (pool if pool is not None else snap)[col].dropna()
        usv = snap.loc[snap["iso_alpha2"] == "US", col]
        if usv.empty or pd.isna(usv.iloc[0]):
            return None
        return round(100.0 * (s <= usv.iloc[0]).mean(), 0)
    for col, want in US_PCT.items():
        pool = income_pool if col == "gini_index" else None
        c.approx(us_pct(col, pool), want, f"US percentile {col}", tol=0.5)

    con.close()

    # ---- social/web parity ----
    for name in CHART_NAMES:
        sp = SOCIAL / f"{name}.png"
        wp = WEB / f"{name}.png"
        c.check(sp.exists(), f"missing social chart: {sp.name}")
        c.check(wp.exists(), f"missing web chart: {wp.name}")
    for name in WEB_ONLY:
        c.check((WEB / f"{name}.png").exists(), f"missing web-only chart: {name}.png")

    # Every web chart must be the web canvas width (1664). Height varies for the
    # tall dashboard/catastrophe charts, so only the width is fixed.
    try:
        from PIL import Image
        for name in CHART_NAMES + WEB_ONLY:
            wp = WEB / f"{name}.png"
            if wp.exists():
                w, _h = Image.open(wp).size
                c.check(w == 1664, f"web chart {name}: width {w} != 1664")
    except ImportError:
        c.check(False, "Pillow not available to check web canvas dimensions")

    # ---- report ----
    print(f"validate_charts: {c.passes} checks passed, {len(c.failures)} failed")
    if c.failures:
        print("\nFAILURES:")
        for f in c.failures:
            print(f"  - {f}")
        print("\nNOT safe to publish — fix the above (regenerate exports / re-render charts) and re-run.")
        return 1
    print("All chart facts tie back to the DuckDB source; exports match; social/web parity holds.")
    print("safe to publish")
    return 0


if __name__ == "__main__":
    sys.exit(main())
