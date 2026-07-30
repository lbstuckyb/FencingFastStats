# FencingFastStats — Rebuild as Static Analytics Site + FIE Proposal

> **This is the single source of truth as of Milestone 0/1** — update the Progress Log below, not the copy in `~/.claude/plans/`.

> **This plan is self-contained and designed to be executed across MULTIPLE clean sessions.** All facts below (fie.org structure, query keys, file paths, stats definitions) were verified on 2026-07-13 — do not re-derive them, but do re-verify live fie.org behavior if scraping errors appear.

## EXECUTION PROTOCOL (MANDATORY — read first in every session)

1. **One milestone per session.** At the start of a session: read this plan fully, read the Progress Log at the bottom, run `git log --oneline -5` to confirm state, then execute ONLY the next unchecked milestone.
2. **At every `⛔ STOP` point** (end of each milestone): run that milestone's verification, `git add` + `git commit` with the given message, update the Progress Log section of the repo's `PLAN.md` (check the box, add 1–3 lines of notes: what deviated, open issues), and **END THE SESSION. Do not start the next milestone.**
3. **Milestone 0 (first session only):** copy this plan file into the repo as `PLAN.md` and commit it. From then on, the repo's `PLAN.md` is the single source of truth — update its Progress Log, not the copy in `~/.claude/plans/`.
4. Commit messages end with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` (or the executing model's tag).
5. If a milestone turns out too large for one session, find a coherent stopping point, commit with `(partial)` in the message, note it in the Progress Log, and stop — the next session resumes the same milestone.
6. Never push without being asked. Never delete legacy files beyond what a milestone explicitly lists.

## Context

The repo is a 2021–2022-era fencing analytics project: an old Plotly Dash app (pre-2.0 API, 3 near-duplicate ~800-line app files, no requirements.txt/Procfile, Spanish UI) fed by a manual pipeline (hand-download FIE Excel files → hand-edit filenames in scripts → commit 110 MB of duplicate CSV snapshots). The premise still holds: **fie.org offers zero analytics** (verified live today), even after their site redesign.

**Key discovery (verified live):** the new fie.org is a Nuxt 3 app that server-renders ALL competition data (info, pools, pool results, tableau, final results) into a `<script id="__NUXT_DATA__">` JSON payload (~210 KB/page, devalue serialization format), fetchable with plain `curl` + browser User-Agent — HTTP 200, no Cloudflare block (Turnstile key present in config but not enforced on GETs). This makes a fully automated scraper feasible and removes the manual Excel pipeline entirely. No official API exists (api.fie.org root answers 200 but guessed routes 404); the SSR-payload approach is the way.

**User decisions (locked):**
1. Product: **static web app** (HTML/JS/CSS + pre-baked JSON, GitHub Pages, no server). Python only as offline pipeline.
2. Language: **English only**.
3. **Colombian data dropped** from this rebuild (files left untouched, revivable later).
4. Analytics: **port current stats + head-to-head + ELO rating with history**. Write a **phase-3 backlog doc** (win-probability, momentum/comeback, style profiles, fantasy/gaming) describing what each needs — not implemented now.
5. Goals: (a) polished demo + written proposal to FIE; (b) if no reply, publish as personal project — note scraping legal/ToS posture.

## Tooling decisions

- **pandas** (not polars — existing code is pandas, dataset fits in memory: ~200k result rows / ~600k bouts even for 2002–2026).
- **Parquet** via pyarrow for canonical tables; no database.
- **requests + beautifulsoup4** (or regex for the one script tag); no scrapy/playwright needed.
- Python ≥3.11, `pyproject.toml` at root, package `ffs`, console script `ffs`. pytest for tests.
- Static site: **no build step** — vanilla ES modules + tiny hash router, **ECharts vendored locally** (lazy-imported on chart pages). Dev server = `python -m http.server`. (Vite/Preact is the escape hatch if ever needed.) **Invoke the `dataviz` skill before writing any chart code.**

## New repo layout

```
├── pyproject.toml, .gitignore, README.md (rewritten)
├── legacy/                 # git mv of old code: app/, data scripts, templates/, tesy.py, comp_results/
├── data/
│   ├── COL.csv, EF.csv     # Colombian — untouched
│   ├── legacy/updated_results.csv   # the ONE kept snapshot (validation oracle)
│   ├── raw_cache/          # gitignored gzipped __NUXT_DATA__ per page
│   └── canonical/          # parquet: competitions, athletes, results, bouts,
│                           #   stats_fencer_comp, ratings_history, h2h, h2h_bouts
├── src/ffs/                # devalue.py, fie_client.py, discover.py, parse.py, schema.py,
│                           # stats.py, elo.py, h2h.py, build_site.py, validate_legacy.py, cli.py
├── tests/                  # fixtures (2–3 real payloads, gz) + test_devalue/parse/stats/elo.py
├── site/                   # index.html, css/, js/ (router, api, views/*), vendor/echarts.min.js, data/
├── docs/                   # proposal.md, methodology.md, backlog-phase3.md
└── .github/workflows/pages.yml
```

Cleanup in Milestone 1: **scrub token fragment at `data/input_new_results.py:72`**; delete `final_results/` duplicates after spot-checking they're ancestors of `data/updated_results.csv` (git pack is only ~33 MiB — history surgery via git filter-repo is optional and NOT recommended; flag to user only if clone size ever matters).

## Scraper design

**`devalue.py`** — decode the flat-array devalue format: root at index 0, composites store indices, sentinels (-1 undefined, -3 NaN, …), Nuxt reducer tags (`["Reactive", idx]`, `["Date", idx]`, `Map`/`Set`). ~40-line recursive resolver with memo. `extract_queries(decoded)` walks for dehydrated vue-query state and returns `{queryKey_tuple: state.data.body}` — bodies are HTTP-shaped `{status, body}`; unwrap. Verified query keys on a live page: `["competitions",242,2025]`, `[...,"results","pools",...]`, `[...,"pool","results",...]`, `[...,"results","tableau",...]`, `[...,"results",...,{"page":1,"pageSize":24}]` (results are paginated — iterate pages).

**`fie_client.py`** — session w/ browser UA, 30s timeout, 3 retries + backoff, **≥1.5s throttle between requests**, disk cache `data/raw_cache/{key}.json.gz` so re-parses never re-hit fie.org. Check robots.txt at Milestone 2 start; record findings in methodology.md.

**`discover.py`** — decode the `/competitions` listing SSR payload per season (paginated); also probe legacy `POST /competitions/search` once and prefer it if alive. Filter: **Senior, Individual**, all weapons/genders. URLs: `fie.org/competitions/{season}/{cid}` and `/tournaments/{season}/{tid}/event/{cid}/pools`. Store tournament_id too.

**`parse.py` + `schema.py`** — canonical LONG schema replacing the 110-wide-column format:
- `competitions`: competition_id (`"{season}-{cid}"`), season, tournament_id, name, city, country, start_date, weapon, gender, category, level, n_entries
- `athletes`: athlete_id (**real FIE id**), name, country, birth_year?, hand?
- `results`: competition_id, athlete_id, final_rank, seed?, exempt, points?
- `bouts`: competition_id, phase ('poule'|'de'), round (poule 1..n; DE 256…2, 96 for pre-64), poule_no?, **bout_order?** (needed for PM1V% / PM1&2V%), athlete_a (smaller id), athlete_b, score_a, score_b, winner, status ('ok'|'forfeit'|…) — legacy dropped "D with tr=0" rows (`update_data.py:26-31`); exclude non-'ok' from stats the same way.
- `schema.py`: dtypes + `validate_tables()` invariants (bout athletes ∈ results, poule V from bouts == pool-result V, etc.)

**First implementation task of Milestone 2:** `ffs scrape --comp 2025/242 --dump` to write decoded query bodies to scratch — exact body shapes are a discovery step; then write extractors and freeze fixtures.

**Historical backfill: re-scrape everything 2002→2026 from fie.org** rather than migrating the legacy CSV (legacy ids are collision-prone `name[:11].lower()`; fie.org has real athlete ids and more history). Legacy CSV (48,535 rows, 204 comps, 2015–2022, Senior only) becomes a **validation oracle only**. Tolerate old competitions with results-only data (poule metrics null, like PEXMPT semantics).

## Stats engine

**`stats.py`** — one row per (competition_id, athlete_id) from bout-level data (explode bouts to fencer perspective, two groupbys). Port every metric from `data/update_data.py:26-98`: POS, Q, PEXMPT, PVICT, PIND, PTR, PTD, PT-DIFF, PMTR, PMTD, PMT-DIFF (+stds), TTR, TTD, TMT-DIFF, TMVAVG (null if Q=0), PM1V%, PM1&2V%, T64+, TPRE64. Note legacy inconsistency (`p_tr_mean = tr_poules/p_matches` vs `p_td_mean` = row-mean) — replicate intent, document deviations in methodology.md. Plus career aggregates per athlete×weapon for site profiles.

**`h2h.py`** — group bouts by unordered pair within (weapon, gender) → `h2h.parquet` (bouts, wins, td, poule/de split, last_met) + `h2h_bouts.parquet` (per-pair bout list for the site).

**`elo.py`** — per (weapon, gender) pool, start 1500, **K=16 poule / K=32 DE**, provisional 2×K for first 30 bouts, no decay/MoV in v1 (→ backlog). Order: competitions by start_date, within comp poules then DE 256→2. Emit `ratings_history.parquet`: (athlete, competition, pre, post). ~30-line loop with defaultdicts (sketch in plan discussion; straightforward).

## Site data artifacts (`build_site.py` → `site/data/`)

Small eager bundle + lazy shards via relative `fetch()` (GitHub Pages-safe):
- `meta.json` (~2 KB); `fencers/index.json` (search index, ≤~1 MB); `summary/{me,mf,we,wf,se,sf}.json` (ELO top-200, leaderboards, comp list); `fencers/{id%100}/{id}.json` (career, per-comp stats, rating timeline, h2h aggregates); `h2h/{lo}-{hi}.json` **only for pairs ≥5 bouts**; `competitions/index.json` + `competitions/{id}.json` (full results, poules, bracket).
- Added in M6.5: `explore/{pool}.json` (pre-aggregated per (athlete, season, level group) sums + population counts, for the metrics explorer) and `paths/{pool}.json` (by-age cohort distributions for the trajectories page). Both lazy and page-scoped.
- Size guardrails: warn on eager files >1.5 MB; prune per-fencer shards to athletes with ≥2 comps; measured decision at Milestone 5 whether to commit `site/data/` or generate in CI.

## Static site pages (`site/`)

Home (pool selector, ELO top-20, recent comps, leaderboards) · Fencer search (client-side over index.json) · Fencer profile (**rating timeline chart**, career table, per-comp results, H2H list) · H2H explorer (two fencers → aggregate card + bout list) · Competition browser + detail (results, poule grids, DE bracket) · Metrics explorer (every metric per fencer, filtered by season/level, sortable — added in M6.6) · Compare (up to six fencers' metrics over time, side by side — M6.7) · Trajectories (cohort median + p25–p75 band by age, with fencers overlaid — M6.8) · Methodology (metric + ELO definitions, data attribution). Deploy via `.github/workflows/pages.yml` (`upload-pages-artifact` on `site/`).

## Docs deliverables

- **`docs/proposal.md`** (FIE pitch): problem (no analytics layer), live demo link + screenshots, metrics catalog, engagement/gaming roadmap (from backlog), integration path (FIE owns this data — an official API kills scraping and enables live stats), data/legal posture (public data, throttled, attributed, offer to switch to official feed).
- **`docs/methodology.md`**: every metric + ELO spec, legacy deviations, robots.txt/ToS findings.
- **`docs/backlog-phase3.md`**: win-probability, momentum/comeback, style profiles, fantasy scoring — what each is, data needed beyond current schema, rough approach, effort guess. No implementation.

## Verification

- **Decoder/parser**: pytest with 2–3 committed real payload fixtures; golden test on a 2022 comp also present in legacy xlsx (e.g. Vancouver EF 2022) — hand-checked entry count, champion, one full poule, one DE path.
- **Stats parity**: `ffs validate` matches legacy↔new comps by (date±1, weapon, gender) and fencers by normalized name+country; require **≥99% agreement** on POS/PVICT/PTD/PTR/PIND/Q/TMVAVG across ≥3 competitions; investigate systematic disagreements (legacy may be the buggy one).
- **ELO sanity**: unit tests on toy sequences; top-10 per pool should surface known world-class names.
- **Site**: `python -m http.server -d site` + click-through; all fetches relative paths.

## Milestones (one per session; each ends runnable at a ⛔ STOP)

**M0 — Plan into repo** (do together with M1, same session): copy this plan to repo root as `PLAN.md` with a `## Progress Log` section (checkbox per milestone).

**M1 — Restructure + scaffold**: `git mv` old code to `legacy/`, scrub token at `data/input_new_results.py:72` (file moves to `legacy/`), spot-check `final_results/*.csv` are ancestors of `data/updated_results.csv` (row-count + tail comparison) then delete them, `git mv data/updated_results.csv data/legacy/`, add `pyproject.toml` + `.gitignore`, rewrite `README.md`, empty `ffs` package importable with stub CLI.
*Verify:* `pip install -e . && ffs --help`; `git status` clean of junk; Colombian CSVs untouched.
⛔ STOP — commit `refactor: restructure repo, archive legacy app, scaffold ffs package`

**M2 — One competition end-to-end**: `devalue.py` + `fie_client.py` (throttle ≥1.5s, gz disk cache) + `ffs scrape --comp 2025/242 --dump` to discover payload body shapes (this is a discovery step — inspect dumped JSON before writing extractors); then `parse.py` + `schema.py` producing all four canonical parquet tables for 2025/242; freeze 2–3 payloads as gz test fixtures; pytest for decoder + parser (incl. golden values hand-checked against the live fie.org page). Check `fie.org/robots.txt`, note findings for methodology.md.
*Verify:* `ffs scrape --comp 2025/242` writes validated parquet; `pytest` green.
⛔ STOP — commit `feat: FIE scraper + parser, one competition end-to-end`

**M3a — Discovery + shape survey**: `discover.py` (season listing via SSR payload; probe legacy `POST /competitions/search` once and prefer if alive). Scrape a SAMPLE: ~2 competitions from each of seasons 2004, 2008, 2012, 2016, 2020, 2024 — fix parser for old payload shapes / missing poule data (results-only comps must parse with poule metrics null).
*Verify:* sample parses clean; coverage notes in Progress Log.
⛔ STOP — commit `feat: competition discovery + parser robustness across seasons`

**M3b — Bulk historical scrape 2002–2026**: run the full throttled scrape (hours of wall-clock; the gz cache makes it resumable — run in background, monitor, resume on failures). Then `validate_legacy.py` competition-matching report (match by date±1/weapon/gender; fencers by normalized name+country).
*Verify:* canonical parquet covers all seasons; coverage report vs legacy's 204 comps ≥95% matched.
⛔ STOP — commit `data: full historical scrape + canonical tables` (raw_cache stays gitignored; commit parquet only if < ~50 MB, else note in Progress Log and gitignore it)

**M4 — Stats + ELO + H2H**: `stats.py` (all legacy metrics from bout-level data), `h2h.py`, `elo.py`; `ffs validate` parity ≥99% on ≥3 comps vs legacy CSV; draft `docs/methodology.md`.
*Verify:* `ffs build-stats` emits stats/ratings/h2h parquet; parity report ≥99%; ELO top-10 per pool passes the sniff test (known world-class names); `pytest` green.
⛔ STOP — commit `feat: stats engine, ELO ratings, head-to-head`

**M5 — Site data + core pages**: `build_site.py` (JSON artifacts + size report), site shell (vanilla ESM + hash router, vendored ECharts), Home + Fencer search + Fencer profile with rating timeline. **Invoke the `dataviz` skill before writing chart code.**
*Verify:* `python -m http.server -d site` → all three pages work; no eager file >1.5 MB; all fetches relative.
⛔ STOP — commit `feat: static site core (home, search, fencer profiles)`

**M6 — Remaining pages + deploy**: H2H explorer, competition browser + detail (poule grids, DE bracket), methodology page, visual polish, `.github/workflows/pages.yml`.
*Verify:* full local click-through; workflow YAML valid. (Enabling Pages + pushing = ask user.)
⛔ STOP — commit `feat: complete site + GitHub Pages workflow`

**M7 — Proposal + backlog docs**: `docs/proposal.md` (with screenshots of the running site), `docs/backlog-phase3.md`, final README pass.
*Verify:* user-readable, demo link placeholder filled if Pages is live.
⛔ STOP — commit `docs: FIE proposal + phase-3 backlog`

## Risks

- Pre-~2012 payload shapes may differ / poule data absent → Milestone 3 samples early seasons before bulk scrape.
- Cloudflare Turnstile could activate under load → throttle + cache + resumability.
- `site/data/` size (10k fencers × shards) → measured decision point at Milestone 5.

## Key reference files

- `data/update_data.py` — executable spec for all stats to port
- `data/main.py` — legacy parser, poule/DE semantics reference
- `data/updated_results.csv` — validation oracle → `data/legacy/`
- `data/input_new_results.py:72` — token to scrub
- `app/app1.py` — old UI reference for views/filters

## Progress Log

(Copy this plan to repo `PLAN.md` in M0/M1; update the checkboxes THERE after each milestone, with 1–3 lines of notes per completed milestone: deviations, open issues, data sizes.)

- [x] M0+M1 — Restructure + scaffold
  - Moved `app/`, `templates/`, `tesy.py`, `comp_results/`, and the data scripts (`get_data_nacional.py`, `input_new_results.py`, `main.py`, `new_results.csv`, `update_data.py`) into `legacy/`.
  - Scrubbed the leaked GitHub token fragment at `legacy/data/input_new_results.py:72`.
  - Confirmed `final_results/results15dec2022.csv` is byte-identical (md5) to `data/updated_results.csv`; the other 5 snapshots form a strictly increasing row-count/date progression with matching headers — deleted all 6 as redundant, kept `data/updated_results.csv` (moved to `data/legacy/updated_results.csv`) as the sole validation oracle.
  - Added `pyproject.toml` (package `ffs`, console script `ffs`, src-layout), `.gitignore`, stub `src/ffs/cli.py` (argparse, `scrape`/`build-stats`/`validate` placeholders), rewrote `README.md` to point at `PLAN.md`.
  - Verified: `pip install -e .` + `ffs --help` succeed in a clean venv; `data/COL.csv` / `data/EF.csv` untouched (no diff); no stray untracked files.
  - Left `.idea/` as-is (not mentioned in the plan's cleanup scope).
- [x] M2 — One competition end-to-end
  - Done: `devalue.py` (flat-array decoder + `extract_queries`), `fie_client.py`, `schema.py`, `parse.py` — all verified working end-to-end against live `fie.org/competitions/2025/242` (215 entries, 29 pools, 866 bouts, `validate_tables()` clean, champion KANO Koki id 34385 confirmed via B2 final bout winner == results rank 1).
  - **Key discovery not in the original plan:** the SSR payload's paginated `("competitions","results",cid,season,{page,pageSize})` query is frozen at page 1/24 server-side — clicking "next page" in the browser calls a separate plain-JSON REST API, not another SSR render. Found by downloading all 48 `/_fie/*.js` chunks and grepping for the ts-rest contract: **`GET https://fie.org/api/fie/competition/{season}/{compId}/results/ranking?page=N&pageSize=M`** — undocumented, but `pageSize` is honored up to at least 10000 (one request gets everything). Added as `FieClient.fetch_results_ranking()`. robots.txt (`fie.org/robots.txt`) is wide open (`Disallow:` empty), covers `/api/` too.
  - `fie_client.fetch_competition()` follows the real HTTP 301 (`/competitions/{season}/{cid}` → `/tournaments/{season}/{tid}/event/{cid}/...`) and parses `tournament_id` from the resolved URL, since the payload's own `tournamentId` field is null.
  - **Deviation to note in methodology.md:** `bouts.bout_order` for poule bouts is defined as the opponent's 1-indexed seed/row position within the pool's `rows` array (not a true chronological round number — fie.org doesn't expose one; this mirrors how the legacy Excel p1..p6 columns were almost certainly also just seed-ordered sheet columns, but isn't verified). For DE bouts, `bout_order` is just the 0-indexed bracket-slot position within that round's list — a reproducibility aid, not legacy-parity data. Both are optional/best-effort per the plan's `?` annotation on those columns.
  - DE bout status: fie.org uses `status`/`newStatus` `'V'`/`'D'` for normal results, `'E'`/`'EXC'` for withdrawal/injury (mapped to `bouts.status='forfeit'`), and `isBye`/empty status for byes (mapped to `'bye'`, `athlete_b=None`).
  - **Closed out this session:** wired `ffs scrape --comp SEASON/ID [--dump] [--force]` into `cli.py` — fetches, decodes, parses, runs `validate_tables()` (non-zero exit + printed issues if dirty), then merges into `data/canonical/*.parquet` (replaces rows for any competition_id already present, so re-scraping is idempotent; athletes deduped by `athlete_id`, keep-last). `--dump` writes decoded query bodies to `data/raw_cache/dump-{season}-{id}.json` for inspection.
  - Froze two fixtures under `tests/fixtures/` (`competitions-*.json.gz` + `results-ranking-*.json.gz`, same gz-cache format `FieClient` already writes — tests point `FieClient(cache_dir=...)` straight at the fixtures dir so no network is hit): **2025/242** (Men's Epee Worlds, 215 entries — the large fixture, has the tournament's one DE forfeit, pool GIANNOTTE/JORGENSEN `B64`) and **2025/245** (Women's Sabre Worlds, 125 entries — smaller, bye-heavy, no forfeits, different weapon/gender for shape variety). Deliberately did not chase an older-season fixture — surveying pre-2012 payload shapes is explicitly M3a's job, not M2's, and `discover.py` (needed to find real old comp ids) doesn't exist yet.
  - Wrote `pytest` suite: `test_devalue.py` (13 unit tests on hand-built flat arrays — sentinels, holes, shared references, all tag reducers, `extract_queries` key-hashing) + `test_parse.py` (golden tests against both fixtures: entry/bout counts, champions — KANO Koki 34385 for 242, EGORIAN Yana 25208 for 245 — full 7-fencer/21-bout poule 1 of 242, the B2 gold-medal bout score 9–10, the one DE forfeit, `validate_tables()` clean on both) + `test_schema.py` (empty_table columns, validate_tables catches each invariant violation individually). **30/30 pass.**
  - `ffs scrape --comp 2025/242` and `--comp 2025/245` both run clean end-to-end against live fie.org through the full CLI path (not just library calls) and produced `data/canonical/{competitions,athletes,results,bouts}.parquet` (2 comps, 340 athletes, 1337 bouts total) — gitignored per plan, not committed; only `tests/fixtures/` (the 4 gz payloads) and the code are.
  - Environment: created `.venv/` (gitignored, not present before this session) and `pip install -e ".[dev]"` — no dependency changes needed, `pyproject.toml` already had pandas/pyarrow/requests/beautifulsoup4/pytest.
- [x] M3a — Discovery + shape survey
  - `discover.py` uses `GET /api/fie/competitions` (a plain REST endpoint, reverse-engineered from the ts-rest contract in the site's `cHy4glSy.js` JS chunk) rather than an SSR page — fie.org has no SSR-rendered per-season competition listing (the `/competitions` URL 301s to `/events`, which only embeds *upcoming* tournaments + the seasons list via vue-query; per-season archives aren't SSR'd anywhere). This is a deviation from the plan's literal "SSR payload" wording but same spirit (found via the same JS-chunk-grepping technique M2 used for the results-ranking endpoint).
  - Probed the legacy `POST /competitions/search` endpoint mentioned in the original plan: dead, 404 on every guessed path (`/competitions/search`, `/api/competitions/search`, `/api/fie/competitions/search`). The REST endpoint above supersedes it, so no fallback logic needed.
  - **Two server-side quirks discovered and documented in `fie_client.py`'s docstring:** (1) the `category` query param (S/J/C/V/GV) is accepted by the endpoint's zod schema but silently ignored — filtering by it server-side returns an identical unfiltered `totalFound` regardless of value; `discover.list_competitions` filters `category` client-side instead. (2) `season` itself isn't validated — an out-of-range value (e.g. 1913) silently no-ops the season filter and returns fie.org's *entire* unfiltered competitions table rather than an empty page; `ffs discover` now checks the requested season against `fetch_seasons()` first and errors out if it's not in the known range (1953–2027 as of 2026-07-14). `weapon`, `gender`, and `type` ('I'/'E') *are* honored server-side (verified: each partitions `totalFound` correctly).
  - Added `FieClient.fetch_seasons()` and `FieClient.fetch_competitions_list()`; factored the pagination loop shared with `fetch_results_ranking()` into a private `_fetch_paginated_json()` helper.
  - Added `discover.py` (`list_competitions()`) and an `ffs discover --season YYYY [--weapon] [--gender]` CLI subcommand (prints Senior Individual competitions for a season — usable both for manual inspection and, later, to drive M3b's bulk scrape loop).
  - **Shape survey result: no parser changes were needed.** Sampled 2 Senior Individual competitions per season for 2004, 2008, 2012, 2016, 2020, 2024 (12 total, picked for weapon/gender diversity — see selection script in session transcript) and ran the full `ffs scrape` pipeline against each live. All 12 parsed cleanly with `validate_tables()` clean, including: pre-~2016 Olympics/Championships that are **results-only** (zero pool and zero tableau data recorded in fie.org's archive — `pools: []`, `tableau: []`, but a populated final-ranking list and, curiously, a populated `pool/results` summary table even without match-level detail) and one genuinely **fully-empty competition** (`2004/433`, a qualification event with 0 ranking items, 0 athletes, 0 everything — fie.org has the competition's metadata but never digitized any results for it). The M2 parser's "empty list -> empty rows, no crash" design already covered every shape encountered; `bouts` count only becomes nonzero from ~2016 onward in this sample (fie.org's archive appears to start including pool/tableau match-level detail around then, not just final rankings).
  - Open issue for M3b to decide: whether to skip/flag competitions with 0 ranking items (like `2004/433`) during the bulk historical scrape, or keep them as empty rows in `competitions.parquet` for completeness.
  - Froze `tests/fixtures/competitions-list-2004-I.json.gz` (260 rows, real 2004 season listing, `type=I`) and `tests/fixtures/seasons.json.gz` (75 seasons, 1953–2027) as new fixtures; wrote `tests/test_discover.py` (4 tests: seasons range, client-side category filtering against the real mixed-category fixture, weapon/gender filtering, empty-filter result). **34/34 tests pass** (30 from M2 + 4 new).
  - No canonical parquet from the 12 sampled scrapes was committed (gitignored per plan, as in M2).
- [x] M3b — Bulk historical scrape 2002–2026
  - Built `ffs scrape-all --from YYYY --to YYYY [--weapon] [--gender] [--force] [--max-consecutive-fails N]`: iterates seasons, skips competitions already in `data/canonical/competitions.parquet` (resumable), flushes per season (not per competition) to bound I/O overhead, logs per-competition failures to `data/raw_cache/scrape_failures.json` and aborts after N consecutive fails. Zero-result competitions are kept as rows (empty tables) for browsing completeness, per M3a's decision.
  - Wrote `validate_legacy.py` (`load_legacy_competitions`, `match_competitions` on weapon+gender+`start_date`±1 day, `normalize_name` reserved for M4 fencer-level matching) wired to `ffs validate`.
  - Root-caused and fixed (`999e009`) a validation bug where `validate_tables()` raised and dropped an entire competition over one "Deleted Fencer" placeholder athlete or a rare real-athlete/no-ranking-entry archive gap — `_scrape_one` now tolerates only this specific issue class, recovering ~10 previously-dropped competitions.
  - **Full run completed 2026-07-21** across two background sessions (interrupted once by a session-teardown SIGKILL, fixed with `loginctl enable-linger`; interrupted again by an actual machine reboot, which linger can't protect against — resumed both times via disk-cache-backed replay with no real data loss). Final tally: **3092 competitions, 2002–2026, 0 unresolved failures** (795 in the last run + 2297 resumed-skip from earlier flushes).
  - `ffs validate`: **286/286 legacy competitions matched (100%)**, well above the 95% target.
  - `data/canonical/` is **5.2 MB** (athletes 620K, bouts 3.8M, competitions 64K, results 732K) — comfortably under the 50MB threshold, so it's committed (un-gitignored); `data/raw_cache/` (HTTP cache) stays gitignored.
  - `pytest`: 41/41 green, including `test_validate_legacy.py` and `test_cli_scrape_all.py` added in the prior session.
- [x] M4 — Stats + ELO + H2H
  - `stats.py`: ported every legacy metric from bout-level data. Two real bugs found and fixed against live data before this was trustworthy: (1) `PIND` was wrongly assumed to be touches-scored-minus-received (`PT-DIFF`); verified against the legacy CSV's actual `poule_ind` values that it's really `PVICT / (poule matches played)`, a win ratio — `PT-DIFF` is computed separately and isn't in the parity list. (2) `Q` was `NaN` instead of legacy's explicit `0` for athletes who competed in a DE-having competition but never qualified past poules — `_de_stats` now emits explicit `Q=0`/`T64+=0`/`TPRE64=0` rows for every non-qualifier. These two fixes alone took fencer parity from 82.9% → 98.7%. Also fixed: `PEXMPT` now derives from bout presence rather than fie.org's own `results.exempt` flag, which disagreed with bout-level ground truth for at least one real athlete (2025-242's champion KANO Koki).
  - `parse.py` (M2 file, root-cause fix): poule bouts with `score_a==0 and score_b==0` — a fenced bout can never legitimately end 0-0 — were being classified `status='ok'` (a no-show default result fie.org still tags with a normal winner flag), contaminating every poule numeric stat. Now classified `'forfeit'` (winner kept), matching legacy's "D with tr=0" exclusion. Applied retroactively to the already-scraped `bouts.parquet` (4,422 poule rows reclassified `ok`→`forfeit`) rather than re-scraping all 3092 competitions; a fresh `scrape-all` run would produce the same result directly. This took overall parity from 98.7% → 99.3%, clearing the ≥99% gate.
  - `elo.py`/`h2h.py`: ran against the full ~866k-bout dataset for the first time, no bugs found (no dtype/sort issues on nullable `Int64` columns). ELO sniff test passes: top-10 per (weapon, gender) pool surfaces unambiguously correct world-class names (OH Sanguk, SZILAGYI Aron, GRACHEVA Inna, MASSIALAS Alexander, BOREL Yannick, KANO Koki, KHARLAN Olga, VOLPI Alice, etc).
  - **Final `ffs validate` parity: 99.3% overall** (286/286 comps matched 100%; POS 100.0%, PVICT 99.1%, PTD 98.8%, PTR 98.9%, PIND 98.7%, Q 99.9%, TMVAVG 99.8%) across 45,848 matched fencer-rows in 279 competitions — clears the mandatory ≥99% gate. `PTD`/`PTR`/`PVICT` sit just under 99% individually; traced to genuine fie.org archive gaps (specific pools missing individual bout rows entirely, e.g. `2020-385` pool 29) rather than a parser bug — an accepted, already-anticipated limitation since the combined rate clears the gate.
  - `ffs build-stats` produced `data/canonical/{stats_fencer_comp,ratings_history,h2h,h2h_bouts}.parquet` (259,894 / 144,968 / 413,194 / 512,656 rows) — `data/canonical/` totals 17 MB, comfortably under the 50 MB threshold, so committed.
  - Wrote `tests/test_stats.py`, `tests/test_elo.py`, `tests/test_h2h.py` (fixture-based golden values for stats, toy sequences for ELO/H2H per the plan's verification section) plus a synthetic-payload unit test for the parse.py 0-0→forfeit fix. `pytest`: 60/60 green (41 prior + 19 new).
  - Drafted `docs/methodology.md`: full metric/ELO/H2H specs, all legacy deviations above, the parity numbers, and the M2-era robots.txt finding (wide open, `Disallow:` empty, covers `/api/`).
- [x] M5 — Site data + core pages (DONE — data pipeline in `3208934`, site shell + pages in this session's commit)
  - Done so far: `build_site.py` (`ffs build-site` CLI command) generates all `site/data/*.json` artifacts from canonical parquet: `meta.json`, `fencers/index.json` (17,118 entries -- only athletes with >=2 competition results get a search-index entry + profile shard, per the plan's shard-pruning guardrail, so search never links to a missing profile), `summary/{weapon}{gender}.json` (6 files: `em/ef/fm/ff/sm/sf.json` -- ELO top-200, recent competitions w/ champion, titles + podiums leaderboards, all pool-scoped), and `fencers/{id%100}/{id}.json` (17,118 shards: career-per-weapon summary, every competition result + stats row, full rating timeline for the profile chart, top-10 rivals by h2h bout count).
  - **Naming deviation from the plan's literal text:** used `{weapon}{gender}` two-letter codes (`ef` = Epee+Female) instead of the plan's `me/mf/we/wf/se/sf` list, which double-books `w` between "women" and "weapon" and is ambiguous. Weapon is always `e/f/s`, gender always `m/f`, so `{weapon}{gender}` gives 6 unambiguous codes.
  - **Performance fix during this session:** the first implementation filtered the full-size `results`/`stats_fencer_comp`/`ratings_history`/`h2h` tables with a boolean mask once per athlete (17,118 athletes x ~1.1M total rows across those tables) -- projected to take way too long and was killed after 2+ minutes with no output. Rewrote as a `ProfileContext` that pre-groups each table into a `{athlete_id: sub-dataframe}` dict ONCE (`_group_dict`, one `groupby` pass each), including a `_h2h_by_athlete` helper that reshapes the unordered-pair `h2h` table into an athlete-centric perspective (two renamed copies concatenated, then grouped) so "my rivals" is a single dict lookup instead of an OR-filter over 413k rows. Full run: **6m29s, exit 0**, `site/data/` totals **93 MB** (92 MB of it is the 17,118 fencer shards, ~5.4 KB average each).
  - **Size decision:** 93 MB is well over the ~50 MB precedent used for `data/canonical/` -- decided NOT to commit `site/data/` (added to `.gitignore`); M6's GitHub Pages workflow should run `ffs build-site` as a build step before `upload-pages-artifact` rather than committing generated JSON. Spot-checked output against known-real fencers for sanity (KANO Koki's 83-comp career/rating timeline, POPESCU Ana Maria's 20 epee titles, KONG Man Wai Vivian's #1 women's epee ELO -- all plausible/correct).
  - Vendored `site/vendor/echarts.min.js` (v5, ~1.01 MB via jsdelivr) -- committed since it's a static dependency, not generated data; lazy-loaded per the plan so it doesn't count against the eager-file guardrail.
  - `pytest`: 60/60 still green (no build_site.py tests written yet -- TODO next session, plus the site shell itself).
  - **Not started yet:** the site shell (`index.html`, hash router, `css/`, `js/`) and the three pages (Home, Fencer search, Fencer profile w/ rating chart) -- this is the bulk of the remaining M5 work. **Must invoke the `dataviz` skill before writing the rating-timeline chart code.**
  - **2026-07-23 session (M5 closed):** built the site shell and all three pages, vanilla ESM + hash router, no build step.
    - Files: `site/index.html` (shell: header/nav/theme toggle/footer), `site/css/style.css`, `site/js/{app,data,util,chart}.js`, `site/js/views/{home,search,fencer}.js`.
    - Router: `#/` (home, `?pool=` selects the pool) · `#/search` (`?q=`, `?pool=`) · `#/fencer/{id}`; unknown routes get a 404 view. Views are dynamically `import()`ed per route; every fetch is a relative path (`data/…`, `vendor/…`) so a GitHub Pages project subpath works unchanged.
    - Home: 6-button pool selector, rating leaders (ELO top-20), recent competitions w/ champion, most titles / most podiums. Search: whole 1 MB index held in memory, no debounce needed, prefix-first ranking, accent-folded matching, weapon/gender chips, capped at 100 rendered rows. Profile: career cards per weapon, rating timeline chart, most-met opponents, full results table (POS/PVICT/PIND/PTD/PTR/TMVAVG — note `PTD`/`PTR` are poule **totals**, `TMVAVG` is **DE wins**, per `stats.py`).
    - Chart (`js/chart.js`, dataviz skill invoked first): ECharts lazily injected from the vendored bundle on first profile view, SVG renderer, single series so no legend, 2px line + 10% area wash, hairline solid grid, direct end-label, crosshair tooltip, `<details>` table view as the non-visual fallback. Colours read from CSS tokens (`--series-1` = `#2a78d6` light / `#3987e5` dark, both validated by the skill's `validate_palette.js` against their surface) and re-render on theme change.
    - **Correctness detail:** ratings are per (weapon, gender) pool, so a multi-weapon fencer gets a weapon picker (default = most-rated weapon) rather than one line splicing two rating scales; weapons with <2 rated comps are dropped from the picker (nothing to plot), and a fencer with no plottable weapon gets a notice instead of an empty chart.
    - Also fixed in `build_site.py`: `_load_tables()` now strips athlete names (236 fie.org names carry leading whitespace and sorted ahead of everything in the search index). Local `site/data/` was being regenerated with this fix at session end — **re-run `ffs build-site` if unsure**; nothing is committed either way.
    - Verified with headless Chrome against `python -m http.server -d site` (no browser extension in this session): all 7 routes render, **zero console errors/rejections**, desktop + 390px mobile screenshots checked in light and dark, `documentElement.scrollWidth == viewport` at 375px (wide tables scroll inside `.table-scroll`, not the page). Eager files: `index.json` 1.03 MB, `meta.json` 4 KB, summaries 24 KB each — all under the 1.5 MB guardrail; `echarts.min.js` (1 MB) is lazy so it doesn't count.
    - `tests/test_build_site.py` added (9 tests: meta counts, index pruning/multi-weapon, the name-strip fix, pool scoping + empty pool, profile career/results/timeline, h2h perspective flip, null fields). `pytest`: **69/69 green**.
- [x] M6 — Remaining pages + deploy
  - `build_site.py` now emits the three artifact families M5 deferred: `competitions/index.json`
    (short-key rows, ~548 KB), `competitions/{competition_id}.json` (ranking + poule grids + DE
    rounds), and `h2h/{lo}-{hi}.json` for pairs with **>=5** meetings (~2.2k files).
  - **Design decision (deviation):** a pair file per pair would be 413k files, so each fencer shard
    also gained `h2h_all` — a compact `[opponent_id, weapon, bouts, wins, last_met]` row for *every*
    opponent that has a profile. The H2H explorer therefore answers "have these two ever met?"
    exactly for any indexed pair, and only fetches a pair file for the bout-by-bout list.
  - Poule grids reconstruct fie.org's own row order from `bout_order` (= the row position of the
    larger id in each pair, so every fencer but the lowest-id one is placed directly and that one
    takes the leftover slot). Verified over a 60-competition sample: 1059/1068 poules resolve
    exactly, 9 have 2 unplaced fencers and 11 have a duplicate/out-of-range position (archive
    gaps) — those fall back to id order, so the grid is still complete.
  - DE round ordering is a documented best-effort (`_ROUND_PREFIXES`): fie.org runs a preliminary
    "A" tableau into the main "B" one (`A256 → A64`, then `B64 → B2` = the final), with older
    seasons also using `F*`, `pre*`, `PD*` and bare round numbers.
  - New views: `competitions.js` (browser: search + season select + pool chips), `competition.js`
    (podium, ranking, poule grids, scrolling bracket), `h2h.js` (two pickers, record card, bout
    list), `methodology.js` (reader-facing summary of `docs/methodology.md`). Router, nav,
    cross-links (home/profile → competition, rivals → H2H) and CSS updated.
  - `.github/workflows/pages.yml` added: builds `site/data/` with `ffs build-site` from the
    committed canonical parquet (no scraping in CI) before `upload-pages-artifact`.
  - `pytest`: **76/76 green** (69 + 7 new build_site tests).
  - **2026-07-23 session (M6 closed):** regenerated `site/data/` end-to-end (~20 min; the `pd.NA`
    city crash from the previous run did not recur) and verified the whole site headlessly.
    - Size report: **146 MB** total — `fencers/*` 111 MB (17,118 files), `competitions/*` 30 MB
      (3,092), `h2h/*` 3.1 MB (2,243). Eager files all well under the 1.5 MB guardrail:
      `fencers/index.json` 1002 KB, `competitions/index.json` **472 KB**, summaries 23 KB, meta 0.2 KB.
    - Verified 12 routes × light/dark at 375px (the four new ones plus home/pool-switch/search/
      profile/404, and two edge competitions: `2025-242` = 215 entries/29 poules/9 rounds, and
      `2004-433` = the fully-empty archive row): **zero console errors or unhandled rejections,
      and `documentElement.scrollWidth <= 375` everywhere**. Spot-checked against M2's golden data:
      poule 1 of 2025-242 and the B2 final SIKLOSI 9 – KANO 10 both render correctly.
    - Fixed during verification: **`grid-2`/`grid-3` used a bare `minmax(420px, 1fr)` floor, which
      can't shrink — the home page scrolled sideways at 375px**; now `minmax(min(420px, 100%), 1fr)`.
      Same class of bug in `.poule-list`, whose implicit `auto` track sized itself from the poule
      grid's max-content width (competition detail page was 700px wide at a 375px viewport); now an
      explicit `minmax(0, 1fr)`.
    - Polish: DE round codes of 2/4/8 now read Final / Semi-final / Quarter-final instead of
      "Table of 2" (checked across all 3,092 competitions — a table of 2 or 4 is always the real
      one; a preliminary tableau always feeds the main one well above that size); competition
      ranking defaults to the top 16 rather than 64 so the poules and bracket aren't buried;
      filter/picker `<label>`s forced to `display:block` (the season label sat beside its select);
      prose capped at 72ch on the methodology page; bout/poule/entry count pluralisation.
    - Also fixed `build_site.build_meta`'s `pd.Timestamp.utcnow()` deprecation (→ `.now("UTC")`),
      the one warning `pytest` emitted. `pytest`: **77/77 green.**
    - **Pages is not enabled and nothing has been pushed** — that needs the user's go-ahead.
- [x] M6.5 — Data foundations for the advanced-metric work (this session, 2026-07-23)
  - Context: a review against the legacy Dash app found three of its analytical features were
    never carried over (advanced-metric table + comparison, metric-over-time chart, by-age
    trajectory curves) plus an unexplained ratings card and one wrong column name. Plan for
    M6.5–M6.8 lives in `~/.claude/plans/it-looks-good-but-sprightly-snail.md`. M6.5 is the
    data layer only — no new UI.
  - **`T96+` → `TPRE64` everywhere.** "Table of 96" was a legacy invention, not FIE
    terminology; the flag really counts entries into the *preliminary* tableau feeding the
    table of 64 (fie.org round code `A64`). `T64+` keeps its name. The only surviving `T96+`
    strings outside `legacy/` are the three places that explain the rename. `ffs validate`
    re-run after the rename: **286/286 competitions matched, fencer parity 99.3% unchanged**
    (POS 100.0%, PVICT 99.1%, PTD 98.8%, PTR 98.9%, PIND 98.7%, Q 99.9%, TMVAVG 99.8% over
    45,848 rows) — as expected, `T96+` was never a parity metric.
  - **New `src/ffs/metrics.py`** — the metric registry, one `Metric(code, label, short, group,
    agg, better, fmt, den, blurb)` per column, serialized into `meta.json` so no JS view ever
    hardcodes a label, an aggregation or a sort direction. `agg`/`better` are ports of legacy's
    own choices (`update_table_ind`'s aggregation dict: `T64+`/`TPRE64` summed, everything else
    averaged including `POS`; `indres-graph`'s reversed `POS` axis).
    - `den` is an addition to the planned signature and the non-obvious part: metrics have
      genuinely different populations (a fencer's 40 results can hold 40 `POS` values but only
      12 `PVICT` and 9 `TTR`, because pre-~2016 competitions carry no bout data), so
      re-aggregating pre-summed rows needs eight distinct denominators, not one row count.
  - **`meta.json`** (7.3 KB) now also carries `level_groups` (fie.org's `A/GP/CHM/JO/OF/CHZ/
    SA/NF` bucketed into `WC/GP/WCH/ZON/SAT/NAT/OTH`, `OTH` as catch-all), `default_level_groups`
    (`WC`+`GP`, as legacy defaulted), `cohort_tiers` and `path_series`.
  - **Fencer shards carry all 23 metrics** instead of 11, as a fixed-order `"m"` array keyed by
    the registry rather than named keys. This was genuinely size-neutral as predicted: shards
    total **108 MB, marginally *down* from M6's 111 MB** — dropping 11 repeated key strings per
    result row paid for the 12 extra values. Career blocks gain `peak_rating` and
    `peak_pool_rank` (rank of that peak among profiled fencers of the pool).
  - **New `explore/{pool}.json`** (6 lazy files, 2.2–4.5 MB each, 19 MB total): one row per
    (athlete, season, level group), `[athlete_id, season, level_group_index, ...8 counts,
    ...23 metric sums]`. Sums, not means — the client sums the rows the reader's filters select
    and divides once at the end, which is the only way any season-range × level-group subset
    comes out right (the mean of per-season means is not the mean).
  - **New `paths/{pool}.json`** (6 lazy files, ~90–96 KB each): for each cohort tier
    (`top10/top32/top100/all`) and each of 29 series, the by-age distribution
    `{age: [n, mean, p25, p50, p75]}` over ages 12–45, ages with <3 members omitted. Cohort =
    peak **FencingFastStats rating** rank within the pool — there is no FIE ranking anywhere in
    this dataset, so this must be labelled as the project's own measure wherever it appears
    (M6.8's job). Series = the 23 metrics plus rating, competitions/year and the four
    round-entry rates (T64+, TPRE64, podium, title) that replace legacy's `fieresults-graph`.
    Sniff test, men's épée top-10 cohort: mean `POS` 116 at 18 → 47 at 23, mean rating
    1615 → 1846, `T64+` rate 13% → 57%. Plausible.
  - `cli.py`'s eager-size guardrail now keys off an explicit `is_eager()` prefix list rather
    than "does the report line contain a bracket" — `explore/*` and `paths/*` are lazy and
    would otherwise have tripped it.
  - `site/js/views/fencer.js` reads the new `m` array through a registry-driven `metricReader`.
    No other view consumed named metric keys.
  - Full rebuild: `ffs build-stats` (4m) → `ffs validate` → `ffs build-site` (~23m). **Total
    `site/data` 162 MB** (fencers 108, competitions 30, explore 19, h2h 3.1, paths 0.6).
    Eager files still well under the 1.5 MB guardrail: `fencers/index.json` 1002 KB,
    `competitions/index.json` 472 KB, summaries 23 KB, `meta.json` 7.3 KB.
  - Verified 6 routes × light/dark at 375px headlessly (home, search, RODRIGUEZ John Edison's
    profile, Errigo–Kiefer H2H, 2025-242, methodology): **zero console errors or unhandled
    rejections, `scrollWidth <= 375` everywhere**, and the profile's results table renders the
    same values the shard holds. `pytest`: **86/86 green** (77 + 9 new: registry round-trip,
    level-group coverage, explorer row keying/sums/counts/pruning, peak-rating ranks, cohort
    membership, by-age distributions, sample floor).
- [x] M6.6 — Ratings explainer + Metrics Explorer page (this session, 2026-07-23)
  - **New route `#/explore?pool=&…`** (`site/js/views/explore.js`, nav entry "Metrics"): legacy's
    `update_table_ind` DataTable rebuilt over `explore/{pool}.json`. Pool chips, season range,
    level-group chips, country, min-competitions and name filters; sortable on every column
    (click, shift-click to add a tie-breaker) with the first direction taken from the registry's
    `better`; column-group toggles (overall / poules / DE); sticky name column inside
    `.table-scroll`; row checkboxes with a selection bar. All filter state round-trips through
    the hash via `history.replaceState`, so a view is linkable without pushing history entries.
  - **New `site/js/metrics.js`** — the shared registry reader (formatting per `fmt`, initial sort
    direction per `better`, and the explorer-row aggregation). M6.7/M6.8 read metrics through it
    rather than re-deriving any of that.
  - Aggregation is the whole trick and it lives here: sum the rows the filters select, then
    divide each metric's sum by the count named by its `den` — never by the number of
    competitions entered. 1,579 men's épée fencers pass the default filters (WC+GP, ≥5 comps)
    and re-aggregate in a few ms per keystroke.
  - **Ratings explainer**: `docs/methodology.md`'s Elo section now opens with an explicit "these
    ratings are not an FIE ranking" statement (the FIE's points were never scraped; legacy read
    them from a spreadsheet that has no equivalent here), and gains a `metrics.py` registry
    section explaining `den`. `site/js/views/methodology.js` mirrors it: a rewritten rating
    section with the formula, all four constants and the ordering caveat, plus a metric glossary
    **generated from `meta.json`'s registry** rather than a hand-kept list — a metric can no
    longer be described differently from how it is computed. Sections are deep-linkable
    (`#/methodology?s=rating`, `?s=glossary`); the profile's rating card and the explorer link in.
  - **Data bug found by the new table and fixed (needed a rebuild).** fie.org marks an entrant
    with no final ranking (withdrawn / did not start) with a sentinel `final_rank` of `999` or
    `9999`, and 1,463 of 259,894 stats rows carried one as a real placing. Averaged, it wrecks
    `POS`: LIMARDO GASCON Ruben showed a mean place of **218** over 159 World Cup/GP entries
    (median 20) because three of them were 9999s. The legacy CSV has no such values, so nulling
    them is also the legacy-faithful choice. `schema.RANK_SENTINEL_MIN` + `schema.clean_final_rank`
    now null them at three boundaries: on parse (future scrapes), in `stats.compute_stats` (parquet
    written before this was understood) and in `build_site._load_tables` (so a competition's
    results table can't print "#9999"). `ffs validate` re-run: **286/286 matched, parity 99.3%
    unchanged** (POS still 100.0%). Rebuilt `build-stats` (4m) → `build-site` (~23m).
  - Verified headlessly at 375px and 1280px in both themes (`#/explore` for two pools,
    `#/methodology`, `#/methodology?s=rating`, RODRIGUEZ John Edison's profile): zero console
    errors or unhandled rejections, `scrollWidth <= viewport` everywhere. `pytest`: **88/88
    green** (86 + the sentinel tests in `test_stats.py` / `test_schema.py`).
  - Deviation from the plan: the "Compare selected" action was to point at `#/compare?ids=…`,
    which M6.7 builds. Rather than ship a link to a 404, the selection bar shows the picked
    fencers and offers head-to-head when exactly two are selected; M6.7 swaps in the compare
    route using the same selection state.
- [x] M6.7 — Profile metric chart, per-season table, H2H metric comparison (this session, 2026-07-23)
  - Pure UI over the existing shards — no rebuild, no new data artifact, no change to
    `site/data/`. (M6.6's finished work was still uncommitted at the start of this session; it
    was committed as `b6fa7c6` before M6.7 began.)
  - **New `site/js/metricview.js`** — the one implementation of the advanced-metric UI, used by
    three views: the filter bar (metric picker, season range, level-group chips, per-season /
    per-competition toggle), the metric-over-time chart, the side-by-side comparison table and
    the season-by-season table. Nothing about a metric is re-derived here: label, blurb, format,
    aggregation and sort direction all come from the registry through `metrics.js`.
  - **Aggregation from raw shard rows** (`metrics.aggregateResults`): the explorer re-aggregates
    pre-summed rows, but a profile holds one raw value per competition, so the same rule had to
    be re-implemented — sum, then divide by the population that actually carries the metric.
    The `den` → representative-column mapping is *derived* in JS as "the first metric in registry
    order with that `den`", which reproduces `metrics.COUNT_SOURCE` exactly (all eight keys
    checked) rather than shipping a second copy of it in `meta.json`.
  - **`#/compare?ids=a,b,…`** (`site/js/views/compare.js`): fencer chips + type-ahead add, up to
    **6** fencers (one categorical colour slot each), missing shards and over-length id lists
    reported rather than fatal. Filters round-trip through the hash with `replaceState`. The
    explorer's selection bar now links here (M6.6 had deferred it to avoid shipping a 404) and
    keeps its two-fencer head-to-head link.
  - **Profile** gains the metric chart, the season-by-season table (with an "All seasons" row)
    sharing one filter state with it, and a "Compare with another fencer" picker that hands off
    to `#/compare`. **H2H** keeps the record card and bout list and gains the same chart plus
    the two-column comparison table, so profile → "Compare" no longer dead-ends at bouts only.
  - `site/js/picker.js` extracted from `h2h.js` (one type-ahead used by all three views);
    `chipRow`/`pressOnly`/`toggle` moved from `explore.js` into `util.js`.
  - **Chart work** (dataviz skill invoked first): `chart.js` now has a shared mount/theme/resize
    core plus `renderMetricChart` — multi-series, legend from two series up, direct end-labels
    only up to four, `POS`-style metrics on a reversed axis (legacy did the same), one line per
    fencer × weapon with colour following the *fencer* and a dashed line for their second weapon.
    Categorical slots 2–6 added to `style.css` from the dataviz reference palette; the six-slot
    set was validated with the skill's `validate_palette.js` in both modes (worst adjacent CVD
    ΔE 9.1 light / 8.4 dark, normal-vision 19.6 / 19.3). Three light-mode slots sit under 3:1 on
    the light surface, so the relief rule applies — every chart ships a `<details>` table view.
  - Two chart bugs found by looking at the rendered PNG rather than the DOM: the season x-axis
    was a value axis anchored at 0 (every point crushed into the right margin — fixed with
    `min/max: dataMin/dataMax`), and an inverted y-axis put its `nameLocation:"end"` label on top
    of the first x tick (axis name dropped; the picker and the note under the chart name the
    metric).
  - Verified headlessly at 375/390/420px and 1280px in both themes: profile (21208, 10222),
    `#/compare` (2 fencers, 4 fencers, a 7-id link with a missing shard and an over-cap id, and
    an empty `ids=`), `#/h2h` for a met pair and a never-met pair, `#/explore`. **Zero console
    errors or unhandled rejections, `scrollWidth <= viewport` everywhere.** Spot-check against
    the shard: Errigo's 2015–2020 WC+GP window holds 60 competitions but only 20 with poule data,
    and the chart plots exactly those 20 with a mean `PIND` of 81.3% — the wrong denominator
    (60) would have read 27%.
  - `pytest`: **88/88 green** (unchanged — this milestone added no Python; the site has no JS
    test harness, so verification is the headless-Chrome acceptance run above).
- [x] M6.8 — Trajectories page + polish and close-out (this session, 2026-07-23)
  - Pure UI again: no rebuild, no new data artifact. `paths/{pool}.json` was generated back in
    M6.5 and is read as-is.
  - **New route `#/paths?pool=&tier=&metric=&ids=`** (`site/js/views/paths.js`, nav entry
    "Trajectories"), the merged and generalised form of legacy's `rank-graph` +
    `fieresults-graph`: pool chips, cohort tier chips (Top 10 / 32 / 100 / all), a series picker
    over the 23 registry metrics **plus** the six `path_series` extras (rating, comps entered,
    T64+/TPRE64/podium/title rates), and up to five overlaid fencers through the shared
    `picker.js`. Every control round-trips through the hash with `replaceState`.
  - **Cohort curve = median with a p25–p75 band**, an improvement on legacy's bare mean: the
    band is what makes "on track" legible. The mean, the quartiles and `n` ride the median's
    tooltip and the table view. The caption on the page — and a new deep-linkable
    `#/methodology?s=cohorts` section, mirrored in `docs/methodology.md` — say that a cohort is
    a **peak FencingFastStats rating** rank, never an FIE ranking, and that a fencer's curve
    only reflects what fie.org's archive holds.
  - **An overlaid fencer's own curve is computed client-side** from their shard by the rule the
    cohort was built with: one value per (fencer, age), age = calendar year − birth year, means
    through `metrics.aggregateResults` (so the denominator is the population that carries the
    metric), rating from the `rating_timeline`'s last point of that year, and the four rates as
    the share of that year's entries. `cohort_ids` is used to mark a fencer who is himself part
    of the curve he is being compared against; a fencer with nothing in the selected pool is
    named, with the pools they do fence, instead of silently missing a line.
  - **Chart work** (dataviz skill invoked first; three bugs, all invisible in the DOM and all
    found by looking at rendered PNGs):
    - The band was first built as two stacked lines — the standard recipe, and **wrong on a
      cartesian value/value axis**: ECharts stacks the *x* dimension too, which folded the band
      onto the baseline and doubled the x extent (ages ran to 72). It is now a `custom` series
      drawing one polygon, with the quantiles still declared through `encode` so both count
      towards the axis extents.
    - The horizontal legend wraps but never tells the grid, so at 375px its second row landed on
      the top y tick. `grid.top` now follows an estimated legend row count, and `mount()` passes
      the container width into the option builder and rebuilds on a real width change — this
      fixed the same latent bug on `#/compare` with five or more series.
    - `containLabel` reserves room for tick labels but not for an axis *name*, so the new "Age"
      axis label needed its own bottom inset.
  - **`.select` had no `max-width`**, so a wordy option label ("Share of entries reaching the
    preliminary table") pushed the whole page 57px wider than a 375px screen — the first
    horizontal overflow the site has had. Fixed in `style.css` for every select.
  - Cross-links added: the profile's compare card → `#/paths?pool=…&ids={id}`, and the home
    page's rating-leaders card → the pool's trajectories.
  - **Close-out**: `README.md` rewritten with the page-by-page feature list and the real CLI
    workflow (it still said "Currently a stub"); `docs/methodology.md` gained the trajectories
    section. `T96+` survives outside `legacy/` only in prose *about* the rename (`stats.py`,
    `metrics.py`'s blurb, `docs/methodology.md`, this file) — never as a live metric name.
  - Verified headlessly at 375px and 1000–1280px in both themes across six route variants, plus
    a scripted interaction pass (pool switch → tier switch → metric change → drop a fencer →
    open the table view): **zero console errors or unhandled rejections, `scrollWidth <=
    viewport` everywhere**, and `#/explore`, `#/compare` and `#/fencer` re-checked for
    regressions. Spot-check against the source: KANO Koki's rating at age 27 is 2014.3 and the
    men's épée top-10 median at 27 is 1964.6 — both exactly as plotted.
  - `pytest`: **88/88 green** (no Python changed this milestone).
- [ ] M7 — Proposal + backlog docs

### Out-of-band: 2026 World Championships data refresh (2026-07-30)

Not a milestone — the first live data refresh since the historical scrape, run because the
Senior Worlds (Hong Kong, 22–27 July 2026) had finished.

- **Found a bug that made the archive un-refreshable.** `cmd_scrape_all` called
  `list_competitions()` without passing `force`, so it read the season's competition listing
  from `data/raw_cache/competitions-list-{season}-I.json.gz`. That cache was written during the
  historical scrape, so a season still in progress could never gain competitions and
  `ffs scrape-all` reported "nothing new" forever. `--force` was not the escape hatch — it only
  reaches `_scrape_one`, and it would re-scrape the whole range.
- The season loop is now `_scrape_seasons()`, shared by `scrape-all` and the new `ffs update`.
  It **always re-fetches the newest requested season's listing** (only that season can grow, so
  one extra request even on a 2002–2026 replay); `scrape-all --refresh-lists` forces all of
  them. `_scrape_seasons` returns `{ok, skipped, failed, aborted, new_competition_ids}`.
- **`ffs update`** is the routine path: refresh listings → scrape what's new → `build-stats` →
  print what landed. It defaults to the newest canonical season **and the one after it**, which
  is what makes the September season rollover need no flag. `--build-site` chains the site build.
- **`hasResults` is a lie** — all six Worlds events report `hasResults: 0` with full brackets
  published, as do the already-scraped Asian Championships. It is deliberately not used as a gate.
- **fie.org's CDN served a stale listing** (252 rows, pre-Worlds) on the first `ffs update`; an
  immediate retry got the current 258. Noted in the runbook — retry before investigating.
- Result: 3,092 → **3,098 competitions**, +1,029 result rows, +3,711 bouts, 2026 season 109 →
  115. `ffs validate` still 286/286 matched, parity 99.3%. `pytest` 97/97 (88 + 9 new).
- **`docs/updating.md`** is new — the refresh runbook, which had never been written down.
