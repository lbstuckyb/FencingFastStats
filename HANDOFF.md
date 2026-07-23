# Handoff — start of next session

**State: M6.6 is DONE and committed. M6.7 (profile metric chart + per-season
table + H2H metric comparison + the `#/compare` route) is next — one milestone
per session, so M6.7 is the whole job.**

M6 shipped a complete site; a review against the legacy Dash app found three of
its analytical features had never been carried over. M6.5 built the data layer,
M6.6 the explorer and the ratings explainer. The plan for all four is
`~/.claude/plans/it-looks-good-but-sprightly-snail.md` — **read its M6.7 section
before starting.**

## Read first

1. That plan file's `## M6.7` section (the actual spec for this session).
2. `PLAN.md` → `## Progress Log` → the M6.5 and M6.6 entries.
3. `site/js/metrics.js` — the registry reader every metric view goes through
   (formatting, sort direction, explorer-row aggregation). Do not re-derive
   labels, aggregations or sort directions anywhere else.

## What M6.6 left you

- **`#/explore`** (`site/js/views/explore.js`) is the worked example of
  registry-driven rendering: metric columns, their headers, their formats and
  their sort directions all come from `meta.json`. Its selection bar already
  tracks picked fencer ids — that is the state M6.7's `#/compare?ids=…` route
  is meant to consume. (M6.6 deliberately did not link to `#/compare` yet,
  since the route did not exist; the bar offers head-to-head for two picks.)
- **Aggregation rule, everywhere**: divide a metric's sum by the count named by
  its `den`, never by the number of competitions entered. The per-season table
  M6.7 builds from a shard has to do the same thing the explorer does over
  `explore/*.json` — a fencer's poule columns rest on fewer competitions than
  their placings do.
- **`#/methodology?s={id}`** deep-links into a section (`rating`, `glossary`,
  `source`, `bouts`, `h2h`, `limits`). New views that show a rating or a metric
  should link there rather than re-explaining.
- **Data fix**: fie.org's no-ranking sentinels (`final_rank` 999/9999, 1,463
  rows) are now nulled at parse, in `stats.compute_stats` and in
  `build_site._load_tables` (`schema.RANK_SENTINEL_MIN`). Canonical parquet and
  `site/data/` were rebuilt on 2026-07-23, so shards are already clean. `ffs
  validate`: 286/286 matched, parity 99.3%, POS 100.0%.

## State of the repo

- Eight routes work and are verified: `#/`, `#/search`, `#/fencer/{id}`,
  `#/competitions`, `#/competition/{id}`, `#/h2h?a=&b=`, `#/explore?pool=`,
  `#/methodology`.
- `site/data/` is gitignored. Rebuild with `.venv/bin/ffs build-site` (~23 min,
  162 MB, 22k files); it is a pure function of `data/canonical/*.parquet`.
  **M6.7 needs no rebuild** — it is UI over the shards.
- `.github/workflows/pages.yml` builds `site/data/` in CI. **Pages has never
  been enabled and master has never been pushed** — both need the user's
  go-ahead.
- `pytest`: 88/88 green.

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
on), Errigo–Kiefer (`#/h2h?a=9377&b=21717`, 14 meetings), KANO Koki (34385),
LIMARDO GASCON Ruben (10222 — the profile that exposed the rank sentinel; his
mean World Cup/GP placing should now read ~20, not 218).

⛔ Reminder: one milestone per session — stop at M6.7's commit.
