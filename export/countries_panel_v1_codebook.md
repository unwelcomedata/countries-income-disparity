# countries-income-disparity — Dataset Codebook
Generated: 2026-09-23

## Columns

### `iso_alpha2`
- **Type**: `str`
- **Non-null**: 14,256 / 14,256 (100.0%)
- **Description**: ISO 3166-1 alpha-2 country code (e.g. US).

### `iso_alpha3`
- **Type**: `str`
- **Non-null**: 14,256 / 14,256 (100.0%)
- **Description**: ISO 3166-1 alpha-3 country code (e.g. USA).

### `country_name`
- **Type**: `str`
- **Non-null**: 14,256 / 14,256 (100.0%)
- **Description**: World Bank country name.

### `region`
- **Type**: `str`
- **Non-null**: 14,256 / 14,256 (100.0%)
- **Description**: UN geoscheme region (Africa, Americas, Asia, Europe, Oceania).

### `sub_region`
- **Type**: `str`
- **Non-null**: 14,256 / 14,256 (100.0%)
- **Description**: UN geoscheme sub-region (e.g. Sub-Saharan Africa).

### `year`
- **Type**: `int32`
- **Non-null**: 14,256 / 14,256 (100.0%)
- **Description**: Observation year (panel only).

### `population`
- **Type**: `float64`
- **Non-null**: 14,226 / 14,256 (99.8%)
- **Description**: Total population (World Bank SP.POP.TOTL).

### `gdp_per_capita_ppp`
- **Type**: `float64`
- **Non-null**: 7,020 / 14,256 (49.2%)
- **Description**: GDP per capita, PPP (current international $).

### `gdp_per_capita_nominal`
- **Type**: `float64`
- **Non-null**: 11,739 / 14,256 (82.3%)
- **Description**: GDP per capita (current US$).

### `gdp_growth_pct`
- **Type**: `float64`
- **Non-null**: 11,394 / 14,256 (79.9%)
- **Description**: GDP growth, annual %.

### `gini_index`
- **Type**: `float64`
- **Non-null**: 2,430 / 14,256 (17.0%)
- **Description**: Gini index of income or consumption, 0-100 (World Bank SI.POV.GINI). Higher = more unequal. SEE gini_welfare_type: income- and consumption-based Ginis are NOT directly comparable (income runs ~4.7 pts higher on average).

### `gini_welfare_type`
- **Type**: `str`
- **Non-null**: 2,371 / 14,256 (16.6%)
- **Description**: Whether the Gini is based on an INCOME or CONSUMPTION welfare aggregate (World Bank PIP). NULL if no matching survey. Label/segment rankings by this to avoid mixing methods.

### `life_expectancy`
- **Type**: `float64`
- **Non-null**: 14,006 / 14,256 (98.2%)
- **Description**: Life expectancy at birth, total years.

### `fertility_rate`
- **Type**: `float64`
- **Non-null**: 14,008 / 14,256 (98.3%)
- **Description**: Total fertility rate, births per woman.

### `urban_pct`
- **Type**: `float64`
- **Non-null**: 14,256 / 14,256 (100.0%)
- **Description**: Urban population, % of total.

### `unemployment_pct`
- **Type**: `float64`
- **Non-null**: 6,496 / 14,256 (45.6%)
- **Description**: Unemployment, % of labor force (ILO modeled estimate).

### `poverty_215_pct`
- **Type**: `float64`
- **Non-null**: 2,430 / 14,256 (17.0%)
- **Description**: Poverty headcount ratio at $2.15/day (2017 PPP), % of population.

### `poverty_365_pct`
- **Type**: `float64`
- **Non-null**: 2,430 / 14,256 (17.0%)
- **Description**: Poverty headcount ratio at $3.65/day (2017 PPP), % of population.

### `inflation_pct`
- **Type**: `float64`
- **Non-null**: 9,136 / 14,256 (64.1%)
- **Description**: Inflation, consumer prices, annual %.

### `trade_pct_gdp`
- **Type**: `float64`
- **Non-null**: 9,029 / 14,256 (63.3%)
- **Description**: Trade (exports + imports) as % of GDP.

### `internet_pct`
- **Type**: `float64`
- **Non-null**: 6,224 / 14,256 (43.7%)
- **Description**: Individuals using the Internet, % of population.

## Notes

Sources: World Bank World Development Indicators (WDI) API v2 and the World Bank Poverty and
Inequality Platform (PIP); ISO 3166-1 + UN geoscheme regions. License: CC-BY 4.0 (World Bank),
public domain (ISO codes). Compiled and cleaned by @unwelcomedata.
Coverage: 216 countries. World Bank AGGREGATES (World, income groups, regions) are excluded.
Namibia and Kosovo are included (handled explicitly during cleaning). Indicator coverage is
irregular — many country-years are blank, especially Gini (only ~171 countries have any).
CRITICAL Gini caveat: gini_index mixes income-based and consumption-based measures across
countries; these are NOT directly comparable (income ~4.7 pts higher on average). Use
gini_welfare_type to filter or label. See SOURCES.md for full methodology and series breaks.
