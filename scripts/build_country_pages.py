#!/usr/bin/env python3
"""Build the PUBLIC per-country dashboard picker for GitHub Pages (Option A).

Publish-stage companion to build_country_dashboards.py (the dev review sheet). It
renders one WEB-MODE metric_dashboard PNG per country into a TRACKED docs/ folder
and writes a self-contained countries.html with a <select> that swaps the image —
static, in-pipeline, no JS charting library.

It REUSES build_country_dashboards.py's rendering logic (load, metrics_for, SUPPRESS,
METRIC_DEFS) so the published dashboards inherit exactly what the owner reviewed —
including the CAF life-expectancy suppression and the per-country welfare-type +
survey-break annotations. No duplicated chart logic.

Outputs (tracked, part of the public release):
  - docs/countries/<ISO3>.png   web-mode dashboard per country (chrome-light, watermark only)
  - docs/countries.html         <select> picker that swaps the dashboard image

Run:  .venv/bin/python scripts/build_country_pages.py
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "scripts"))
sys.path.insert(0, str(PROJECT.parent.parent / "shared"))

import chart_templates as ct  # noqa: E402
from viz import PRESETS  # noqa: E402
# Reuse the dev builder's data + per-country metric logic (incl. SUPPRESS/CAF fix).
from build_country_dashboards import load, metrics_for, NAVY, SRC  # noqa: E402

OUT_DIR = PROJECT / "docs" / "countries"
OUT_DIR.mkdir(parents=True, exist_ok=True)
HTML_OUT = PROJECT / "docs" / "countries.html"
WW, WH, _ = PRESETS["web"]
DEFAULT_ISO = "USA"  # the project's anchor country


def main() -> None:
    panel, welfare, breaks = load()
    countries = (panel[["iso_alpha3", "country_name"]].dropna()
                 .drop_duplicates().sort_values("country_name"))
    print(f"Rendering {len(countries)} web-mode country dashboards -> {OUT_DIR}")

    options = []
    for _, row in countries.iterrows():
        iso3, name = row["iso_alpha3"], row["country_name"]
        sub = panel[panel.iso_alpha3 == iso3].copy()
        img = ct.metric_dashboard(
            df=sub, metrics=metrics_for(iso3, sub, welfare, breaks),
            title="", subtitle=None, source=None,   # web mode drops chrome; page carries it
            line_color=NAVY, img_width=WW, web_mode=True,
        )
        img.save(OUT_DIR / f"{iso3}.png", format="PNG", optimize=True)
        sel = " selected" if iso3 == DEFAULT_ISO else ""
        options.append(f'    <option value="{iso3}"{sel}>{name}</option>')

    default_iso = DEFAULT_ISO if (countries.iso_alpha3 == DEFAULT_ISO).any() \
        else countries.iloc[0]["iso_alpha3"]
    _write_html(options, default_iso)
    print(f"Done. {len(countries)} dashboards + {HTML_OUT.name}")


def _write_html(options: list[str], default_iso: str) -> None:
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Country profiles — income &amp; inequality</title>
<style>
  body {{ font-family: -apple-system, Helvetica, Arial, sans-serif; margin: 0;
          color: #1c2530; background: #fff; }}
  .wrap {{ max-width: 960px; margin: 0 auto; padding: 24px 16px 48px; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  p.lead {{ color: #55606b; font-size: 15px; margin: 0 0 18px; line-height: 1.5; }}
  .controls {{ margin: 0 0 16px; }}
  label {{ font-weight: 600; font-size: 14px; margin-right: 8px; }}
  select {{ font-size: 15px; padding: 7px 10px; border: 1px solid #c7ced5;
            border-radius: 6px; background: #fff; min-width: 260px; }}
  .chart img {{ width: 100%; height: auto; border: 1px solid #eee; border-radius: 6px; }}
  .note {{ color: #77818b; font-size: 13px; margin-top: 14px; line-height: 1.5; }}
  a {{ color: #005F73; }}
  .backlink {{ display: inline-block; margin: 0 0 14px; font-size: 14px;
               font-weight: 600; text-decoration: none; }}
  .backlink:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<div class="wrap">
  <a class="backlink" href="../">&larr; Back to How Countries Compare</a>
  <h1>Country profiles — income &amp; inequality over time</h1>
  <p class="lead">
    Pick a country to see six metrics over time: life expectancy, GDP per capita (PPP),
    income inequality (Gini), fertility, unemployment, and urbanization. Each panel is
    <b>0-based</b> (true scale, not zoomed). <b>Gini is measured 0–100</b> (0 = everyone
    equal, 100 = one person has it all) and is labeled income- or consumption-based per
    country — the two are <b>not directly comparable</b>. Source: World Bank WDI + PIP;
    survey years vary. A gold dashed line marks a documented survey/comparability break.
  </p>
  <div class="controls">
    <label for="country">Country</label>
    <select id="country" onchange="swap()">
{chr(10).join(options)}
    </select>
  </div>
  <div class="chart">
    <img id="dash" src="countries/{default_iso}.png" alt="Country metric dashboard">
  </div>
  <p class="note">
    Some countries have little or no survey data for a given metric; those panels read
    “(no data).” A small number of series with demographically implausible source values
    are suppressed and labeled as such (e.g. Central African Republic life expectancy, a
    World Bank modeling artifact). Data ties back to the World Bank source in every case.
    &middot; <a href="../">&larr; Back to How Countries Compare</a>
  </p>
</div>
<script>
  function swap() {{
    var iso = document.getElementById('country').value;
    document.getElementById('dash').src = 'countries/' + iso + '.png';
    document.getElementById('dash').alt = iso + ' metric dashboard';
  }}
</script>
</body>
</html>
"""
    HTML_OUT.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
