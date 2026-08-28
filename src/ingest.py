"""Web ingestion utilities.

Handles three source types:
  - html_table  : pandas read_html on a static page
  - html_scrape : BeautifulSoup for custom element extraction
  - csv / json  : direct download and save to data/raw

All raw files land in data/raw unchanged. Call load_config() once per notebook
to get paths and source definitions from config.yaml.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yaml
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config(config_path: str | Path = "config.yaml") -> dict[str, Any]:
    """Load project config.yaml and return it as a dict."""
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def raw_path(cfg: dict, filename: str) -> Path:
    """Return a Path inside data/raw, creating the directory if needed."""
    p = Path(cfg["paths"]["data_raw"]) / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_CACHE_DIR: Path | None = None


def _get_cache_dir(cfg: dict) -> Path:
    """Return the cache directory (data/raw by default)."""
    global _CACHE_DIR
    if _CACHE_DIR is None:
        _CACHE_DIR = Path(cfg["paths"]["data_raw"])
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR


def fetch_html(url: str, headers: dict | None = None, timeout: int = 30) -> str:
    """Fetch a URL and return the response text.

    Raises requests.HTTPError on non-2xx status.
    """
    hdrs = {**_DEFAULT_HEADERS, **(headers or {})}
    resp = requests.get(url, headers=hdrs, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def fetch_cached(
    url: str,
    filename: str,
    cfg: dict,
    max_age_hours: float = 24.0,
    headers: dict | None = None,
    timeout: int = 30,
) -> str:
    """Fetch a URL with local file caching.

    If a cached file exists and is younger than max_age_hours, returns its
    contents without making a network request. Otherwise fetches, saves to
    data/raw/{filename}, and returns the content.

    Args:
        url:            URL to fetch.
        filename:       Cache filename (saved in data/raw/).
        cfg:            Loaded config dict.
        max_age_hours:  Re-fetch if cache is older than this (0 = always fetch).
        headers:        Optional extra HTTP headers.
        timeout:        Request timeout in seconds.

    Returns:
        Response text (from cache or network).
    """
    cache_path = _get_cache_dir(cfg) / filename
    if cache_path.exists() and max_age_hours > 0:
        age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
        if age_hours < max_age_hours:
            return cache_path.read_text(encoding="utf-8")

    text = fetch_html(url, headers=headers, timeout=timeout)
    cache_path.write_text(text, encoding="utf-8")
    return text


def fetch_with_retry(
    url: str,
    headers: dict | None = None,
    timeout: int = 30,
    max_retries: int = 3,
    rate_limit_seconds: float = 1.5,
) -> str:
    """Fetch a URL with rate limiting and exponential backoff on 429s.

    Args:
        url:                 URL to fetch.
        headers:             Optional extra HTTP headers.
        timeout:             Request timeout in seconds.
        max_retries:         Max retry attempts on 429/5xx.
        rate_limit_seconds:  Minimum delay between requests.

    Returns:
        Response text.

    Raises:
        requests.HTTPError after exhausting retries.
    """
    hdrs = {**_DEFAULT_HEADERS, **(headers or {})}
    time.sleep(rate_limit_seconds)

    for attempt in range(max_retries + 1):
        resp = requests.get(url, headers=hdrs, timeout=timeout)
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt < max_retries:
                wait = rate_limit_seconds * (2 ** attempt)
                print(f"  ⚠ {resp.status_code} on {url} — retrying in {wait:.0f}s")
                time.sleep(wait)
                continue
        resp.raise_for_status()
        return resp.text

    resp.raise_for_status()  # will raise on the last failed attempt
    return ""  # unreachable


def fetch_html_js(url: str, wait_selector: str | None = None, timeout: int = 30000) -> str:
    """Fetch a JS-rendered page using Playwright (headless Chromium).

    Use this when fetch_html() returns an empty or incomplete page.
    Requires: playwright install chromium

    Args:
        url:           Page URL.
        wait_selector: Optional CSS selector to wait for before returning HTML.
        timeout:       Playwright timeout in milliseconds.
    """
    from playwright.sync_api import sync_playwright  # lazy import

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(extra_http_headers=_DEFAULT_HEADERS)
        page.goto(url, timeout=timeout)
        if wait_selector:
            page.wait_for_selector(wait_selector, timeout=timeout)
        else:
            page.wait_for_load_state("networkidle", timeout=timeout)
        html = page.content()
        browser.close()
    return html


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_html_table(html: str, table_index: int = 0) -> pd.DataFrame:
    """Extract a <table> from HTML by index and return it as a DataFrame.

    Cleans up column names: lowercase, spaces → underscores.
    """
    tables = pd.read_html(html)
    if not tables:
        raise ValueError("No tables found in the provided HTML.")
    if table_index >= len(tables):
        raise IndexError(
            f"table_index {table_index} out of range — page has {len(tables)} table(s)."
        )
    df = tables[table_index]
    df.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_")
        for c in df.columns
    ]
    return df


def parse_html_scrape(
    html: str,
    row_selector: str,
    field_map: dict[str, str],
) -> pd.DataFrame:
    """Scrape structured rows from HTML using CSS selectors.

    Args:
        html:          Raw HTML string.
        row_selector:  CSS selector that matches each "row" element.
        field_map:     Dict mapping output column name → CSS selector
                       relative to each row element.
                       Use '' (empty string) to get the row's own text.

    Example:
        parse_html_scrape(html, "tr.data-row", {"name": "td.name", "value": "td.val"})
    """
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select(row_selector)
    records = []
    for row in rows:
        record: dict[str, str] = {}
        for col, selector in field_map.items():
            el = row.select_one(selector) if selector else row
            record[col] = el.get_text(" ", strip=True) if el else ""
        records.append(record)
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def download_file(url: str, dest: Path, headers: dict | None = None, timeout: int = 60) -> Path:
    """Stream-download a file (CSV, JSON, zip, etc.) to dest and return the path."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    hdrs = {**_DEFAULT_HEADERS, **(headers or {})}
    with requests.get(url, headers=hdrs, timeout=timeout, stream=True) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
    return dest


# ---------------------------------------------------------------------------
# Source-driven ingest (reads config.yaml sources block)
# ---------------------------------------------------------------------------

def ingest_source(
    name: str,
    cfg: dict,
    save_raw: bool = True,
    js_wait_selector: str | None = None,
    row_selector: str | None = None,
    field_map: dict[str, str] | None = None,
    rate_limit_seconds: float = 1.0,
) -> pd.DataFrame:
    """Ingest a named source from config.yaml and return a DataFrame.

    Args:
        name:               Key under `sources:` in config.yaml.
        cfg:                Loaded config dict (from load_config()).
        save_raw:           If True, save the raw HTML/bytes to data/raw/.
        js_wait_selector:   Passed to fetch_html_js() if js_render is true.
        row_selector:       Required for html_scrape type.
        field_map:          Required for html_scrape type.
        rate_limit_seconds: Polite delay before fetching.
    """
    source = cfg["sources"][name]
    url: str = source["url"]
    source_type: str = source.get("type", "html_table")
    js_render: bool = source.get("js_render", False)
    table_index: int = source.get("table_index", 0)

    time.sleep(rate_limit_seconds)

    if source_type == "csv":
        dest = raw_path(cfg, f"{name}.csv")
        download_file(url, dest)
        return pd.read_csv(dest, encoding=cfg["settings"]["encoding"])

    if source_type == "json":
        dest = raw_path(cfg, f"{name}.json")
        download_file(url, dest)
        with open(dest, encoding=cfg["settings"]["encoding"]) as f:
            data = json.load(f)
        return pd.json_normalize(data)

    # HTML-based types
    html = fetch_html_js(url, wait_selector=js_wait_selector) if js_render else fetch_html(url)

    if save_raw:
        raw_path(cfg, f"{name}.html").write_text(html, encoding="utf-8")

    if source_type == "html_table":
        return parse_html_table(html, table_index=table_index)

    if source_type == "html_scrape":
        if row_selector is None or field_map is None:
            raise ValueError("html_scrape requires row_selector and field_map arguments.")
        return parse_html_scrape(html, row_selector, field_map)

    raise ValueError(f"Unknown source type '{source_type}'. Use: html_table, html_scrape, csv, json.")


# ---------------------------------------------------------------------------
# World Bank API v2 — Indicator Bulk Download
# ---------------------------------------------------------------------------
# The World Bank API is free, no key required, generous rate limits.
# Returns paginated JSON with country-year observations.
# Docs: https://datahelpdesk.worldbank.org/knowledgebase/articles/898599
# ---------------------------------------------------------------------------


def ingest_world_bank_indicator(
    cfg: dict,
    indicator_code: str,
    indicator_name: str,
    date_range: str = "1960:2025",
    per_page: int = 1000,
    save_raw: bool = True,
) -> pd.DataFrame:
    """Fetch a single World Bank indicator for all countries.

    Handles pagination automatically. Saves raw JSON to data/raw/.

    Args:
        cfg:            Loaded config dict.
        indicator_code: WDI indicator code (e.g., "SI.POV.GINI").
        indicator_name: Human-readable name for logging.
        date_range:     Year range as "YYYY:YYYY".
        per_page:       Records per page (max 1000).
        save_raw:       Save raw JSON response to data/raw/.

    Returns:
        DataFrame with columns: country_code, country_name, year, value, indicator.
    """
    source = cfg["sources"]["world_bank"]
    base_url = source["base_url"]
    rate_limit = cfg["settings"].get("rate_limit_seconds", 1.5)

    url = f"{base_url}/country/all/indicator/{indicator_code}"
    params = {
        "format": "json",
        "per_page": per_page,
        "date": date_range,
        "page": 1,
    }

    all_records = []
    page = 1
    total_pages = 1  # will be updated from first response

    while page <= total_pages:
        params["page"] = page
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        # First element is metadata, second is data array
        if len(data) < 2 or data[1] is None:
            break

        metadata = data[0]
        records = data[1]
        total_pages = metadata.get("pages", 1)

        for rec in records:
            if rec.get("value") is not None:
                all_records.append({
                    "country_code": rec["country"]["id"],
                    "country_name": rec["country"]["value"],
                    "year": int(rec["date"]),
                    "value": float(rec["value"]),
                    "indicator": indicator_code,
                })

        page += 1
        if page <= total_pages:
            time.sleep(rate_limit)

    df = pd.DataFrame(all_records)

    if save_raw and not df.empty:
        filename = f"wb_{indicator_code.replace('.', '_').lower()}.parquet"
        dest = raw_path(cfg, filename)
        df.to_parquet(dest, index=False)

    return df


def ingest_world_bank_all(
    cfg: dict,
    indicators: list[dict] | None = None,
    skip_existing: bool = True,
) -> pd.DataFrame:
    """Fetch all configured World Bank indicators.

    Args:
        cfg:            Loaded config dict.
        indicators:     Override list of {"code": ..., "name": ...} dicts.
                        If None, uses config sources.world_bank.indicators.
        skip_existing:  If True, skip indicators that already have raw parquet files.

    Returns:
        Combined DataFrame with all indicators (long format).
    """
    source = cfg["sources"]["world_bank"]
    indicator_list = indicators or source["indicators"]
    date_range = source.get("date_range", "1960:2025")
    per_page = source.get("per_page", 1000)

    all_frames = []
    total = len(indicator_list)

    print(f"=== World Bank Indicator Ingest ===")
    print(f"  Indicators: {total}")
    print(f"  Date range: {date_range}")
    print()

    for i, ind in enumerate(indicator_list, 1):
        code = ind["code"]
        name = ind["name"]
        filename = f"wb_{code.replace('.', '_').lower()}.parquet"
        dest = raw_path(cfg, filename)

        if skip_existing and dest.exists():
            print(f"  [{i}/{total}] skip (exists): {code} — {name}")
            df = pd.read_parquet(dest)
            all_frames.append(df)
            continue

        print(f"  [{i}/{total}] fetching: {code} — {name}")
        try:
            df = ingest_world_bank_indicator(
                cfg, code, name, date_range=date_range, per_page=per_page
            )
            if not df.empty:
                all_frames.append(df)
                print(f"           → {len(df):,} observations")
            else:
                print(f"           → (no data)")
        except requests.HTTPError as e:
            print(f"           → FAILED: {e}")
            continue

    if all_frames:
        combined = pd.concat(all_frames, ignore_index=True)
    else:
        combined = pd.DataFrame()

    print(f"\n  Total: {len(combined):,} observations across {combined['indicator'].nunique() if not combined.empty else 0} indicators")
    return combined


# ---------------------------------------------------------------------------
# ISO 3166-1 Country Codes Reference Table
# ---------------------------------------------------------------------------

def ingest_iso_countries(cfg: dict, skip_existing: bool = True) -> pd.DataFrame:
    """Download and parse the ISO 3166-1 country codes CSV.

    Returns DataFrame with: alpha-2, alpha-3, numeric, name, region, sub-region.
    """
    source = cfg["sources"]["iso_countries"]
    url = source["url"]
    dest = raw_path(cfg, "iso_countries.csv")

    if skip_existing and dest.exists():
        print("  ISO countries: skip (exists)")
        return pd.read_csv(dest)

    print("  Downloading ISO 3166-1 country codes...")
    download_file(url, dest)
    df = pd.read_csv(dest)
    print(f"  → {len(df)} entries")
    return df


# ---------------------------------------------------------------------------
# Full ingest orchestrator
# ---------------------------------------------------------------------------

def ingest_all(cfg: dict, skip_existing: bool = True) -> dict[str, pd.DataFrame]:
    """Run full countries ingest: ISO codes + all World Bank indicators.

    Returns dict with 'iso_countries' and 'indicators' DataFrames.
    """
    print("=" * 60)
    print("  COUNTRIES INCOME DISPARITY — FULL INGEST")
    print("=" * 60)
    print()

    # 1. ISO country codes
    print("--- ISO 3166-1 Country Codes ---")
    df_iso = ingest_iso_countries(cfg, skip_existing=skip_existing)
    print()

    # 2. World Bank indicators
    print("--- World Bank Indicators ---")
    df_indicators = ingest_world_bank_all(cfg, skip_existing=skip_existing)
    print()

    return {
        "iso_countries": df_iso,
        "indicators": df_indicators,
    }
