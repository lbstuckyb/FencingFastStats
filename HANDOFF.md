# Handoff — start of next session

**State: M5 is DONE and committed. M6 is next. Nothing is half-finished.**

## Read first

1. `PLAN.md` → `## Progress Log` → the M5 entry (JSON shapes, router/page details,
   the naming and chart decisions). Don't re-derive any of it.
2. `src/ffs/build_site.py` module docstring — the `site/data/` layout.

## Where things stand

- `site/` is a working static site: shell + hash router + three pages
  (Home, Fencer search, Fencer profile with the ELO rating-timeline chart).
- `pytest`: 69/69 green.
- `site/data/` is **gitignored** — regenerate locally with `.venv/bin/ffs build-site`
  (~6.5 min) if it isn't there. A rebuild was launched at the end of the last
  session to pick up the athlete-name-strip fix in `_load_tables()`; if the
  search index still shows names with a leading space, just re-run it.
- Serve with `python -m http.server -d site` (the venv's python: `.venv/bin/python`).

## Verifying the site without a browser extension

Claude in Chrome was not connected. Headless Chrome worked well:

```bash
google-chrome --headless=new --disable-gpu --no-sandbox \
  --virtual-time-budget=12000 --dump-dom "http://localhost:8765/#/fencer/22439"
google-chrome --headless=new --disable-gpu --no-sandbox --window-size=1280,1000 \
  --virtual-time-budget=12000 --screenshot=out.png "http://localhost:8765/#/"
```

For measurements and console errors, drop a temporary `site/_debug.html` that
loads `index.html` in an iframe, walks the routes via `location.hash`, and
prints results into a `<pre>` that `--dump-dom` picks up (delete it afterwards —
it must not be committed).

## Next milestone — M6 (remaining pages + deploy)

Per `PLAN.md`: H2H explorer, competition browser + detail (poule grids, DE
bracket), methodology page, visual polish, `.github/workflows/pages.yml`.

Two things M5 deliberately left for M6:

- `build_site.py` does **not** yet emit `competitions/index.json`,
  `competitions/{id}.json`, or the `h2h/{lo}-{hi}.json` pair files — the
  competition and H2H pages need those built first.
- The Pages workflow must run `ffs build-site` as a CI step before
  `upload-pages-artifact` (93 MB of generated JSON is never committed).

⛔ Reminder: one milestone per session — stop at M6's commit.
