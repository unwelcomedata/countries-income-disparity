#!/usr/bin/env python3
"""Reproducible pipeline entrypoint (serious tier): raw -> export, one command.

The canonical pipeline lives in the numbered notebooks (they are the project's
authoritative record). Rather than duplicate that logic in a script — which would
inevitably drift from the notebooks — this entrypoint EXECUTES the pipeline
notebooks in order via nbconvert, so a skeptic can reproduce the published dataset
straight from source with a single command, byte-for-byte faithful to the notebooks.

Stages:
  01-ingest.ipynb   fetch World Bank WDI + PIP + ISO/region -> DuckDB (hits the live
                    World Bank API) + data/raw/
  02-clean.ipynb    build countries_clean in DuckDB (drops WB aggregates, patches
                    Namibia/Kosovo, attaches region + per-country Gini welfare type)
  03-prepare.ipynb  export countries_panel_v1 + countries_latest_v1
                    (CSV/xlsx/parquet + codebook) to export/

After a run, verify with:  python scripts/validate_charts.py

Usage:
  python scripts/reproduce.py               # full raw -> export (re-fetches from WB API)
  python scripts/reproduce.py --from-clean  # skip ingest; start at 02 (raw already loaded)
  python scripts/reproduce.py --kernel NAME # Jupyter kernel to run under (default: cid-venv)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
NOTEBOOKS = PROJECT / "notebooks"

STAGES = [
    ("01-ingest.ipynb", "Ingest — World Bank WDI + PIP + ISO/regions -> DuckDB + data/raw/"),
    ("02-clean.ipynb", "Clean — build countries_clean in DuckDB"),
    ("03-prepare.ipynb", "Prepare — export countries_panel_v1 + countries_latest_v1"),
]


def run_notebook(nb: str, kernel: str, timeout: int) -> None:
    path = NOTEBOOKS / nb
    if not path.exists():
        raise FileNotFoundError(f"missing pipeline notebook: {path}")
    cmd = [
        sys.executable, "-m", "jupyter", "nbconvert",
        "--execute", "--inplace",
        f"--ExecutePreprocessor.kernel_name={kernel}",
        f"--ExecutePreprocessor.timeout={timeout}",
        str(path),
    ]
    print(f"\n>>> {nb}")
    subprocess.run(cmd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Reproduce the raw->export pipeline.")
    ap.add_argument("--from-clean", action="store_true",
                    help="skip 01-ingest (raw already loaded); start at 02-clean")
    ap.add_argument("--kernel", default="cid-venv",
                    help="Jupyter kernel name to execute under (default: cid-venv)")
    ap.add_argument("--timeout", type=int, default=1200,
                    help="per-notebook cell timeout in seconds (default: 1200)")
    args = ap.parse_args()

    stages = STAGES[1:] if args.from_clean else STAGES
    if args.from_clean:
        print("--from-clean: skipping 01-ingest (assuming raw already loaded in DuckDB)")

    for nb, desc in stages:
        print(f"\n=== {desc} ===")
        run_notebook(nb, args.kernel, args.timeout)

    print("\nPipeline complete. Exports written to export/.")
    print("Verify with: python scripts/validate_charts.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
