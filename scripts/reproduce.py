#!/usr/bin/env python
"""Reproduce the countries-income-disparity published dataset from raw sources.

Serious-tier reproducibility entrypoint: a single command that goes from the World
Bank WDI + PIP APIs and the ISO/UN region crosswalk all the way to the published
exports in ``export/`` — the same ``countries_latest_v1`` / ``countries_panel_v1``
CSV + codebook the release is built on. It runs the exact same ``src/`` logic the
notebooks use, in the documented pipeline order (ingest -> clean -> prepare), and is
fully standalone (it does NOT execute the notebooks).

What it does, in order:
  1. INGEST  — fetch the ISO/UN region crosswalk, the 14 World Bank WDI indicators,
               and the PIP welfare-type/Gini table (into data/raw/ + DuckDB).
  2. CLEAN   — pivot WDI to a wide annual table, drop World Bank AGGREGATES via the
               ISO join, patch Namibia (NA) + Kosovo (XK), attach region/sub-region,
               and label each Gini income- vs consumption-based from PIP ->
               ``countries_clean``.
  3. PREPARE — build the full country x year panel and the latest-per-country
               snapshot, and package both exports (CSV + Excel + Parquet + codebook).

Usage:
    python scripts/reproduce.py                # full run: raw -> export (hits WB API)
    python scripts/reproduce.py --no-download   # fail instead of fetching missing raw files
    python scripts/reproduce.py --db /tmp/x.duckdb --export-dir /tmp/exp  # scratch run

Prerequisites:
  - Python 3.11+ with the packages in requirements.txt.
  - Network access on the first run (to fetch the World Bank APIs). Subsequent runs
    reuse the cached files in data/raw/.

Verify afterwards with:  python scripts/validate_charts.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from src.ingest import (  # noqa: E402
    load_config,
    ingest_iso_countries,
    ingest_world_bank_all,
    ingest_pip,
)
from src.clean_quality import (  # noqa: E402
    get_connection,
    load_to_duckdb,
    run_sql,
    register_source,
)
from src.prepare import package_dataset  # noqa: E402

# Short readable names for the WB indicator codes (matches 01-ingest).
SHORT = {
    "SP.POP.TOTL": "population", "NY.GDP.PCAP.PP.CD": "gdp_per_capita_ppp",
    "NY.GDP.PCAP.CD": "gdp_per_capita_nominal", "NY.GDP.MKTP.KD.ZG": "gdp_growth_pct",
    "SI.POV.GINI": "gini_index", "SP.DYN.LE00.IN": "life_expectancy",
    "SP.DYN.TFRT.IN": "fertility_rate", "SP.URB.TOTL.IN.ZS": "urban_pct",
    "SL.UEM.TOTL.ZS": "unemployment_pct", "SI.POV.DDAY": "poverty_215_pct",
    "SI.POV.LMIC": "poverty_365_pct", "FP.CPI.TOTL.ZG": "inflation_pct",
    "NE.TRD.GNFS.ZS": "trade_pct_gdp", "IT.NET.USER.ZS": "internet_pct",
    "EN.ATM.CO2E.PC": "co2_per_capita",
}

# Export rounding (values unchanged in meaning) — matches 03-prepare.
ROUND = {
    "gdp_per_capita_ppp": 0, "gdp_per_capita_nominal": 0, "population": 0,
    "gdp_growth_pct": 2, "gini_index": 1, "life_expectancy": 1, "fertility_rate": 2,
    "urban_pct": 1, "unemployment_pct": 2, "poverty_215_pct": 1, "poverty_365_pct": 1,
    "inflation_pct": 2, "trade_pct_gdp": 1, "internet_pct": 1,
}

CODEBOOK = {
    "iso_alpha2": "ISO 3166-1 alpha-2 country code (e.g. US).",
    "iso_alpha3": "ISO 3166-1 alpha-3 country code (e.g. USA).",
    "country_name": "World Bank country name.",
    "region": "UN geoscheme region (Africa, Americas, Asia, Europe, Oceania).",
    "sub_region": "UN geoscheme sub-region (e.g. Sub-Saharan Africa).",
    "year": "Observation year (panel only).",
    "gini_index": "Gini index of income or consumption, 0-100 (World Bank SI.POV.GINI). "
                  "Higher = more unequal. SEE gini_welfare_type: income- and consumption-based "
                  "Ginis are NOT directly comparable (income runs ~4.7 pts higher on average).",
    "gini_year": "Year the gini_index value is from (snapshot only). Gini is measured in irregular "
                 "survey years, so this often lags the other indicators.",
    "gini_welfare_type": "Whether the Gini is based on an INCOME or CONSUMPTION welfare aggregate "
                         "(World Bank PIP). NULL if no matching survey. Label/segment rankings by "
                         "this to avoid mixing methods.",
    "population": "Total population (World Bank SP.POP.TOTL).",
    "gdp_per_capita_ppp": "GDP per capita, PPP (current international $).",
    "gdp_per_capita_nominal": "GDP per capita (current US$).",
    "gdp_growth_pct": "GDP growth, annual %.",
    "poverty_215_pct": "Poverty headcount ratio at $2.15/day (2017 PPP), % of population.",
    "poverty_365_pct": "Poverty headcount ratio at $3.65/day (2017 PPP), % of population.",
    "life_expectancy": "Life expectancy at birth, total years.",
    "fertility_rate": "Total fertility rate, births per woman.",
    "urban_pct": "Urban population, % of total.",
    "unemployment_pct": "Unemployment, % of labor force (ILO modeled estimate).",
    "inflation_pct": "Inflation, consumer prices, annual %.",
    "trade_pct_gdp": "Trade (exports + imports) as % of GDP.",
    "internet_pct": "Individuals using the Internet, % of population.",
}

NOTES = """
Sources: World Bank World Development Indicators (WDI) API v2 and the World Bank Poverty and
Inequality Platform (PIP); ISO 3166-1 + UN geoscheme regions. License: CC-BY 4.0 (World Bank),
public domain (ISO codes). Compiled and cleaned by @unwelcomedata.
Coverage: 216 countries. World Bank AGGREGATES (World, income groups, regions) are excluded.
Namibia and Kosovo are included (handled explicitly during cleaning). Indicator coverage is
irregular — many country-years are blank, especially Gini (only ~171 countries have any).
CRITICAL Gini caveat: gini_index mixes income-based and consumption-based measures across
countries; these are NOT directly comparable (income ~4.7 pts higher on average). Use
gini_welfare_type to filter or label. See SOURCES.md for full methodology and series breaks.
"""

LATEST_INDICATORS = [
    "gdp_per_capita_ppp", "gdp_per_capita_nominal", "gdp_growth_pct", "life_expectancy",
    "fertility_rate", "urban_pct", "unemployment_pct", "poverty_215_pct", "poverty_365_pct",
    "inflation_pct", "trade_pct_gdp", "internet_pct", "population",
]
LATEST_COL_ORDER = [
    "iso_alpha2", "iso_alpha3", "country_name", "region", "sub_region",
    "gini_index", "gini_year", "gini_welfare_type", "population",
    "gdp_per_capita_ppp", "gdp_per_capita_nominal", "gdp_growth_pct",
    "poverty_215_pct", "poverty_365_pct", "life_expectancy", "fertility_rate",
    "urban_pct", "unemployment_pct", "inflation_pct", "trade_pct_gdp", "internet_pct",
]


def _rule(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


# ---------------------------------------------------------------------------
# 1. INGEST — fetch + load raw sources into DuckDB
# ---------------------------------------------------------------------------

def step_ingest(cfg: dict, con, allow_download: bool) -> None:
    skip = not allow_download  # skip_existing True means "use cached, don't re-fetch"

    df_iso = ingest_iso_countries(cfg, skip_existing=True)
    load_to_duckdb(df_iso, "countries", con)
    register_source(
        con, "countries", name="ISO 3166-1 Country Codes with UN Geoscheme",
        url="https://github.com/lukes/ISO-3166-Countries-with-Regional-Codes",
        license="Public domain / CC0", retrieved="2026-08-27",
        notes="alpha-2/3, name, UN region/sub-region. Join key to WDI = alpha_2.",
        methodology="ISO 3166-1 codes joined to the UN M49 geoscheme regions.",
        series_breaks="None — reference table.",
    )
    print(f"countries: {len(df_iso):,} rows")

    df_long = ingest_world_bank_all(cfg, skip_existing=True)
    load_to_duckdb(df_long, "indicators_long", con)
    register_source(
        con, "indicators_long", name="World Bank WDI (14 indicators)",
        url="https://api.worldbank.org/v2/country/all/indicator/", license="CC-BY 4.0",
        retrieved="2026-08-27",
        notes="Long form: one row per country_code x year x indicator. Includes WB aggregates "
              "(separated in cleaning via the ISO join).",
        methodology="A compilation of nationally reported figures; inequality via PIP household surveys.",
        series_breaks="Income- vs consumption-based Gini not comparable; irregular surveys; PPP rebasing.",
    )
    print(f"indicators_long: {len(df_long):,} rows, {df_long['indicator'].nunique()} indicators")

    df_pip = ingest_pip(cfg, skip_existing=True)
    load_to_duckdb(df_pip, "pip_inequality", con)
    register_source(
        con, "pip_inequality", name="World Bank Poverty & Inequality Platform (PIP) — welfare metric",
        url="https://api.worldbank.org/pip/v1/pip", license="CC-BY 4.0", retrieved="2026-09-22",
        notes="welfare_type = income|consumption (the flag WDI SI.POV.GINI does not expose); "
              "gini is a 0-1 fraction, gini_pct = gini*100.",
        methodology="Estimated directly from national household surveys, harmonized by the World Bank.",
        series_breaks="Exists to resolve the income-vs-consumption break; comparable_spell flags vintage breaks.",
    )
    print(f"pip_inequality: {len(df_pip):,} rows, {df_pip.country_code.nunique()} countries")

    # indicator catalog (WB code -> short name) from config
    cat = pd.DataFrame(
        [{"indicator_code": i["code"], "column_name": SHORT[i["code"]], "description": i["name"]}
         for i in cfg["sources"]["world_bank"]["indicators"]]
    )
    load_to_duckdb(cat, "indicator_catalog", con)
    register_source(
        con, "indicator_catalog", name="Indicator Code Reference", license="Public domain",
        retrieved="2026-08-27", notes="Maps WB indicator codes to readable column names.",
        methodology="Lookup table derived from WDI metadata + config.yaml.",
        series_breaks="Reference table; no break.",
    )

    # pivot long -> wide annual (still raw: includes WB aggregates)
    code_to_col = dict(zip(cat["indicator_code"], cat["column_name"]))
    wide = (df_long
            .assign(column_name=lambda d: d["indicator"].map(code_to_col))
            .pivot_table(index=["country_code", "country_name", "year"],
                         columns="column_name", values="value", aggfunc="first")
            .reset_index())
    wide.columns.name = None
    load_to_duckdb(wide, "countries_annual", con)
    register_source(
        con, "countries_annual", name="World Bank Indicators (wide format)",
        url="https://api.worldbank.org/v2/country/all/indicator/", license="CC-BY 4.0",
        retrieved="2026-08-27",
        notes="Pivoted wide form of indicators_long; still raw (WB aggregates included).",
        methodology="Pivot of indicators_long; no transformation of values.",
        series_breaks="Inherits indicators_long breaks.",
    )
    print(f"countries_annual: {len(wide):,} rows, years {wide.year.min()}-{wide.year.max()}")


# ---------------------------------------------------------------------------
# 2. CLEAN — build countries_clean (drop aggregates, patch NA/XK, label welfare)
# ---------------------------------------------------------------------------

def step_clean(cfg: dict, con) -> pd.DataFrame:
    con.execute("DROP TABLE IF EXISTS region_xwalk")
    con.execute("""
      CREATE TABLE region_xwalk AS
      WITH base AS (
        SELECT CASE WHEN alpha_3 = 'NAM' THEN 'NA' ELSE alpha_2 END AS alpha_2,
               alpha_3, name AS iso_name, region, sub_region
        FROM countries WHERE region IS NOT NULL
      )
      SELECT * FROM base
      UNION ALL
      SELECT 'XK', 'XKX', 'Kosovo', 'Europe', 'Southern Europe'
    """)

    con.execute("DROP VIEW IF EXISTS _countries_geo")
    con.execute("""
      CREATE TEMP VIEW _countries_geo AS
      SELECT ca.country_code AS iso_alpha2, x.alpha_3 AS iso_alpha3, ca.country_name,
             x.region, x.sub_region, CAST(ca.year AS INTEGER) AS year,
             ca.population, ca.gdp_per_capita_ppp, ca.gdp_per_capita_nominal, ca.gdp_growth_pct,
             ca.gini_index, ca.life_expectancy, ca.fertility_rate, ca.urban_pct,
             ca.unemployment_pct, ca.poverty_215_pct, ca.poverty_365_pct,
             ca.inflation_pct, ca.trade_pct_gdp, ca.internet_pct
      FROM countries_annual ca
      JOIN region_xwalk x ON ca.country_code = x.alpha_2
    """)

    df_clean = run_sql("""
      WITH pip_nat AS (
        SELECT country_code, reporting_year, welfare_type, gini_pct
        FROM pip_inequality WHERE welfare_type IS NOT NULL AND gini_pct IS NOT NULL
      ),
      matched AS (
        SELECT g.iso_alpha3, g.year, p.welfare_type,
               ROW_NUMBER() OVER (PARTITION BY g.iso_alpha3, g.year
                                  ORDER BY abs(g.gini_index - p.gini_pct)) AS rn
        FROM _countries_geo g
        JOIN pip_nat p ON g.iso_alpha3 = p.country_code AND g.year = p.reporting_year
        WHERE g.gini_index IS NOT NULL
      ),
      welfare AS (SELECT iso_alpha3, year, welfare_type FROM matched WHERE rn = 1)
      SELECT g.iso_alpha2, g.iso_alpha3, g.country_name, g.region, g.sub_region, g.year,
             g.population, g.gdp_per_capita_ppp, g.gdp_per_capita_nominal, g.gdp_growth_pct,
             g.gini_index, w.welfare_type AS gini_welfare_type,
             g.life_expectancy, g.fertility_rate, g.urban_pct, g.unemployment_pct,
             g.poverty_215_pct, g.poverty_365_pct, g.inflation_pct, g.trade_pct_gdp, g.internet_pct
      FROM _countries_geo g
      LEFT JOIN welfare w ON g.iso_alpha3 = w.iso_alpha3 AND g.year = w.year
      ORDER BY g.country_name, g.year
    """, con)

    # integrity: no aggregates leaked; Namibia + Kosovo retained
    codes = set(df_clean["iso_alpha2"])
    aggregates = {"1W", "1A", "EU", "XC", "XD", "OE", "Z4", "Z7", "ZG", "ZJ", "XU", "XM", "XP", "XT", "XN", "ZT"}
    assert not (codes & aggregates), f"aggregates leaked: {codes & aggregates}"
    for cc, nm in [("NA", "Namibia"), ("XK", "Kosovo")]:
        assert (df_clean["iso_alpha2"] == cc).any(), f"{nm} ({cc}) missing from clean data"

    con.execute("DROP TABLE IF EXISTS countries_clean")
    con.execute("CREATE TABLE countries_clean AS SELECT * FROM df_clean")
    register_source(
        con, "countries_clean", name="Country-level WDI panel (cleaned, welfare-flagged)",
        url="https://api.worldbank.org/v2/country/all/indicator/", license="CC-BY 4.0",
        retrieved="2026-09-22",
        notes="countries_annual filtered to real countries (ISO join), WB aggregates dropped, "
              "region attached, Namibia/Kosovo patched, gini_welfare_type attached from PIP.",
        methodology="ISO alpha_2 join (patched) + UN geoscheme region; welfare metric from PIP "
                    "joined on alpha-3 + year, disambiguated by closest-gini match.",
        series_breaks="Income vs consumption Gini not comparable; gini_welfare_type lets you segment. "
                      "Surveys irregular; PPP rebasing shifts values.",
    )
    print(f"countries_clean: {len(df_clean):,} rows, {df_clean.iso_alpha2.nunique()} countries")
    return df_clean


# ---------------------------------------------------------------------------
# 3. PREPARE — panel + latest snapshot, then package exports
# ---------------------------------------------------------------------------

def step_prepare(cfg: dict, con) -> None:
    panel = con.execute("SELECT * FROM countries_clean ORDER BY country_name, year").df()
    for col, nd in ROUND.items():
        panel[col] = panel[col].round(nd)

    latest = con.execute("""
        SELECT DISTINCT iso_alpha2, iso_alpha3, country_name, region, sub_region
        FROM countries_clean
    """).df()
    gini_latest = con.execute("""
        SELECT iso_alpha2, gini_index, year AS gini_year, gini_welfare_type
        FROM (SELECT iso_alpha2, gini_index, year, gini_welfare_type,
                     row_number() OVER (PARTITION BY iso_alpha2 ORDER BY year DESC) rn
              FROM countries_clean WHERE gini_index IS NOT NULL) WHERE rn = 1
    """).df()
    latest = latest.merge(gini_latest, on="iso_alpha2", how="left")
    for col in LATEST_INDICATORS:
        one = con.execute(f"""
            SELECT iso_alpha2, {col} FROM (
              SELECT iso_alpha2, {col},
                     row_number() OVER (PARTITION BY iso_alpha2 ORDER BY year DESC) rn
              FROM countries_clean WHERE {col} IS NOT NULL) WHERE rn = 1
        """).df()
        latest = latest.merge(one, on="iso_alpha2", how="left")
    for col, nd in ROUND.items():
        if col in latest.columns:
            latest[col] = latest[col].round(nd)
    latest = latest[LATEST_COL_ORDER].sort_values("country_name").reset_index(drop=True)

    assert latest["iso_alpha2"].is_unique, "latest snapshot has duplicate countries"
    assert (latest["gini_index"].notna() == latest["gini_year"].notna()).all(), "gini without gini_year"

    package_dataset(panel, cfg, name="countries_panel_v1", codebook=CODEBOOK, notes=NOTES)
    package_dataset(latest, cfg, name="countries_latest_v1", codebook=CODEBOOK, notes=NOTES)
    print(f"exported: countries_panel_v1 ({len(panel):,} rows), "
          f"countries_latest_v1 ({len(latest):,} countries)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Reproduce the raw->export pipeline (standalone).")
    ap.add_argument("--no-download", action="store_true",
                    help="fail instead of fetching missing raw files (use cached data/raw/)")
    ap.add_argument("--db", default=None, help="DuckDB path (default: config paths.database)")
    ap.add_argument("--export-dir", default=None, help="export dir (default: export/)")
    args = ap.parse_args()

    cfg = load_config("config.yaml")
    if args.db:
        cfg.setdefault("settings", {})["duckdb_file"] = args.db
    if args.export_dir:
        cfg.setdefault("paths", {})["export"] = args.export_dir
    con = get_connection(cfg)
    try:
        _rule("1. INGEST — World Bank WDI + PIP + ISO/UN regions")
        step_ingest(cfg, con, allow_download=not args.no_download)
        _rule("2. CLEAN — build countries_clean")
        step_clean(cfg, con)
        _rule("3. PREPARE — panel + latest snapshot -> export")
        step_prepare(cfg, con)
    finally:
        con.close()

    print("\nPipeline complete. Exports written to export/.")
    print("Verify with: python scripts/validate_charts.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
