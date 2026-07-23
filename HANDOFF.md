# Handoff — start of next session

**State: M6.5 is DONE and committed. M6.6 (ratings explainer + the Metrics
Explorer page) is next — one milestone per session, so M6.6 is the whole job.**

M6 shipped a complete site, then a review against the legacy Dash app found
three of its analytical features had never been carried over. M6.5–M6.8 bring
them back. The plan for all four is
`~/.claude/plans/it-looks-good-but-sprightly-snail.md` — **read its M6.6
section before starting.**

## Read first

1. That plan file's `## M6.6` section (the actual spec for this session).
2. `PLAN.md` → `## Progress Log` → the M6.5 entry (what the new data layer
   holds and why it is shaped that way).
3. `src/ffs/metrics.py` — the metric registry. Everything M6.6 renders is
   driven by it, via `meta.json`.

## What M6.5 left you

- **`meta.json`** (7.3 KB, eager) now carries `metrics` (23 `Metric` records:
  `code, label, short, group, agg, better, fmt, den, blurb`), `groups`,
  `counts`, `path_series`, `level_groups`, `default_level_groups`
  (`["WC","GP"]`) and `cohort_tiers`. **No view should hardcode a metric
  label, aggregation or sort direction** — read them from here.
- **`data/explore/{pool}.json`** (lazy, 2.2–4.5 MB): rows of
  `[athlete_id, season, level_group_index, ...8 counts, ...23 metric sums]`.
  To aggregate: sum the rows the filters select, then for a `mean` metric
  divide by the summed count named by that metric's `den`; a `sum` metric
  needs no division. Join names/countries from `fencers/index.json`.
- **`data/paths/{pool}.json`** (lazy, ~95 KB) — M6.8's input, not M6.6's.
- Fencer shards carry all 23 metrics as a fixed-order `"m"` array keyed by
  `meta.metrics`; `site/js/views/fencer.js`'s `metricReader` is the pattern to
  copy. Career blocks now have `peak_rating` and `peak_pool_rank`.
- `T96+` is now `TPRE64` everywhere outside `legacy/`.

## State of the repo

- Seven routes work and are verified: `#/`, `#/search`, `#/fencer/{id}`,
  `#/competitions`, `#/competition/{id}`, `#/h2h?a=&b=`, `#/methodology`.
- `site/data/` is gitignored. Rebuild with `.venv/bin/ffs build-site` (~23 min,
  162 MB, 22k files); it is a pure function of `data/canonical/*.parquet`.
  **M6.6 needs no rebuild** — it is UI over artifacts that already exist.
- `.github/workflows/pages.yml` builds `site/data/` in CI. **Pages has never
  been enabled and master has never been pushed** — both need the user's
  go-ahead.
- `pytest`: 86/86 green.

## Verifying the site without a browser extension

No browser extension on this machine; headless Chrome is the way.

```bash
python3 -m http.server 8765 -d site &
google-chrome --headless=new --disable-gpu --no-sandbox --window-size=1280,1400 \
  --virtual-time-budget=20000 --screenshot=out.png \
  "http://localhost:8765/index.html#/explore?pool=em"
```

For console errors, overflow measurements and dark mode, drop a temporary
`site/_debug.html` that loads `index.html` in a fixed-width iframe, sets
`documentElement.dataset.theme`, hooks `console.error` / `unhandledrejection`,
and prints the results into a `<pre>` that `--dump-dom` picks up. One route per
page load (`?r=…&t=…&w=…`) — walking several routes in one load does not
survive `--virtual-time-budget`. **Delete it before committing.**

Acceptance for every new/changed route, at 375px and desktop in both themes:
zero console errors or unhandled rejections, and
`documentElement.scrollWidth <= viewport`.

Spot-check names: RODRIGUEZ John Edison (21208, the profile the gaps were found
on), Errigo–Kiefer (`#/h2h?a=9377&b=21717`, 14 meetings), KANO Koki (34385).

⛔ Reminder: one milestone per session — stop at M6.6's commit.
