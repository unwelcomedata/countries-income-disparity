# Scripts — reproducible pipeline + release tooling

The ingest → clean → prepare pipeline logic lives in **`src/`** (`ingest.py`,
`clean_quality.py`, `prepare.py`), driven by `config.yaml`. **`reproduce.py` is a
standalone entrypoint** that runs that same `src/` logic in order, raw → export, with
one command — it does NOT execute the notebooks (its output is byte-for-byte identical
to the published exports). The numbered notebooks are the author's working record and
call the same `src/` functions.

## Prerequisites

- Python 3.11+ with packages from `requirements.txt` (project `.venv`).
- Network access on the first run — ingest fetches the World Bank WDI + PIP APIs.
  Subsequent runs reuse the cached files in `data/raw/`.

## Reproduce the dataset (raw → export)

```bash
# Full rebuild: fetch World Bank data → clean → export
python scripts/reproduce.py

# Use cached raw files only; fail if any are missing (no network)
python scripts/reproduce.py --no-download

# Dry run to a scratch DB + export dir (leaves the project untouched)
python scripts/reproduce.py --db /tmp/x.duckdb --export-dir /tmp/exp
```

Stages (all inside `reproduce.py`, calling `src/`):

| Stage | Does | Output |
|-------|------|--------|
| Ingest | Fetch WDI (14 indicators) + PIP inequality + ISO/UN regions; pivot to wide annual | DuckDB tables, `data/raw/` |
| Clean | Build `countries_clean` (drop WB aggregates via ISO join, patch Namibia/Kosovo, attach region + per-country Gini welfare type) | DuckDB `countries_clean` |
| Prepare | Build panel + latest snapshot; package `countries_panel_v1` + `countries_latest_v1` (CSV/xlsx/parquet + codebook) | `export/*` |

Charts are rendered from the same cleaned data using the shared Pillow chart factory
(the exploration and publication chart steps live in the project's source repo).

## Pre-publish validation gate (serious tier — required before release)

```bash
# Re-derive every published chart's facts from DuckDB; assert export-vs-DB match,
# the scatter correlations, catastrophe values at marked years, US percentiles,
# and social/web parity. Must print "safe to publish" and exit 0.
python scripts/validate_charts.py
```

## Script descriptions

| Script | Purpose | Inputs | Outputs |
|--------|---------|--------|---------|
| `reproduce.py` | Standalone reproducible entrypoint: run the `src/` ingest→clean→prepare logic raw→export (output byte-identical to the published exports) | `src/`, `config.yaml`, WB API | DuckDB tables, `export/*` |
| `validate_charts.py` | Pre-publish data-validation gate: re-derive each published chart's facts from DuckDB; assert export-vs-DB match + social/web parity | DuckDB, exports, output PNGs | exit 0 + "safe to publish" |
| `build_country_pages.py` | Publish-stage: render web-mode per-country dashboards + a `<select>` picker for GitHub Pages | DuckDB | `docs/countries/*.png`, `docs/countries.html` |
| `build_country_dashboards.py` | Dev-only per-country dashboard review sheet (Gini-only-noise suppressed; CAF life-exp panel suppressed as a data artifact) | DuckDB | `artifacts/country-dashboards/` |

## Conventions

- **Pipeline logic lives in `src/`.** Both `reproduce.py` and the project's notebooks
  call the same `src/` functions, so the reproducible entrypoint and the working record
  can't drift (verified: `reproduce.py` output is byte-identical to the published exports).
- **Only the current export version lives in `export/`.** Tag old versions in git.
- **`build_country_pages.py` reuses `build_country_dashboards.py`** so the published
  dashboards inherit the exact review-stage logic (incl. the CAF suppression).
- **Document new scripts here.**
