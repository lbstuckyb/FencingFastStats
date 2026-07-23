"""Per-(competition, athlete) stats engine — ports every metric from the
legacy `data/update_data.py:26-98` pipeline, computed here from bout-level
data (`bouts` table) instead of legacy's wide hand-scraped Excel columns.

Column names intentionally match the legacy CSV (`data/legacy/updated_results.csv`)
so `validate_legacy.py` can diff them directly: POS, Q, PEXMPT, PVICT, PTR,
PTD, PIND, PT-DIFF, PMTR, PMTD, PMT-DIFF, p_tr_std, p_td_std, TTR, TTD,
TMT-DIFF, table_tr_std, table_td_std, TMVAVG, PM1V%, PM1&2V%, T64+, TPRE64.

Deviations from legacy (see `docs/methodology.md` for the full writeup):

- `TPRE64` is legacy's `T96+` renamed: "table of 96" is not FIE terminology,
  and the quantity it actually measures is entries into the *preliminary*
  tableau feeding the table of 64 (fie.org round code `'A64'`). None of the
  parity metrics are affected -- `T96+` was never in `PARITY_METRICS`.

- Only `status == 'ok'` bouts feed every numeric metric (byes/forfeits have
  no real score) -- this is a cleaner version of legacy's ad-hoc "D with
  tr=0" no-show filter, already applied once at parse time (see schema.py).
- PIND is NOT touches-scored-minus-received despite the name suggesting FIE's
  usual bout "Indicator" -- empirically verified against the legacy CSV
  (`poule_ind` in `legacy/data/update_data.py`, sourced straight from FIE's
  own historical Excel export, not derived by the legacy pipeline itself):
  its values are exactly `PVICT / (poule matches played)`, a win ratio in
  [0, 1] (e.g. 5 wins out of 6 matches -> 0.833). Reproduced here as
  `PVICT / n_poule_matches`. (A ~0.15%-of-rows legacy sentinel value of
  `1000.0` was observed and is presumed a raw-export artifact, not
  reproducible from bout data -- not chased further.) PT-DIFF is the
  genuinely different touches-scored-minus-received quantity and is computed
  separately; it isn't in the mandatory parity metric list.
- PMTR/PMTD are both simple per-bout means (legacy's inconsistency between
  `tr_poules/p_matches` and a row-mean was itself caused by asymmetric
  no-show filtering that our upstream `status` filter already resolves).
- Poule-derived metrics are NaN for an entire competition if fie.org's
  archive has zero poule bout data for it (pre-~2016 "results-only"
  competitions, see M3a); ditto DE-derived metrics vs zero DE bout data.
  Within a competition that *does* have poule/DE data, an athlete with zero
  personal bouts in that phase gets NaN there too (PEXMPT=1 marks this "no
  poule bouts" case, derived directly from bout presence rather than
  fie.org's own pool-results-listing `results.exempt` flag -- that flag was
  found to disagree with bout-level ground truth for at least one real
  athlete, e.g. 2025-242's champion KANO Koki, id 34385: fie.org's
  pool-results summary lists a placeholder row for them (td=tr=0,
  qualified=False) despite them never appearing in any pool's actual
  fencer list -- a real archive quirk, not a parser bug).
- T64+ / TPRE64 check literal FIE tableau round codes `'B64'` (round of 64)
  and `'A64'` (the preliminary round feeding into it) -- stable labels
  fie.org uses regardless of a competition's total bracket size (verified
  against 215- and 125-entry fixtures). A long tail of older/odd
  competitions uses other round-code conventions (`'F64'`, `'PD1'`, plain
  digits, ...) that these two flags don't recognize -- a known gap, not in
  the mandatory parity metric list.
- PM1V% / PM1&2V% ("won pool match 1 / matches 1 and 2") approximate
  legacy's match-number columns, which were themselves derived from a fixed
  historical FIE pool pairing schedule (hardcoded per seed-count in
  `legacy/data/main.py`), not literally "ascending seed order". Here they're
  redefined as "beat the pool opponent with the lowest / two lowest seed
  numbers" (seed reconstructed from `bouts.bout_order`, see `_pool_seeds`)
  -- a reasonable, deterministic proxy, not a verified bit-exact port. Also
  excluded from the mandatory parity metric list.
"""
from __future__ import annotations

import pandas as pd

POULE_COLS = [
    "PVICT", "PTR", "PTD", "PIND", "PT-DIFF", "PMTR", "PMTD", "PMT-DIFF",
    "p_tr_std", "p_td_std", "PEXMPT", "PM1V%", "PM1&2V%",
]
DE_COLS = ["Q", "TTR", "TTD", "TMT-DIFF", "table_tr_std", "table_td_std", "TMVAVG", "T64+", "TPRE64"]


def _explode(bouts: pd.DataFrame) -> pd.DataFrame:
    """One row per (bout, perspective): athlete_id/opponent_id/td/tr/win."""
    a = bouts.rename(columns={
        "athlete_a": "athlete_id", "athlete_b": "opponent_id",
        "score_a": "td", "score_b": "tr",
    }).copy()
    a["win"] = (a["winner"] == a["athlete_id"]).astype("Int64")
    b = bouts.rename(columns={
        "athlete_b": "athlete_id", "athlete_a": "opponent_id",
        "score_b": "td", "score_a": "tr",
    }).copy()
    b["win"] = (b["winner"] == b["athlete_id"]).astype("Int64")
    cols = ["competition_id", "phase", "round", "poule_no", "bout_order", "athlete_id", "opponent_id", "td", "tr", "win"]
    return pd.concat([a[cols], b[cols]], ignore_index=True)


def _pool_seeds(pool_bouts: pd.DataFrame) -> pd.Series:
    """Reconstruct each athlete's own seed rank within their pool: `bout_order`
    is defined (in `schema.py`/`parse.py`) as `seed_position[athlete_b]`, a
    fixed property of whichever fencer is athlete_b in that row -- so taking
    it from any row where an athlete appears as athlete_b recovers their own
    seed. Returns a Series indexed by (competition_id, athlete_id) -> seed.
    """
    seeds = pool_bouts.groupby(["competition_id", "athlete_b"])["bout_order"].first()
    seeds.index.set_names(["competition_id", "athlete_id"], inplace=True)
    return seeds


def _poule_stats(bouts: pd.DataFrame, results: pd.DataFrame) -> pd.DataFrame:
    poule = bouts[bouts["phase"] == "poule"]
    comps_with_data = set(poule["competition_id"].unique())
    ok = poule[poule["status"] == "ok"]

    seeds = _pool_seeds(poule)
    exploded = _explode(ok)

    grp = exploded.groupby(["competition_id", "athlete_id"])
    agg = grp.agg(
        PVICT=("win", "sum"),
        PTR=("tr", "sum"),
        PTD=("td", "sum"),
        p_tr_std=("tr", "std"),
        p_td_std=("td", "std"),
        PMTR=("tr", "mean"),
        PMTD=("td", "mean"),
        _n_matches=("win", "size"),
    ).reset_index()
    agg["PIND"] = agg["PVICT"] / agg["_n_matches"]
    agg["PT-DIFF"] = agg["PTD"] - agg["PTR"]
    agg["PMT-DIFF"] = agg["PMTD"] - agg["PMTR"]
    agg = agg.drop(columns=["_n_matches"])

    # PM1V% / PM1&2V%: seed-order proxy (see module docstring). `bout_order`
    # is the opponent's seed directly from athlete_a's perspective; from
    # athlete_b's perspective it's actually athlete_id's OWN seed, so look
    # the true opponent seed up via the reconstructed `seeds` table instead.
    opponent_seed = exploded.set_index(["competition_id", "opponent_id"]).index.map(seeds)
    exploded["opponent_seed"] = pd.Series(opponent_seed, index=exploded.index)
    # Fallback for the one pool member per pool who's never athlete_b (the
    # globally-lowest athlete_id in that pool, so `seeds` has no entry for
    # them): bout_order itself, exact only from athlete_a's perspective but
    # the best available proxy for the rare miss.
    exploded["opponent_seed"] = exploded["opponent_seed"].fillna(exploded["bout_order"])
    ordered = exploded.sort_values(["competition_id", "athlete_id", "opponent_seed"])
    ranked = ordered.groupby(["competition_id", "athlete_id"]).head(2).copy()
    ranked["rk"] = ranked.groupby(["competition_id", "athlete_id"]).cumcount() + 1
    pm1 = ranked[ranked["rk"] == 1][["competition_id", "athlete_id", "win"]].rename(columns={"win": "PM1V%"})
    pm2 = ranked[ranked["rk"] == 2][["competition_id", "athlete_id", "win"]].rename(columns={"win": "_win2"})
    agg = agg.merge(pm1, on=["competition_id", "athlete_id"], how="left")
    agg = agg.merge(pm2, on=["competition_id", "athlete_id"], how="left")
    agg["PM1&2V%"] = agg["PM1V%"] * agg["_win2"]
    agg = agg.drop(columns=["_win2"])

    # PEXMPT: any athlete with a result in a poule-having competition but
    # zero poule bouts recorded (real pool exemption, or an archive gap
    # where fie.org's own pool-results summary listed them without match
    # data -- e.g. 2025-242's actual champion, confirmed live: a
    # placeholder row with td=tr=0, qualified=False, absent from every
    # pool's row list). Derived from bout presence, not `results.exempt`,
    # to stay consistent with PVICT/PTR/etc. (see module docstring).
    all_in_comp = results.loc[results["competition_id"].isin(comps_with_data), ["competition_id", "athlete_id"]].drop_duplicates()
    played = agg[["competition_id", "athlete_id"]].drop_duplicates()
    played["_played"] = 1
    pexmpt_base = all_in_comp.merge(played, on=["competition_id", "athlete_id"], how="left")
    pexmpt_base["PEXMPT"] = pexmpt_base["_played"].isna().astype("Int64")
    agg = agg.merge(pexmpt_base[["competition_id", "athlete_id", "PEXMPT"]], on=["competition_id", "athlete_id"], how="outer")

    agg = agg[agg["competition_id"].isin(comps_with_data)]
    return agg


def _de_stats(bouts: pd.DataFrame, results: pd.DataFrame) -> pd.DataFrame:
    de = bouts[bouts["phase"] == "de"]
    comps_with_data = set(de["competition_id"].unique())
    ok = de[de["status"] == "ok"]
    exploded = _explode(ok)

    agg = exploded.groupby(["competition_id", "athlete_id"]).agg(
        TTR=("tr", "mean"),
        TTD=("td", "mean"),
        table_tr_std=("tr", "std"),
        table_td_std=("td", "std"),
        TMVAVG=("win", "sum"),
    ).reset_index()
    agg["TMT-DIFF"] = agg["TTD"] - agg["TTR"]

    # Q / T64+ / TPRE64 use ANY status (bye/forfeit still count as "reached
    # that round"), so derive from the raw (unexploded) bout rows.
    a_side = de[["competition_id", "athlete_a", "round"]].rename(columns={"athlete_a": "athlete_id"})
    b_side = de[de["athlete_b"].notna()][["competition_id", "athlete_b", "round"]].rename(columns={"athlete_b": "athlete_id"})
    participation = pd.concat([a_side, b_side], ignore_index=True)

    qualified = participation[["competition_id", "athlete_id"]].drop_duplicates()
    qualified["Q"] = 1

    t64 = participation[participation["round"] == "B64"][["competition_id", "athlete_id"]].drop_duplicates()
    t64["T64+"] = 1
    tpre64 = participation[participation["round"] == "A64"][["competition_id", "athlete_id"]].drop_duplicates()
    tpre64["TPRE64"] = 1

    out = qualified.merge(agg, on=["competition_id", "athlete_id"], how="left")
    out = out.merge(t64, on=["competition_id", "athlete_id"], how="left")
    out = out.merge(tpre64, on=["competition_id", "athlete_id"], how="left")
    out["T64+"] = out["T64+"].fillna(0).astype("Int64")
    out["TPRE64"] = out["TPRE64"].fillna(0).astype("Int64")
    out["TMVAVG"] = out["TMVAVG"].fillna(0)
    out["Q"] = out["Q"].astype("Int64")

    out = out[out["competition_id"].isin(comps_with_data)]

    # Explicit Q=0 rows for every athlete with a result in a DE-having
    # competition who never appears in any DE bout (eliminated in poules,
    # or otherwise never reached the tableau) -- without this, such athletes
    # get NaN (not 0) for Q after compute_stats's left-merge, which
    # disagrees with legacy's explicit Q=0 semantics.
    all_in_comp = results.loc[results["competition_id"].isin(comps_with_data), ["competition_id", "athlete_id"]].drop_duplicates()
    non_qualifiers = all_in_comp.merge(
        qualified[["competition_id", "athlete_id"]], on=["competition_id", "athlete_id"], how="left", indicator=True
    )
    non_qualifiers = non_qualifiers[non_qualifiers["_merge"] == "left_only"][["competition_id", "athlete_id"]].copy()
    non_qualifiers["Q"] = pd.array([0] * len(non_qualifiers), dtype="Int64")
    non_qualifiers["T64+"] = pd.array([0] * len(non_qualifiers), dtype="Int64")
    non_qualifiers["TPRE64"] = pd.array([0] * len(non_qualifiers), dtype="Int64")

    return pd.concat([out, non_qualifiers], ignore_index=True)


def compute_stats(bouts: pd.DataFrame, results: pd.DataFrame) -> pd.DataFrame:
    """One row per (competition_id, athlete_id): every result the athlete
    has (POS/points from `results`) plus every poule/DE-derived metric
    (NaN where fie.org has no bout data for that phase/competition/athlete —
    see module docstring)."""
    base = results[["competition_id", "athlete_id", "final_rank"]].rename(columns={"final_rank": "POS"})

    poule = _poule_stats(bouts, results)
    de = _de_stats(bouts, results)

    out = base.merge(poule, on=["competition_id", "athlete_id"], how="left")
    out = out.merge(de, on=["competition_id", "athlete_id"], how="left")

    # TMVAVG is null (not 0) when the athlete never qualified into the
    # tableau at all, per legacy semantics.
    out.loc[out["Q"] != 1, "TMVAVG"] = pd.NA

    ordered_cols = [
        "competition_id", "athlete_id", "POS", "Q", "PEXMPT", "PVICT", "PTR", "PTD",
        "PIND", "PT-DIFF", "PMTR", "PMTD", "PMT-DIFF", "p_tr_std", "p_td_std",
        "TTR", "TTD", "TMT-DIFF", "table_tr_std", "table_td_std", "TMVAVG",
        "PM1V%", "PM1&2V%", "T64+", "TPRE64",
    ]
    return out.reindex(columns=ordered_cols)
