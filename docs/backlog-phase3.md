# Phase-3 backlog

Analytics this project deliberately did **not** build. Everything here is a
specification, not an implementation: what the thing is, what it needs beyond the
current schema, roughly how it would be approached, what could make it fail, and
a rough effort estimate.

Effort is in focused working sessions of the kind the rebuild was executed in
(one milestone each), assuming the current pipeline as the starting point.

Current state to build on:

- `data/canonical/{competitions,athletes,results,bouts}.parquet` — 3,098
  competitions, 552,612 bouts, 2002–2026, **bout-level detail from 2015 onward
  only** (41.8% of competitions; ~100% of seasons since 2016).
- A bout row is a final score: `phase`, `round`, `poule_no`, `bout_order`,
  `athlete_a/b`, `score_a/b`, `winner`, `status`. **There is no touch-by-touch
  sequence and no clock anywhere in the dataset** — this is the single constraint
  that shapes most of this document.
- Derived: `stats_fencer_comp` (23 metrics, `src/ffs/metrics.py`),
  `ratings_history` (Elo, `src/ffs/elo.py`), `h2h` / `h2h_bouts`.

---

## 1. Win probability

**What it is.** Given a bout state, the probability each fencer wins it. Two
distinct products hide under one name:

- **Pre-bout**: "Kano beats Borel 61% of the time in a DE bout." Usable for
  previews, seeding analysis, upset detection, and as the baseline any live model
  needs anyway.
- **In-bout / live**: "10–8 in the third period with 40 seconds left → 78%."
  This is the broadcast-overlay product, and the one people mean when they ask
  for win probability.

**What the data supports today.**

Pre-bout is fully supported. The Elo model already produces
`P(A) = 1 / (1 + 10^((R_B − R_A)/400))`, which is a calibrated-ish win
probability sitting unused as a *display* quantity. Turning it into a product is
mostly calibration and presentation work: bin historical bouts by predicted
probability, plot observed win rate against it, and correct the curve (isotonic
regression or a logistic recalibration) so that the number shown is honest.
Adding features beyond rating difference — weapon, phase (poules are to 5, DE to
15, and are *not* the same prediction problem), head-to-head history, days since
last competition, home-country advantage — turns it into a small logistic
regression or gradient-boosted model, trained per weapon, with the Elo difference
as the dominant feature.

In-bout is **not supported**. A bout in this dataset is one final score. There is
no touch sequence, no period boundary, no clock. The state space of a live model
(`score_a, score_b, time_remaining, period, priority`) cannot be observed at all.

**What is needed beyond the current schema.**

| Need | For | Source |
|---|---|---|
| Touch-by-touch sequence per bout | in-bout model | FIE scoring machines / DT software; not published |
| Timestamps per touch (or at least period) | in-bout model | same |
| Card and priority events | in-bout model, edge cases | same |
| Nothing new | pre-bout model | already have it |

**Approach.**

1. *Pre-bout, offline.* Split by season (train ≤2023, test 2024–2026 — never a
   random split, which leaks a fencer's future into their past). Baseline: raw
   Elo expectation. Model: logistic regression on
   `[Δrating, weapon, phase, Δrecent-form, h2h prior, Δage]`. Report Brier score
   and a reliability diagram, not accuracy — a model that says 61% must be right
   61% of the time.
2. *Pre-bout, on the site.* A number on the H2H page and on each DE bout card,
   always with its calibration stated.
3. *In-bout.* Blocked. If a touch-level feed ever arrives, the standard approach
   is a state-transition model: estimate `P(next touch to A)` from the two
   fencers' rates, then either solve the resulting Markov chain exactly (a bout
   to 15 with a clock is small enough to solve by dynamic programming) or
   simulate. Fitting the per-touch rate is the modelling work; the chain is
   bookkeeping.

**Risks.** Calibration on poule bouts is harder than it looks — a poule bout to 5
is high-variance and the favourite wins less often than a DE bout at the same
rating gap; they must be modelled separately or the combined model will be
mis-calibrated on both. Ratings from a cold start (2015) mean early-era
predictions carry systematically inflated uncertainty.

**Effort.** Pre-bout: 1–2 sessions including calibration and the site
surfaces. In-bout: 2–3 sessions *after* a touch-level feed exists, and 0 without
it.

---

## 2. Momentum and comeback metrics

**What it is.** The vocabulary commentary already uses, made measurable: who
scores in runs, who stops the run, who wins from behind, who closes out a lead,
who tightens up at 14–14.

**What the data supports today.** Much less than the name suggests, and the
distinction matters:

*Supported from final scores alone:*

- **Comeback outcomes at the bout level, coarse.** In DE, a 15–14 win is a
  different event from a 15–5 win; the distribution of a fencer's winning and
  losing margins is a real signal that the current per-bout means and standard
  deviations (`TTD`, `TTR`, `table_td_std`) only partly capture.
- **One-touch bouts.** Rate of 15–14 / 5–4 results, won and lost, per fencer —
  a clean, cheap "close-bout record" nobody publishes.
- **Poule-level momentum.** A poule *is* a sequence — six bouts in a
  reconstructed order. `PM1V%` and `PM1&2V%` already exploit this. It extends to:
  performance after a loss vs after a win, best and worst runs within a poule,
  and recovery rate (share of poules where the fencer loses bout 1 and still
  qualifies).
- **Competition-level momentum.** Round-by-round scoring trend through a
  tableau: does this fencer's touch differential improve as the opposition gets
  harder?
- **Season momentum.** Rating slope over a rolling window, results in a
  competition following a bad one — form, honestly labelled.

*Not supported:*

- **True in-bout momentum** — runs of consecutive touches, "scored 5 in a row",
  the 14–14 record — requires the touch sequence. Every claim of the form "wins
  the last three touches" is unavailable and must not be faked from margins.

**What is needed beyond the current schema.** Touch sequence, again, for the
in-bout half. The poule/competition/season half needs nothing new — only
`bout_order` (already parsed) and the existing bout table.

**Approach.** A `momentum.py` alongside `stats.py`, emitting per (competition,
athlete) and per (athlete, season): close-bout record, poule recovery rate,
after-loss performance delta, round-by-round differential trend, margin
distribution. Present as a profile card and as new columns in the metrics
explorer — the registry (`src/ffs/metrics.py`) is designed for exactly this kind
of extension, and adding a `Metric` record propagates it to the explorer, the
compare view, the trajectories series list and the methodology glossary at once.

**Risks.** Sample size. "Performance after a loss" over 12 poules is noise; every
one of these needs a minimum-sample gate and a visible `n`, like the cohort
curves already have. The label "momentum" also invites a causal reading the data
cannot support — these are descriptive splits, and should be worded as such.

**Effort.** 1–2 sessions for the supported half, including site surfaces.

---

## 3. Style profiles

**What it is.** Turning numbers into recognisable descriptions: the fencer who
wins narrow bouts on defence, the fencer with a wide scoring spread who blows
opponents out or falls apart, the poule specialist who fades in the tableau. A
preview that says *what kind of fencer* someone is about to meet.

**What the data supports today.** Enough to be interesting, entirely from
existing metrics. The current 23 already span the right axes:

- **Scoring rate** — `PMTD`, `TTD`.
- **Defensive rate** — `PMTR`, `TTR`.
- **Consistency** — `p_td_std`, `p_tr_std`, `table_td_std`, `table_tr_std`. This
  is the interesting one, and no public source shows it.
- **Phase asymmetry** — poule performance versus DE performance for the same
  fencer, which cleanly separates "qualifies comfortably then loses early" from
  "scrapes out of the poule then goes on a run".
- **Margin profile** — from §2, once built.

**What is needed beyond the current schema.** Nothing for a first version.
Genuine *tactical* style (attack vs counter-attack, preparation length, blade
work, distance) needs touch-level or video data and is out of reach — the honest
framing is "statistical profile", never "tactical style".

**Approach.**

1. Build a per-fencer feature vector from career metrics, restricted to fencers
   with enough competitions to be stable (the explorer's existing min-comps gate
   is the right instrument), standardised within (weapon, gender) so a sabreur is
   not compared against an épéeist.
2. Reduce and cluster — PCA for the axes, k-means or Gaussian mixture for the
   groups, `k` chosen by silhouette and, more importantly, by whether the
   clusters are *nameable*. A cluster nobody can describe in a sentence is a
   failed cluster.
3. Name each cluster from its centroid, by hand, once.
4. Surface as a profile badge, a similar-fencers list ("statistically closest to:
   …"), and a radar or parallel-coordinates view on the compare page. Similarity
   search is arguably the better product and needs no clustering at all — just a
   distance in the standardised feature space.

**Risks.** Clusters that track *level* rather than *style* — the first principal
component of any of this will be "how good is the fencer", which is not a style.
Residualising the features against rating before clustering is the standard fix
and should be treated as mandatory. Second risk: labels are sticky and read as
judgements, so the naming has to be descriptive ("high-variance scorer"), never
pejorative.

**Effort.** 2 sessions, of which most is the honesty work — gates, residualising,
naming, and the explanatory copy.

---

## 4. Fantasy and prediction games

**What it is.** The engagement layer: a scoring system over real competition
results that people play between competitions. Two forms, in increasing order of
cost:

- **Head-to-head pick'em.** Pick the winner of each DE bout in a live
  competition; score against the results. Trivially explainable, and the pre-bout
  model in §1 supplies both a baseline opponent and a difficulty weighting
  (correctly picking an upset should be worth more).
- **Fantasy roster.** Pick a squad under a budget before a competition; score
  from actual results — placing, bouts won, touch differential, upsets — with
  prices set from ratings.

**What the data supports today.** The scoring engine, entirely. Every quantity a
fantasy system would score is already computed per (competition, fencer): final
place, bouts won, touch differential, whether they beat someone rated far above
them. Pricing from rating is a one-liner given `ratings_history`. A **historical
backtest** — "what would this scoring system have paid out across 2016–2026?" —
runs today, offline, and is the right first step: it tunes the scoring so that
skill beats luck before anyone plays it. The minigame at `#/play` already
demonstrates the tuning discipline this needs (scripted policies, medians over
many seeded runs, a required ordering of outcomes).

**What is needed beyond the current schema — and it is not data:**

| Need | Why | Note |
|---|---|---|
| User accounts and persistence | picks must be stored before the competition | **breaks the static architecture** |
| A backend or BaaS | to hold entries and prevent late edits | first server-side component in the project |
| Near-live results | scoring within hours, not on the next scrape | `ffs update` currently runs on demand |
| A competition calendar with lock times | to close entry before the first bout | derivable from fie.org's upcoming-events data |
| Moderation / terms | any user-generated content | |

This is the only item in this backlog that changes the shape of the project. The
site is deliberately a directory of static files; fantasy needs writes. A
serverless function plus a hosted database is the minimum, and the honest
accounting is that this is a small product with ongoing operational cost, not a
weekend feature.

**Approach.**

1. *Offline backtest first.* Implement scoring in `src/ffs/`, replay 2016–2026,
   check that consistent skill outperforms random picks by a clear margin and
   that no single competition dominates a season's scoring.
2. *Single-player, no backend.* Pick'em against a past competition, stored in
   `localStorage`, scored client-side — validates the mechanic and the difficulty
   weighting with zero infrastructure. This is the recommended next step.
3. *Multiplayer.* Only then, and only with a backend and a plan for who operates
   it.

**Risks.** Prediction contests over athlete performance edge toward betting
adjacency; a federation-affiliated version would need care, no stakes, and
probably legal review. Near-live scoring depends on how quickly fie.org's own
archive publishes brackets, which — per `docs/updating.md` — is not instant and
occasionally serves stale listings.

**Effort.** Backtest 1 session; single-player pick'em 1–2 sessions; anything
multiplayer is a separate project with an operations story.

---

## 5. Rating-model improvements

Deferred from v1 (`src/ffs/elo.py`) and referenced from `docs/methodology.md`.
Each is small in isolation; the reason they were deferred is that each needs its
own validation, and v1's job was to be simple and checkable.

- **Margin of victory.** A 15–3 and a 15–14 currently move ratings identically.
  Standard fix is a multiplier on `K` from the touch margin, damped so blowouts
  do not run away. Needs a held-out predictive check to prove it helps —
  MoV weighting is not automatically an improvement.
- **Time decay / inactivity.** A fencer absent for two seasons keeps their rating
  intact. Options: regress toward the pool mean per idle period, or inflate `K`
  on return. The latter is gentler and less likely to distort trajectories.
- **True chronology within a competition.** Bouts within an identical (phase,
  round) group are currently ordered deterministically rather than
  chronologically, because fie.org publishes no bout times. Ordering within a
  round has a second-order effect on ratings; a real feed would remove the
  approximation.
- **Rating uncertainty.** Elo carries no variance, so a fencer with 8 bouts is
  shown with the same authority as one with 400 (the provisional-`K` doubling
  helps convergence but publishes no interval). Glicko-2 or a TrueSkill-style
  model would give an interval to display, at the cost of a less explainable
  model — a real trade-off for a public site, not an obvious upgrade.
- **Cross-weapon and cross-era comparability.** Ratings are per (weapon, gender)
  pool by construction and are not comparable across pools; rating inflation over
  time within a pool has not been measured. Worth measuring before any all-time
  cross-era claim is ever made on the site.

**Effort.** 1 session each, plus a shared validation harness — a
predict-the-next-season backtest — which should be built first and is the real
prerequisite for all five.

---

## 6. Smaller items

Recorded so they are not lost, none of them phase-3-sized:

- **Team events.** Structurally similar, not scraped. Would need a relay-bout
  parser and a separate rating pool.
- **Junior / cadet / veteran categories.** The discovery layer already filters by
  category; only senior individual is scraped. Junior data would materially
  improve the trajectories page, which currently sees careers only from the point
  they reach senior international level.
- **Referee data.** fie.org publishes referee assignments for some competitions.
  Card and referee analysis is possible in principle and is politically fraught
  in practice.
- **Nation-level views.** Depth, development rate and medal share per country —
  computable today from existing tables, and probably the highest
  value-per-effort item on this entire page.
- **Age at first international result / career length.** Straightforward
  descriptive work off the existing schema, complementing the trajectories page.
- **Data-quality dashboard.** The archive's holes (missing poule bouts, the ~0.7%
  parity residual documented in `docs/methodology.md`) are currently described in
  prose. A page that shows *where* the archive is thin would be honest and would
  double as a bug-finding tool.
