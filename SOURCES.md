# Data Sources — countries-income-disparity

All data used in this project is from authoritative sources. Crowd-edited
references (Wikipedia, etc.) are not used as primary sources.

Document every data source here before ingesting it. Include enough detail
that someone else could independently locate and verify the original data.

---

## Source Template

Copy and fill in for each source. The **How the source collects the data**,
**How the source defines the data**, and **Methodology changes / series breaks**
sections are required — they are what keep our analysis honest and prevent
apples-to-oranges comparisons.

### [Source Name]
- **Publisher:** [Agency, organization, or author]
- **URL:** [Direct link to the file or page]
- **Format:** [CSV | JSON | HTML table | ZIP | PDF | hand-curated]
- **License:** [Public domain | CC0 | CC-BY | proprietary | etc.]
- **Fields used:** [Column names or description of what was extracted]
- **Coverage:** [Geographic scope, date range, or other relevant bounds]
- **How the source collects the data:** [Survey / administrative / model estimate; frame; universe]
- **How the source defines the data:** [Definition; judgment calls]
- **Methodology changes / series breaks:** [Break dates / non-comparable periods]
- **Known controversies / debates:** [Contested choices]
- **Notes:** [Quirks, revisions]
- **Retrieved:** [YYYY-MM-DD]

---

## Sources

### World Bank — World Development Indicators (WDI)
- **Publisher:** The World Bank (compiling national statistical offices, and for poverty/
  inequality its Poverty and Inequality Platform, PIP)
- **URL:** https://api.worldbank.org/v2/country/all/indicator/ (WDI API v2)
- **Format:** JSON (API), loaded as `indicators_long` and pivoted to `countries_annual`
- **License:** CC-BY 4.0
- **Fields used:** country_code, country_name, year, indicator, value (14–15 indicators incl.
  Gini index, GNI/GDP per capita, income-share deciles)
- **Coverage:** All economies, 1960–2025 (indicator availability varies widely by country/year)
- **How the source collects the data:** **A compilation**, not primary collection. The World
  Bank aggregates figures reported by national statistical offices and its own programs.
  The inequality/income indicators are built from **household surveys** (via PIP) — each
  country's survey is run by that country on its own schedule and design.
- **How the source defines the data:**
  - *Gini index* (0–100): distribution of household **income or consumption** per capita.
    **Critical:** high-income countries typically report an **income**-based Gini (after taxes
    and benefits) while most low/middle-income countries report a **consumption**-based Gini.
  - Income-share indicators = share held by decile/quintile of the population.
  - GNI/GDP per capita defined by World Bank national-accounts conventions (current US$, PPP, etc.).
- **Methodology changes / series breaks:**
  - **The single biggest comparability hazard is welfare metric: income-based vs
    consumption-based Gini are NOT directly comparable.** Income Ginis run **~4.7 points higher
    on average** than consumption Ginis (up to ~10 points in some regions), and the gap widens
    over time. Comparing an income-Gini country against a consumption-Gini country overstates
    the first country's inequality purely from method. **Always check the survey type before
    ranking countries.** (Equivalence scales and sub-metric definitions add further, smaller
    non-comparabilities.)
  - Surveys are **irregular** — a country's Gini "for 2015" may actually be its nearest survey
    year; gaps are common. Values are **not annual** despite the year column.
  - The World Bank periodically **revises PIP methodology and rebases** (survey vintages, PPP
    updates such as the 2017→2021 ICP round); figures can shift between WDI editions.
- **Known controversies / debates:** Cross-country Gini comparison is a well-known
  apples-to-oranges trap in the inequality literature precisely because of the income/
  consumption split and differing survey design; this project must footnote the metric type
  on any cross-country chart. Top-income undercoverage in surveys (missing the very rich) is a
  further, widely debated downward bias.
- **Notes:** `indicators_long` is the long form; `countries_annual` is the pivoted wide form.
  `indicator_catalog` maps WB codes to short column names.
- **Retrieved:** 2026-08-27

### ISO 3166-1 Country Codes with UN Geoscheme
- **Publisher:** Compilation of ISO 3166-1 + UN M49 regional codes (lukes/ISO-3166 repo)
- **URL:** https://github.com/lukes/ISO-3166-Countries-with-Regional-Codes
- **Format:** CSV, loaded as `countries`
- **License:** Public domain / CC0
- **Fields used:** alpha-2, alpha-3, numeric, name, region, sub-region, intermediate-region
- **Coverage:** 249 entries (countries + territories)
- **How the source collects the data:** A crosswalk of official ISO country codes joined to
  the UN M49 geoscheme regions. Reference data, not statistical measurement.
- **How the source defines the data:** Standard ISO codes and UN region/sub-region groupings,
  used to join and group the WDI indicators.
- **Methodology changes / series breaks:** ISO codes change rarely (occasional additions/
  renames); region groupings follow the UN geoscheme. No statistical series, no break.
- **Known controversies / debates:** Region groupings are conventions; "territories vs
  countries" boundary is a definitional choice that affects any regional aggregation.
- **Retrieved:** 2026-08-27

### World Bank — Poverty and Inequality Platform (PIP)
- **Publisher:** The World Bank (Poverty and Inequality Platform)
- **URL:** https://api.worldbank.org/pip/v1/pip (PIP API; `country=all&year=all&reporting_level=national&format=json`)
- **Format:** JSON (API), loaded as `pip_inequality`
- **License:** CC-BY 4.0
- **Fields used:** country_code (ISO alpha-3), country_name, reporting_year, reporting_level,
  **welfare_type** (income | consumption), gini (0–1 fraction), gini_pct (×100), mean, median,
  survey_acronym, survey_year, survey_comparability, comparable_spell
- **Coverage:** ~2,500 national survey rows across ~170 countries; earliest surveys 1960s → 2024
- **How the source collects the data:** PIP estimates are computed **directly from national
  household surveys** (income and expenditure / budget surveys), harmonized by the World Bank.
  Each country's survey runs on its own schedule and design.
- **How the source defines the data:** `welfare_type` records whether that survey's welfare
  aggregate is **income** or **consumption** — the flag WDI's `SI.POV.GINI` does not expose.
  `gini` is the Gini of that aggregate as a **0–1 fraction** (multiply by 100 to compare to the
  WDI 0–100 Gini). Rows are per survey year (not annual).
- **Methodology changes / series breaks:** This source EXISTS to resolve the biggest break —
  **income vs consumption Gini are not directly comparable** (income ~4.7 pts higher on average).
  `survey_comparability` / `comparable_spell` flag within-country breaks across survey vintages.
  PPP rebasing (2017→2021 ICP) and periodic PIP revisions shift values across editions.
- **Known controversies / debates:** Same cross-country apples-to-oranges debate as the WDI Gini;
  PIP is the source that lets us label the metric rather than hide it. Top-income undercoverage in
  surveys remains a debated downward bias.
- **Notes:** PIP `gini` × 100 should closely match WDI `SI.POV.GINI` for the same country/survey
  year (both derive from PIP), but they are not guaranteed identical (interpolation, edition).
  We use PIP for the **welfare_type flag**; WDI remains the headline Gini series.
- **Retrieved:** 2026-09-22

### Indicator Code Reference
- **Publisher:** Internal (derived from World Bank indicator metadata)
- **Format:** Internal table (`indicator_catalog`)
- **License:** Public domain
- **Fields used:** WB indicator code → short column name + description
- **How the source collects the data:** Lookup table built from WDI metadata.
- **How the source defines the data:** Documentation aid mapping cryptic WB codes to readable names.
- **Methodology changes / series breaks:** Reference table; no break.
- **Known controversies / debates:** None.
- **Retrieved:** 2026-08-27

---

## Notes on Data Quality

- All source files are saved verbatim to `data/raw/` and never modified.
- Discrepancies between sources should be noted here and resolved explicitly.

### Series breaks & comparability (read before any cross-country ranking)

- **Income-based vs consumption-based Gini are not comparable** (income runs ~4.7 pts higher on
  average). Check and label the welfare metric before comparing/ranking countries.
- **Gini/income surveys are irregular** — the "year" is often the nearest survey year, not annual.
- **PPP rebasing and PIP revisions** shift values across World Bank editions; use one edition.

---

## Source Provenance in DuckDB

Every table in `data/project.duckdb` has a corresponding entry in the
`_sources` metadata table:

```sql
SELECT duckdb_table, source_name, methodology, series_breaks FROM _sources;
```

Alongside `source_name`, `url`, `license`, `notes`, `retrieved`, the table carries
**`methodology`** and **`series_breaks`** so provenance travels with the data.
