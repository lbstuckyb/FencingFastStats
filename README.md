# FencingFastStats

FencingFastStats is being rebuilt as a static analytics site for FIE fencing competitions
(scraped from fie.org, pre-baked into JSON, served from GitHub Pages — no server, no database).

See [`PLAN.md`](PLAN.md) for the full rebuild plan, milestones, and progress log.

## Repo layout (mid-rebuild)

- `legacy/` — the original Plotly Dash app and manual data pipeline (Spanish UI, 2021–2022 era).
  Kept for reference; superseded by the `ffs` package and static site as milestones land.
- `data/` — `COL.csv` / `EF.csv` (Colombian data, untouched, out of scope for this rebuild),
  `data/legacy/updated_results.csv` (the legacy dataset, kept as a validation oracle).
- `src/ffs/` — the new Python package (scraper, parser, stats engine, site builder). Currently a stub.
- `site/`, `docs/`, `tests/` — added as milestones land (see `PLAN.md`).

## Development

```
pip install -e .
ffs --help
```
