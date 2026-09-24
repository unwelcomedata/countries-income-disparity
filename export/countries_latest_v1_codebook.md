# countries-income-disparity — Dataset Codebook
Generated: 2026-09-23

## Columns

### `iso_alpha2`
- **Type**: `str`
- **Non-null**: 216 / 216 (100.0%)
- **Description**: ISO 3166-1 alpha-2 country code (e.g. US).

### `iso_alpha3`
- **Type**: `str`
- **Non-null**: 216 / 216 (100.0%)
- **Description**: ISO 3166-1 alpha-3 country code (e.g. USA).

### `country_name`
- **Type**: `str`
- **Non-null**: 216 / 216 (100.0%)
- **Description**: World Bank country name.

### `region`
- **Type**: `str`
- **Non-null**: 216 / 216 (100.0%)
- **Description**: UN geoscheme region (Africa, Americas, Asia, Europe, Oceania).

### `sub_region`
- **Type**: `str`
- **Non-null**: 216 / 216 (100.0%)
- **Description**: UN geoscheme sub-region (e.g. Sub-Saharan Africa).

### `gini_index`
- **Type**: `float64`
- **Non-null**: 171 / 216 (79.2%)
- **Description**: Gini index of income or consumption, 0-100 (World Bank SI.POV.GINI). Higher = more unequal. SEE gini_welfare_type: income- and consumption-based Ginis are NOT directly comparable (income runs ~4.7 pts higher on average).

### `gini_year`
- **Type**: `float64`
- **Non-null**: 171 / 216 (79.2%)
- **Description**: Year the gini_index value is from (snapshot only). Gini is measured in irregular survey years, so this often lags the other indicators.

### `gini_welfare_type`
- **Type**: `str`
- **Non-null**: 170 / 216 (78.7%)
- **Description**: Whether the Gini is based on an INCOME or CONSUMPTION welfare aggregate (World Bank PIP). NULL if no matching survey. Label/segment rankings by this to avoid mixing methods.

### `population`
- **Type**: `float64`
- **Non-null**: 216 / 216 (100.0%)
- **Description**: Total population (World Bank SP.POP.TOTL).

### `gdp_per_capita_ppp`
- **Type**: `float64`
- **Non-null**: 203 / 216 (94.0%)
- **Description**: GDP per capita, PPP (current international $).

### `gdp_per_capita_nominal`
- **Type**: `float64`
- **Non-null**: 213 / 216 (98.6%)
- **Description**: GDP per capita (current US$).

### `gdp_growth_pct`
- **Type**: `float64`
- **Non-null**: 213 / 216 (98.6%)
- **Description**: GDP growth, annual %.

### `poverty_215_pct`
- **Type**: `float64`
- **Non-null**: 171 / 216 (79.2%)
- **Description**: Poverty headcount ratio at $2.15/day (2017 PPP), % of population.

### `poverty_365_pct`
- **Type**: `float64`
- **Non-null**: 171 / 216 (79.2%)
- **Description**: Poverty headcount ratio at $3.65/day (2017 PPP), % of population.

### `life_expectancy`
- **Type**: `float64`
- **Non-null**: 216 / 216 (100.0%)
- **Description**: Life expectancy at birth, total years.

### `fertility_rate`
- **Type**: `float64`
- **Non-null**: 216 / 216 (100.0%)
- **Description**: Total fertility rate, births per woman.

### `urban_pct`
- **Type**: `float64`
- **Non-null**: 216 / 216 (100.0%)
- **Description**: Urban population, % of total.

### `unemployment_pct`
- **Type**: `float64`
- **Non-null**: 186 / 216 (86.1%)
- **Description**: Unemployment, % of labor force (ILO modeled estimate).

### `inflation_pct`
- **Type**: `float64`
- **Non-null**: 193 / 216 (89.4%)
- **Description**: Inflation, consumer prices, annual %.

### `trade_pct_gdp`
- **Type**: `float64`
- **Non-null**: 194 / 216 (89.8%)
- **Description**: Trade (exports + imports) as % of GDP.

### `internet_pct`
- **Type**: `float64`
- **Non-null**: 213 / 216 (98.6%)
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
