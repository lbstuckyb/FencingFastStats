# FencingFastStats

A static analytics site for international FIE fencing: every competition on fie.org's
archive, scraped, parsed into canonical tables, and pre-baked into JSON that a plain
HTML/CSS/JS front end reads. No server, no database, no build step for the front end —
GitHub Pages serves the whole thing.

3,092 competitions, 25,860 fencers and 548,901 bouts across seasons 2002–2026.

See [`PLAN.md`](PLAN.md) for the rebuild plan and its progress log, and
[`docs/methodology.md`](docs/methodology.md) for how every number is computed.

## What the site does

| Page | What it shows |
|---|---|
| Home (`#/`) | Rating leaders, most titles and podiums, recent competitions, per weapon-and-gender pool |
| Fencers (`#/search`, `#/fencer/{id}`) | Type-ahead search; per-fencer career summary, rating timeline, metric-over-time chart, season-by-season metrics, full results and top rivals |
| Competitions (`#/competitions`, `#/competition/{id}`) | Browsable competition archive; per-competition final ranking, poule grids and the DE bracket |
| Metrics (`#/explore`) | Every competition metric for every fencer of a pool, aggregated over any season range and set of competition levels, sortable on any column |
| Compare (`#/compare?ids=…`) | Up to six fencers' metrics plotted over time and set side by side |
| Trajectories (`#/paths`) | A cohort's numbers by age — median with a p25–p75 band — with any fencer's own career overlaid |
| Head-to-head (`#/h2h?a=&b=`) | Two fencers' record against each other, every bout between them, and their metrics compared |
| Methodology (`#/methodology`) | The rating model, the metric glossary generated from the registry, and the data's limits |

Ratings and cohort tiers are **this project's own measure**, computed from bout results.
The FIE's official points and rankings are not part of the dataset and are never implied
by anything the site shows.

## Repo layout

- `src/ffs/` — the Python pipeline: fie.org scraper, parser, stats engine, Elo ratings,
  metric registry and the static-site builder.
- `data/canonical/*.parquet` — the scraped, canonicalised tables (committed, ~17 MB).
  `data/legacy/updated_results.csv` is the old dataset, kept only as a validation oracle.
- `site/` — the front end. `site/data/` is generated and gitignored (~160 MB).
- `docs/`, `tests/` — methodology and the pytest suite.
- `legacy/` — the original Plotly Dash app and its manual Excel pipeline (2021–2022),
  kept for reference.

## Development

```bash
pip install -e .

ffs discover                 # list competitions from fie.org
ffs scrape-all               # scrape them into data/raw/ and data/canonical/
ffs build-stats              # per-fencer-per-competition metrics + ratings
ffs build-site               # generate site/data/ (~23 min) from data/canonical/
ffs validate                 # parity check against the legacy dataset

python -m pytest -q
python3 -m http.server 8765 -d site   # then open http://localhost:8765/
```

`site/data/` is a pure function of `data/canonical/*.parquet`, so CI regenerates it:
`.github/workflows/pages.yml` runs `ffs build-site` before uploading the Pages artifact.
No scraping happens in CI.
