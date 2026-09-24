# Scripts — reproducible pipeline + release tooling

The canonical pipeline lives in the numbered **notebooks** (`notebooks/01-ingest` →
`03-prepare`), which are the project's authoritative record. `reproduce.py` runs them
in order so the published dataset can be rebuilt raw → export with one command,
without drifting from the notebooks.

## Prerequisites

- Python 3.11+ with packages from `requirements.txt` (project `.venv`).
- A registered Jupyter kernel for the venv (default name `cid-venv`).
- Network access for a full run — `01-ingest` fetches the World Bank WDI + PIP APIs.
  (Use `--from-clean` to skip ingest when the raw data is already loaded in DuckDB.)

## Reproduce the dataset (raw → export)

```bash
# Full rebuild: fetch World Bank data → clean → export (hits the WB API)
python scripts/reproduce.py

# Skip ingest, start at cleaning (raw already loaded in data/project.duckdb)
python scripts/reproduce.py --from-clean
```

Stages (each is a notebook `reproduce.py` executes):

| Stage | Notebook | Does | Output |
|-------|----------|------|--------|
| Ingest | `01-ingest.ipynb` | Fetch WDI (14 indicators) + PIP inequality + ISO/UN regions → DuckDB | DuckDB tables, `data/raw/` |
| Clean | `02-clean.ipynb` | Build `countries_clean` (drop WB aggregates, patch Namibia/Kosovo, attach region + per-country Gini welfare type) | DuckDB `countries_clean` |
| Prepare | `03-prepare.ipynb` | Export `countries_panel_v1` + `countries_latest_v1` (CSV/xlsx/parquet + codebook) | `export/*` |

Charts are rendered by `notebooks/04-viz` (exploration) and `06-viz-social`
(publication social + web), using the shared Pillow chart factory.

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
| `reproduce.py` | Reproducible entrypoint: run the pipeline notebooks 01→03 in order (`--from-clean` skips ingest) | notebooks, WB API | DuckDB tables, `export/*` |
| `validate_charts.py` | Pre-publish data-validation gate: re-derive each published chart's facts from DuckDB; assert export-vs-DB match + social/web parity | DuckDB, exports, output PNGs | exit 0 + "safe to publish" |
| `build_country_pages.py` | Publish-stage: render web-mode per-country dashboards + a `<select>` picker for GitHub Pages | DuckDB | `docs/countries/*.png`, `docs/countries.html` |
| `build_country_dashboards.py` | Dev-only per-country dashboard review sheet (Gini-only-noise suppressed; CAF life-exp panel suppressed as a data artifact) | DuckDB | `artifacts/country-dashboards/` |

## Conventions

- **The notebooks are the pipeline.** Scripts orchestrate or validate them; they do
  not re-implement pipeline logic (that would drift from the canonical record).
- **Only the current export version lives in `export/`.** Tag old versions in git.
- **`build_country_pages.py` reuses `build_country_dashboards.py`** so the published
  dashboards inherit the exact review-stage logic (incl. the CAF suppression).
- **Document new scripts here.**
