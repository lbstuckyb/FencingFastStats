# FencingFastStats

A static analytics site for international FIE fencing: every competition on fie.org's
archive, scraped, parsed into canonical tables, and pre-baked into JSON that a plain
HTML/CSS/JS front end reads. No server, no database — GitHub Pages serves the whole
thing.

**[lbstuckyb.github.io/FencingFastStats](https://lbstuckyb.github.io/FencingFastStats/)**

3,098 competitions, 25,886 fencers from 154 countries and 552,612 bouts across seasons
2002–2026, through the 2026 World Championships in Hong Kong. fie.org's archive carries
bout-level detail only from 2015 on, so metrics, ratings and head-to-head records start
there; earlier competitions are final placings only.

![The home page](docs/images/home.png)

## What it does

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
| Play (`#/play`) | A small épée minigame — no data, just distance and tempo |

Ratings and cohort tiers are **this project's own measure**, computed from bout results.
The FIE's official points and rankings are not part of the dataset and are never implied
by anything the site shows.

## Docs

- [`docs/proposal.md`](docs/proposal.md) — the pitch to the FIE: what exists, what the
  data does and doesn't support, what an official feed would unlock, integration paths
  and the data/legal posture.
- [`docs/methodology.md`](docs/methodology.md) — how every number is computed, every
  deviation from the legacy dataset, and the validation results.
- [`docs/backlog-phase3.md`](docs/backlog-phase3.md) — win probability, momentum,
  style profiles, fantasy scoring and rating-model work: specified, not built.

## Repo layout

- `src/ffs/` — the Python pipeline: fie.org scraper, parser, stats engine, Elo ratings,
  metric registry and the static-site builder.
- `data/canonical/*.parquet` — the scraped, canonicalised tables. `data/legacy/` is the
  old dataset, kept only as a validation oracle.
- `site/` — the front end, built by CI from `data/canonical/` and deployed to Pages.
- `legacy/` — the original Plotly Dash app and its manual Excel pipeline (2021–2022),
  kept for reference.
