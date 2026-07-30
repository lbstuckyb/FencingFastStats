# Keeping the archive up to date

The dataset is a snapshot. fie.org publishes results within a day or two of a
competition finishing, so refreshing after each competition weekend keeps the
site current. Everything below runs locally; nothing scrapes in CI.

## The one command

```bash
ffs update
```

That is the whole routine path. It:

1. re-fetches fie.org's season list and the competition listing for the seasons
   it is updating,
2. scrapes every Senior Individual competition not already in
   `data/canonical/competitions.parquet` (already-scraped ones are skipped, so
   re-running is cheap and safe),
3. recomputes `stats_fencer_comp`, `ratings_history`, `h2h` and `h2h_bouts` —
   Elo is chronological, so this is always a full recompute,
4. prints the competitions it added.

By default it updates **the newest season already in the archive, and the one
after it**. The `+1` is what makes the September season rollover work without a
flag: FIE season *N* starts in September of year *N−1*, so on 1 September the
first new competitions appear under a season the archive has never seen.

Options:

```bash
ffs update --season 2026            # one specific season (repeatable)
ffs update --weapon S --gender M    # narrow the scrape
ffs update --build-site             # also regenerate site/data/ (~23 min)
```

Then check it landed and publish:

```bash
ffs validate                        # parity against the legacy oracle
python -m pytest -q
git add data/canonical && git commit -m "data: <what you added>"
git push                            # triggers the Pages rebuild
```

## Verifying before you commit

```bash
ffs build-site                      # ~23 min, regenerates site/data/
python3 -m http.server 8765 -d site # then open http://localhost:8765/
```

`site/data/` is gitignored and is a pure function of `data/canonical/*.parquet`,
so this is only for looking at the result locally — CI rebuilds it on push.
`.github/workflows/pages.yml` runs `pip install -e .`, then `ffs build-site`,
then uploads `site/` as the Pages artifact. It never touches fie.org.

Worth actually looking at, since these are the surfaces new results change:
the home page, `#/competitions`, the new `#/competition/{id}` pages, a
participant's `#/fencer/{id}` (the rating timeline should now extend past the
new competition's date), and `#/explore?pool=…`.

## Gotchas

**`hasResults` is unreliable.** The season listing reports `hasResults: 0` even
for events that finished weeks ago with full brackets published. Never use it to
decide whether to scrape. `ffs update` doesn't — a competition with genuinely no
results simply fails to parse and is recorded in
`data/raw_cache/scrape_failures.json`.

**fie.org's CDN sometimes serves a stale competition listing.** The refresh for
the 2026 Worlds returned the pre-Worlds listing (252 rows instead of 258) on the
first attempt and the current one on an immediate retry. If `ffs update` reports
`0 ok` when you know something finished, just run it again.

**`scrape-all --force` is the wrong tool for a refresh.** Its `--force` bypasses
the per-competition cache and re-scrapes the entire range — thousands of
requests — and until this was fixed it *still* read the season listing from the
disk cache, so it found nothing new anyway. `_scrape_seasons` now always
re-fetches the newest requested season's listing (only that season can grow, so
this costs one request even on a full historical replay);
`scrape-all --refresh-lists` re-fetches every season's, for the rare case
fie.org backfills a closed season.

**Team events and non-senior categories are out of scope.** Discovery filters to
`category="S"`, `type="I"` (see `src/ffs/discover.py`). Junior/cadet/veteran and
team competitions are deliberately not scraped.

## Scraping one competition by hand

If you know the id — the site's URL is `fie.org/competitions/{season}/{id}` —
you can skip discovery entirely:

```bash
ffs discover --season 2026 --force    # list the season, find the id
ffs scrape --comp 2026/246            # scrape just that one
ffs scrape --comp 2026/246 --dump     # ...and dump the decoded payload to inspect
ffs build-stats                       # remember to recompute afterwards
```

`ffs scrape` and `ffs update` are both idempotent: re-scraping a competition
replaces its rows rather than duplicating them.

## What is committed

Only `data/canonical/*.parquet` (~17 MB). `data/raw_cache/` (the gzipped
fie.org responses) and `site/data/` are gitignored. A refresh touches **all
eight** parquet files even when it adds a handful of competitions, because
`build-stats` recomputes ratings and head-to-heads from the whole history —
a large binary diff for a small data change is expected here.
