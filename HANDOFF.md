# Handoff — start of next session

**State: M6 is PARTIAL — all code is written and committed (`b72eb85`), but
`site/data/` has not been regenerated and nothing has been verified in a
browser. Resume M6; do not start M7.**

## Read first

1. `PLAN.md` → `## Progress Log` → the M6 entry (artifact shapes, the poule
   row-order reconstruction, the DE round-ordering heuristic, the `h2h_all`
   design decision). Don't re-derive any of it.
2. `src/ffs/build_site.py` module docstring — the full `site/data/` layout.

## What's done

- `build_site.py` emits `competitions/index.json`, `competitions/{id}.json`,
  `h2h/{lo}-{hi}.json` (pairs with >=5 meetings), and `h2h_all` inside every
  fencer shard.
- Four new views (`competitions`, `competition`, `h2h`, `methodology`), router
  + nav + cross-links + CSS.
- `.github/workflows/pages.yml` (builds `site/data` in CI, no scraping).
- `pytest`: 77/77 green.

## What's left (finish M6 in this order)

1. **Regenerate `site/data/`**: `.venv/bin/ffs build-site` (~15 min now — it
   writes ~3.1k competition files and ~2.2k pair files on top of the 17k
   shards). The last run died partway on a `pd.NA` city — that bug is fixed
   (`_write_json` `default=`) and covered by a test, but the run was never
   repeated, so **the current `site/data/` on disk is stale/incomplete**.
   `site/data/` is gitignored; nothing about it gets committed.
2. Check the printed size report: no *eager* file over 1.5 MB.
   `competitions/index.json` measured ~548 KB when built standalone.
3. Local click-through of the four new routes plus the three old ones:
   `#/competitions`, `#/competition/2025-242` (215 entries, 29 poules, rounds
   A256→B2 — the best detail-page test case), `#/h2h?a=34385&b=30081` (the
   2025 world final pair), `#/methodology`. Serve with
   `python -m http.server -d site` and verify per the headless-Chrome recipe
   below: zero console errors, no horizontal page scroll at 375px, light+dark.
4. Visual polish pass, then update `PLAN.md`'s M6 entry (tick the box) and
   commit `feat: complete site + GitHub Pages workflow`.

Enabling Pages + pushing needs the user's go-ahead — ask, don't push.

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

⛔ Reminder: one milestone per session — stop at M6's commit.
