# Handoff — start of next session

**State: M6 is complete — M6.8 is DONE and committed, and with it the whole
site. M7 (proposal + backlog docs) is next, and it is the last milestone.**

M6.5–M6.8 closed the gap a review against the legacy Dash app had found: the
metrics explorer, the ratings explainer, the metric-over-time chart, the compare
route and the trajectories page all exist now. Their plan was
`~/.claude/plans/it-looks-good-but-sprightly-snail.md`; it is fully delivered
and nothing is left over from it.

## Read first

1. `PLAN.md` → the `**M7**` line, then `## Progress Log` → the M6.5–M6.8 entries.
2. `README.md` — rewritten in M6.8 with the page-by-page feature list. M7's
   "final README pass" starts from there, not from scratch.
3. `docs/methodology.md` — the technical write-up the proposal should cite
   rather than restate.

## What M7 is

Per `PLAN.md`: `docs/proposal.md` (the pitch to the FIE, with screenshots of the
running site), `docs/backlog-phase3.md`, and a final README pass.
⛔ Commit message: `docs: FIE proposal + phase-3 backlog`.

Two things it needs a decision from the user on, both untouched so far:

- **Pages has never been enabled and `master` has never been pushed.** The
  proposal wants a live demo link; enabling Pages and pushing is the user's
  call, so ask before doing either.
- Screenshots for the proposal come from the headless recipe below (the machine
  has no browser extension). `--window-size=1280,1400` on `index.html` gives a
  clean desktop shot.

## State of the repo

- **Eleven routes work and are verified**: `#/`, `#/search`, `#/fencer/{id}`,
  `#/competitions`, `#/competition/{id}`, `#/h2h?a=&b=`, `#/explore?pool=`,
  `#/compare?ids=`, `#/paths?pool=&tier=&metric=&ids=`, `#/methodology?s=`,
  plus the 404 view.
- `site/data/` is gitignored. Rebuild with `.venv/bin/ffs build-site` (~23 min,
  212 MB, 22k files); it is a pure function of `data/canonical/*.parquet`.
  **M7 needs no rebuild.**
- `.github/workflows/pages.yml` builds `site/data/` in CI.
- `pytest`: 97/97 green. `ffs validate`: 286/286 competitions matched, fencer
  parity 99.3%.
- **Data runs through the 2026 World Championships** (Hong Kong, 22–27 July
  2026): 3,098 competitions, 25,886 fencers, 552,612 bouts, seasons 2002–2026.
  Refreshing after a new competition is `ffs update` — see
  [`docs/updating.md`](docs/updating.md), which also records why
  `scrape-all --force` is the wrong tool and why `hasResults` can't be trusted.

## Things worth not re-deriving

- **`site/js/metrics.js` and `site/js/metricview.js`** own everything
  metric-shaped: label, format, aggregation, sort direction. `chart.js` owns
  every chart; `picker.js` the one type-ahead. Nothing re-derives these.
- **Aggregation rule, everywhere**: divide a metric's sum by the count named by
  its `den`, never by the number of competitions entered.
- **Ratings and cohort tiers are this project's own measure** — never an FIE
  ranking, and every surface that shows one says so. The proposal must keep
  that distinction; it is the honest core of the pitch.
- **Colour**: six categorical slots (`--series-1…6`), validated in both themes.
  Three light-mode slots are under 3:1 on the light surface, so every chart
  ships a `<details>` table view.
- **ECharts trap found in M6.8**: on a cartesian value/value axis, `stack`
  stacks the *x* dimension too — the trajectories band is a `custom` polygon
  series for that reason. And a wrapping legend never tells the grid it grew,
  so `grid.top` is computed from an estimated row count.

## Verifying the site without a browser extension

```bash
python3 -m http.server 8765 -d site &
google-chrome --headless=new --disable-gpu --no-sandbox --window-size=1280,1400 \
  --virtual-time-budget=25000 --screenshot=out.png \
  "http://localhost:8765/index.html#/paths?pool=em&tier=top10&metric=rating&ids=34385"
```

For console errors, overflow measurements and dark mode, drop a temporary
`site/_debug.html` that loads `index.html` in a fixed-width iframe, sets
`documentElement.dataset.theme`, hooks `console.error` / `unhandledrejection`,
and prints into a `<pre>` that `--dump-dom` picks up. One route per page load
(`?r=…&t=…&w=…`). A second variant that clicks through controls with
`node.click()` and snapshots after each is how M6.8's interactions were checked.
**Delete both before committing.**

**Screenshot caveat:** a `--window-size=390,…` screenshot of `index.html`
renders a wider layout and *looks* clipped even when there is no overflow.
Screenshot the debug page instead (a 375px iframe inside a 1280px window).
And do look at a rendered PNG of any chart — every chart bug in M6.7 and M6.8
was invisible in the DOM.

Acceptance for every new/changed route, at 375px and desktop in both themes:
zero console errors or unhandled rejections, and
`documentElement.scrollWidth <= viewport`.

Spot-check names: KANO Koki (34385, in the men's épée top-10 cohort),
RODRIGUEZ John Edison (21208), Errigo–Kiefer (`#/h2h?a=9377&b=21717`,
14 meetings), LIMARDO GASCON Ruben (10222).

⛔ Reminder: one milestone per session — stop at M7's commit.
