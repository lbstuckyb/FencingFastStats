# Methodology

How FencingFastStats' metrics, ratings, and head-to-head records are computed
from fie.org's public data, how they were validated against the legacy
Excel-derived dataset (`data/legacy/updated_results.csv`), and where the two
sources genuinely disagree. This consolidates the docstrings at the top of
`src/ffs/stats.py`, `src/ffs/elo.py`, and `src/ffs/h2h.py` — those are the
authoritative source if this doc and the code ever drift.

## Data model

Four canonical tables per competition (`src/ffs/schema.py`), joined by
`competition_id` (`"{season}-{comp_id}"`):

- `competitions` — one row per competition (name, dates, weapon, gender, category, entry count).
- `athletes` — one row per athlete, deduplicated across competitions.
- `results` — one row per (competition, athlete): final ranking and points.
- `bouts` — one row per individual bout, `phase` in `{'poule', 'de'}`.

`bouts.status` is `'ok'` (a genuine fenced result), `'forfeit'` (withdrawal/
injury, or a poule no-show — see below; winner is still recorded where
known), or `'bye'` (no opponent). **Only `status == 'ok'` bouts feed any
numeric stat or rating** — this mirrors legacy's ad-hoc "D with tr=0"
no-show filter, applied more systematically here.

`bouts.round`/`poule_no`/`bout_order`: for `phase='poule'`, `poule_no` is the
1-indexed pool number and `bout_order` is the *opponent's* 1-indexed seed
position within the pool (used to reconstruct seed order for `PM1V%`/
`PM1&2V%`, see below). For `phase='de'`, `round` is FIE's own tableau round
code (`'A256'`, `'B64'`, ..., `'B2'` for the final) and `bout_order` is the
0-indexed bracket-slot position within that round — a reproducibility aid,
not a legacy-parity field. Neither is literally specified by any FIE API
contract; it's a documented interpretation, consistent across the 215- and
125-entry fixtures this was verified against.

## Stats engine (`src/ffs/stats.py`)

One row per (competition, athlete), reproducing every metric in the legacy
CSV (`POS, PVICT, PTR, PTD, PIND, PT-DIFF, PMTR, PMTD, PMT-DIFF, p_tr_std,
p_td_std, TTR, TTD, TMT-DIFF, table_tr_std, table_td_std, TMVAVG, PM1V%,
PM1&2V%, Q, PEXMPT, T64+, TPRE64`) computed from bout-level data instead of
legacy's wide hand-scraped Excel columns.

Poule-derived metrics are `NaN` for an entire competition when fie.org's own
archive has zero poule bout data for it (pre-~2016 "results-only"
competitions — see the M3a progress notes in `PLAN.md`); the same applies to
DE-derived metrics vs zero DE bout data. Within a competition that does have
data, an athlete with zero personal bouts in that phase also gets `NaN`
there (`PEXMPT=1` marks "no poule bouts", see below).

### Legacy deviations

- **`PIND` is a win ratio, not a touch differential.** Despite the name
  suggesting FIE's usual bout "Indicator" (touches scored minus received),
  its legacy values — verified against the raw CSV's `poule_ind` column,
  itself sourced from FIE's own historical Excel export — are exactly
  `PVICT / (poule matches played)` (e.g. 5 wins out of 6 matches → 0.833).
  Reproduced here the same way. `PT-DIFF` is the genuinely different
  touches-scored-minus-received quantity, computed separately, and isn't in
  the mandatory parity list. A ~0.15%-of-rows legacy sentinel value of
  `1000.0` was observed in the raw CSV and is presumed a raw-export
  artifact — not reproducible from bout data, not chased further.
- **Poule no-show bouts (0-0, `status='forfeit'`).** A fenced bout can never
  legitimately end 0-0. fie.org's archive still records these no-show
  defaults with a normal `v`/winner flag, which the parser originally
  (incorrectly) classified as `status='ok'`, contaminating every poule
  numeric stat for both sides. Legacy's pipeline explicitly excluded these
  rows (its "D with tr=0" filter) — `src/ffs/parse.py` now does the same,
  tagging any poule match with `score_a == 0 and score_b == 0` as
  `'forfeit'` (keeping the recorded winner, consistent with how DE-phase
  forfeits already carry a winner). This was applied retroactively to the
  already-scraped `data/canonical/bouts.parquet` (4,422 poule rows
  reclassified `ok → forfeit`) rather than re-running the full historical
  scrape; a fresh `ffs scrape-all` run would produce the same result
  directly from the fixed parser.
- **`Q` (qualified into the tableau) is `0`, not `NaN`, for non-qualifiers.**
  An athlete who competed in a DE-having competition but never appears in
  any DE bout (eliminated in poules, or otherwise never reached the
  tableau) gets an explicit `Q=0` / `T64+=0` / `TPRE64=0` row, matching
  legacy's explicit-zero semantics, rather than being silently dropped and
  turning into `NaN` after the left-merge in `compute_stats`.
- **`PEXMPT`** ("exempt from poules") is derived directly from bout
  presence — any athlete with a result in a poule-having competition but
  zero recorded poule bouts — rather than from fie.org's own pool-results
  summary `results.exempt` flag. That flag was found to disagree with
  bout-level ground truth for at least one real athlete: 2025-242's
  champion, KANO Koki (athlete 34385), has a placeholder row in fie.org's
  pool-results summary (`td=tr=0`, `qualified=False`) despite never
  appearing in any pool's actual fencer list — a real archive quirk, not a
  parser bug.
- **`PMTR`/`PMTD`** are plain per-bout means. Legacy's own inconsistency
  between `tr_poules/p_matches` and a row-mean was itself an artifact of
  asymmetric no-show filtering, which the `status` filter above already
  resolves.
- **`T64+`/`TPRE64`** check the literal FIE tableau round codes `'B64'`
  (round of 64) and `'A64'` (the preliminary round feeding into it) — stable regardless
  of a competition's bracket size, verified against both fixtures. A long
  tail of older/odd competitions uses other round-code conventions
  (`'F64'`, `'PD1'`, plain digits, ...) that these flags don't recognize —
  a known, accepted gap, not in the mandatory parity list.
  `TPRE64` is legacy's `T96+` renamed: "table of 96" is not FIE
  terminology, and what the flag actually measures is entries into the
  preliminary tableau. `T64+` keeps its name — that one is the real
  table of 64. The rename touches no parity metric.
- **`PM1V%`/`PM1&2V%`** ("won pool match 1" / "matches 1 and 2") approximate
  legacy's match-number columns, which were themselves derived from a fixed
  historical FIE pool pairing schedule (hardcoded per seed-count in the
  legacy parser). Here they're redefined as "beat the pool opponent with
  the lowest / two lowest seed numbers", with seed reconstructed from
  `bouts.bout_order` (see `stats._pool_seeds`) — a reasonable, deterministic
  proxy, not a verified bit-exact port. Excluded from the mandatory parity
  list.

### Metric registry (`src/ffs/metrics.py`)

Each metric's human-readable label, column group, aggregation (`mean`/`sum`),
better-direction, display format, and one-line definition live in one
`Metric` record. The registry is serialized into `site/data/meta.json`, so
the site's methodology glossary, the metrics explorer's column headers and
its sort directions are all generated from it — a metric cannot be described
on the site differently from how it is computed here.

`Metric.den` names the *population* a mean is taken over. Metrics have
genuinely different denominators (a fencer's 40 results may hold 40 `POS`
values but only 12 `PVICT` and 9 `TTR`, because pre-~2016 competitions carry
no bout data), so any re-aggregation — the explorer's, and every per-season
or career total on the site — divides each metric's sum by the count of
competitions that actually carry it, never by the number of competitions
entered.

## Elo ratings (`src/ffs/elo.py`)

**These ratings are not an FIE ranking.** The FIE's official ranking points
are not in this dataset and were never scraped; there is no public archive
of historical rankings to derive them from. The legacy app did display an
official ranking, read from a separately maintained spreadsheet
(`data/legacy/`), and that column has no equivalent here. Everything this
site calls a "rating" is the Elo score below, computed from bout results
alone, and every view that shows one says so.

Standard Elo per (weapon, gender) pool, with full history:
`R' = R + K * (actual - expected)`, `expected = 1 / (1 + 10**((Ropp - R) / 400))`.

- Start rating: **1500**.
- `K = 16` for poule bouts, `K = 32` for DE bouts.
- **Provisional doubling**: each side's `K` is doubled while they're within
  their first 30 rated bouts *in that (weapon, gender) pool*, tracked
  independently per side — one player being provisional doesn't change the
  other's `K`.
- No margin-of-victory or time decay in v1 (see `docs/backlog-phase3.md`).
- Only `status == 'ok'` bouts are rated.
- **Processing order**: competitions by `start_date` ascending; within a
  competition, poule bouts before DE bouts; DE rounds from largest bracket
  to smallest. Within an identical (phase, round) group there's no real
  chronology available from fie.org's archive, so bouts are ordered
  deterministically (`poule_no`, `bout_order`, `athlete_a`) rather than
  truly chronologically — a documented simplification.
- `ratings_history` is **one row per (athlete, competition)**: the rating
  immediately before the athlete's first rated bout of that competition
  (`pre`) and immediately after their last (`post`) — not one row per bout.

**Sanity check**: the top-10 rated fencers per (weapon, gender) pool over
the full 2002–2026 dataset surface unambiguously correct world-class names
— OH Sanguk, SZILAGYI Aron, GRACHEVA Inna, MASSIALAS Alexander, BOREL
Yannick, KANO Koki, KHARLAN Olga, VOLPI Alice, among others.

## Head-to-head (`src/ffs/h2h.py`)

Pairs are normalized to `(athlete_lo, athlete_hi)` = sorted athlete ids, so
each pair has a single canonical key regardless of who's listed first in
the underlying bout row.

- `h2h_bouts`: one row per real encounter, `status` in `{'ok', 'forfeit'}`
  (byes have no real opponent and are excluded entirely).
- `h2h`: one row per `(athlete_lo, athlete_hi, weapon, gender)` with bout/
  win counts and `last_met`. Touch sums (`td_lo`/`td_hi`) are computed only
  over `status == 'ok'` bouts, since forfeits carry no real score.

## Career trajectories (`build_site.build_paths`)

`site/data/paths/{weapon}{gender}.json` holds, per cohort tier and per series,
the by-age distribution across the cohort: `{age: [n, mean, p25, p50, p75]}`
over ages 12–45. The trajectories page draws the median as a line and p25–p75
as a band; legacy's `rank-graph` drew a bare mean, which cannot show how wide
the path is.

- **A cohort is defined by peak FencingFastStats rating**, not by any FIE
  ranking: `top10` is every profiled fencer whose peak rating ever placed them
  in the top 10 of their (weapon, gender) pool. The FIE's own points are not in
  this dataset, so there is no official ranking available to build a cohort
  from — every label must say whose measure it is.
- **Age** is the competition's calendar year minus the athlete's birth year
  (`_rating_by_age` uses the same definition), so an "age" is a calendar year of
  results rather than a season.
- **One value per (athlete, age)** enters the distribution: mean-aggregated
  metrics are averaged over that year's competitions and summed metrics totalled,
  and only then is the distribution taken across the cohort. A fencer with twenty
  entries that year weighs the same as one with three.
- Ages with fewer than `MIN_COHORT_AGE_SAMPLE` (3) fencers are omitted rather
  than published as the spike of a single career.
- Beyond the metric registry the file carries `PATH_EXTRA_SERIES`: the rating
  itself (the last rating carried away from a competition that year), the number
  of competitions entered, and the share of entries reaching the table of 64,
  the preliminary table, the podium and the title.
- `cohort_ids` lists each tier's members so the page can mark an overlaid fencer
  who is himself part of the curve he is being compared against.

## Validation against legacy data

`ffs validate` (`src/ffs/validate_legacy.py`) runs two checks:

1. **Competition matching**: legacy competitions matched to canonical ones
   by `(weapon, gender, start_date ± 1 day)`. Gate: ≥95% matched.
2. **Fencer-level parity**: within matched competitions, fencers matched by
   normalized name + country, then `POS/PVICT/PTD/PTR/PIND/Q/TMVAVG`
   compared with float tolerance (`atol=0.01`; both-`NaN` counts as
   agreement, e.g. `TMVAVG` null on both sides when `Q=0`). Gate: ≥99%
   overall agreement across ≥3 competitions.

**Current numbers** (286/286 legacy competitions matched, 100%; 45,848
matched fencer-rows across 279 competitions):

| Metric  | Agreement |
|---------|-----------|
| POS     | 100.0%    |
| PVICT   | 99.1%     |
| PTD     | 98.8%     |
| PTR     | 98.9%     |
| PIND    | 98.7%     |
| Q       | 99.9%     |
| TMVAVG  | 99.8%     |
| **overall** | **99.3%** |

`PTD`/`PTR`/`PVICT` sit just under 99% individually. Investigated and traced
to **genuine fie.org archive gaps** — specific competitions/pools where
fie.org's own archive is missing some poule bouts entirely (e.g. `2020-385`
pool 29: athlete 28816 has bouts recorded at `bout_order` 1, 2, 4, 5, but 3
is simply missing — a real hole in fie.org's data, not a parser bug; the
same phenomenon affects `PEXMPT` for `2025-242`'s champion, documented
above). This was an anticipated risk (`PLAN.md`: "legacy may have real bout
data our scrape doesn't"). Since the combined overall rate (99.3%) clears
the mandatory ≥99% gate, it's accepted as an archive-era limitation rather
than chased further.

## Data source posture

`fie.org/robots.txt` is wide open (`Disallow:` empty), and explicitly covers
`/api/` — nothing on the site is disallowed for crawling. The scraper
(`src/ffs/fie_client.py`) throttles requests (≥1.5s between fetches) and
caches every response to disk regardless, so the site is not re-hit for
data already collected. No official FIE API exists; the SSR-embedded JSON
payload (and one undocumented-but-public REST endpoint for paginated
results, discovered via the site's own JS bundle) is the only way to get
structured competition data from fie.org today. This is public, unauthenticated
data throttled and cached responsibly — see `docs/proposal.md`'s legal/data
posture section (M7) for the fuller pitch to FIE, including an offer to
switch to an official feed if one becomes available.
