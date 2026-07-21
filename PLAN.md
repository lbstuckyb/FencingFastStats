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

**`stats.py`** — one row per (competition_id, athlete_id) from bout-level data (explode bouts to fencer perspective, two groupbys). Port every metric from `data/update_data.py:26-98`: POS, Q, PEXMPT, PVICT, PIND, PTR, PTD, PT-DIFF, PMTR, PMTD, PMT-DIFF (+stds), TTR, TTD, TMT-DIFF, TMVAVG (null if Q=0), PM1V%, PM1&2V%, T64+, T96+. Note legacy inconsistency (`p_tr_mean = tr_poules/p_matches` vs `p_td_mean` = row-mean) — replicate intent, document deviations in methodology.md. Plus career aggregates per athlete×weapon for site profiles.

**`h2h.py`** — group bouts by unordered pair within (weapon, gender) → `h2h.parquet` (bouts, wins, td, poule/de split, last_met) + `h2h_bouts.parquet` (per-pair bout list for the site).

**`elo.py`** — per (weapon, gender) pool, start 1500, **K=16 poule / K=32 DE**, provisional 2×K for first 30 bouts, no decay/MoV in v1 (→ backlog). Order: competitions by start_date, within comp poules then DE 256→2. Emit `ratings_history.parquet`: (athlete, competition, pre, post). ~30-line loop with defaultdicts (sketch in plan discussion; straightforward).

## Site data artifacts (`build_site.py` → `site/data/`)

Small eager bundle + lazy shards via relative `fetch()` (GitHub Pages-safe):
- `meta.json` (~2 KB); `fencers/index.json` (search index, ≤~1 MB); `summary/{me,mf,we,wf,se,sf}.json` (ELO top-200, leaderboards, comp list); `fencers/{id%100}/{id}.json` (career, per-comp stats, rating timeline, h2h aggregates); `h2h/{lo}-{hi}.json` **only for pairs ≥5 bouts**; `competitions/index.json` + `competitions/{id}.json` (full results, poules, bracket).
- Size guardrails: warn on eager files >1.5 MB; prune per-fencer shards to athletes with ≥2 comps; measured decision at Milestone 5 whether to commit `site/data/` or generate in CI.

## Static site pages (`site/`)

Home (pool selector, ELO top-20, recent comps, leaderboards) · Fencer search (client-side over index.json) · Fencer profile (**rating timeline chart**, career table, per-comp results, H2H list) · H2H explorer (two fencers → aggregate card + bout list) · Competition browser + detail (results, poule grids, DE bracket) · Methodology (metric + ELO definitions, data attribution). Deploy via `.github/workflows/pages.yml` (`upload-pages-artifact` on `site/`).

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
- [ ] M4 — Stats + ELO + H2H
- [ ] M5 — Site data + core pages
- [ ] M6 — Remaining pages + deploy
- [ ] M7 — Proposal + backlog docs
