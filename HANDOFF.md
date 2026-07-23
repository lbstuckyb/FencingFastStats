# Handoff — start of next session

**State: M6 is DONE and committed. M7 (`docs/proposal.md`, `docs/backlog-phase3.md`,
final README pass) is next — one milestone per session, so M7 is the whole job.**

## Read first

1. `PLAN.md` → `## Progress Log` → the M6 entry (final size report, the two
   grid-overflow fixes, the round-naming decision, verification coverage).
2. `src/ffs/build_site.py` module docstring — the `site/data/` layout.

## State of the repo

- All seven routes work and are verified: `#/`, `#/search`, `#/fencer/{id}`,
  `#/competitions`, `#/competition/{id}`, `#/h2h?a=&b=`, `#/methodology`.
- `.github/workflows/pages.yml` builds `site/data/` in CI from the committed
  canonical parquet (no scraping) and uploads it. **Pages has never been
  enabled and master has never been pushed — both need the user's go-ahead.**
- `site/data/` is gitignored. Rebuild with `.venv/bin/ffs build-site` (~20 min,
  146 MB, 22k files). It is a pure function of `data/canonical/*.parquet`.
- `pytest`: 77/77 green.

## What M7 needs

- `docs/proposal.md` — the FIE-facing pitch, **with screenshots of the running
  site**. Take them per the recipe below; the competition detail page
  (`#/competition/2025-242`) and a head-to-head with a real bout list
  (`#/h2h?a=9377&b=21717`, Errigo–Kiefer, 14 meetings) are the best two.
- `docs/backlog-phase3.md` — what a phase 3 would add.
- Final `README.md` pass; fill the demo link if Pages ends up live.

## Verifying / screenshotting the site without a browser extension

No browser extension on this machine; headless Chrome is the way.

```bash
python -m http.server 8765 -d site &
google-chrome --headless=new --disable-gpu --no-sandbox --window-size=1280,1400 \
  --virtual-time-budget=20000 --screenshot=out.png \
  "http://localhost:8765/index.html#/competition/2025-242"
```

For console errors, overflow measurements, dark mode, or scrolling to a
specific element, drop a temporary `site/_debug.html` that loads `index.html`
in a fixed-width iframe, sets `documentElement.dataset.theme`, optionally
`scrollIntoView()`s a selector, and prints the results into a `<pre>` that
`--dump-dom` picks up. One route per page load (`?route=…&theme=…&w=…`) —
walking several routes in one load does not survive `--virtual-time-budget`.
**Delete it before committing.**

⛔ Reminder: one milestone per session — stop at M7's commit.
