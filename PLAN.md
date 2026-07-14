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
- [ ] M2 — One competition end-to-end
- [ ] M3a — Discovery + shape survey
- [ ] M3b — Bulk historical scrape
- [ ] M4 — Stats + ELO + H2H
- [ ] M5 — Site data + core pages
- [ ] M6 — Remaining pages + deploy
- [ ] M7 — Proposal + backlog docs
