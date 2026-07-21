"""Elo ratings per (weapon, gender) pool, with history.

Standard Elo: `R' = R + K*(actual - expected)`, `expected = 1/(1+10**((Ropp-R)/400))`.
Start rating 1500. `K=16` for poule bouts, `K=32` for DE bouts; each side's K
is doubled while they're "provisional" (their first 30 rated bouts in that
weapon/gender pool, tracked independently per side — one player being
provisional doesn't change the other's K). No margin-of-victory or time
decay in v1 (see `docs/backlog-phase3.md`).

Only `status == 'ok'` bouts count (byes/forfeits carry no real result to
rate on). Processing order: competitions by `start_date`, then within a
competition, poule bouts before DE bouts, DE rounds from largest bracket to
smallest (`_round_sort_key` orders on the numeric suffix of the round code,
e.g. `'A256' < 'A128' < 'A64' < 'B64' < ... < 'B2'`); within an identical
(phase, round) group there's no real chronology available from fie.org's
archive, so bouts are ordered deterministically (poule_no, bout_order,
athlete_a) rather than truly chronologically -- a documented simplification.

`ratings_history` is one row per (athlete, competition): the athlete's
rating immediately before their first rated bout of that competition
(`pre`) and immediately after their last (`post`) -- not one row per bout.
"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd

START_RATING = 1500.0
K_POULE = 16
K_DE = 32
PROVISIONAL_BOUTS = 30


def _round_sort_key(round_code: str) -> tuple[int, str]:
    digits = "".join(ch for ch in round_code if ch.isdigit())
    size = int(digits) if digits else 0
    return (-size, round_code)


def _ordered_bouts(bouts: pd.DataFrame) -> pd.DataFrame:
    """`bouts` for ONE competition, `status == 'ok'` only, in processing order."""
    ok = bouts[bouts["status"] == "ok"].copy()
    ok["_phase_rank"] = (ok["phase"] == "de").astype(int)
    ok["_round_key"] = ok["round"].map(_round_sort_key)
    ok = ok.sort_values(by=["_phase_rank", "_round_key", "poule_no", "bout_order", "athlete_a"])
    return ok.drop(columns=["_phase_rank", "_round_key"])


def compute_elo(bouts: pd.DataFrame, competitions: pd.DataFrame) -> pd.DataFrame:
    """Returns `ratings_history`: competition_id, athlete_id, weapon, gender,
    pre, post -- one row per athlete per competition they had a rated bout
    in, in `competitions.start_date` order.
    """
    comp_info = competitions.set_index("competition_id")[["weapon", "gender", "start_date"]]
    comp_order = comp_info.dropna(subset=["start_date"]).sort_values("start_date")

    ratings: dict[tuple[str, str, int], float] = defaultdict(lambda: START_RATING)
    bout_counts: dict[tuple[str, str, int], int] = defaultdict(int)

    history_rows: list[dict] = []

    bouts_by_comp = {cid: g for cid, g in bouts.groupby("competition_id")}

    for competition_id, row in comp_order.iterrows():
        weapon, gender = row["weapon"], row["gender"]
        comp_bouts = bouts_by_comp.get(competition_id)
        if comp_bouts is None:
            continue
        ordered = _ordered_bouts(comp_bouts)
        if ordered.empty:
            continue

        pre: dict[int, float] = {}
        post: dict[int, float] = {}

        for bout in ordered.itertuples(index=False):
            a, b = bout.athlete_a, bout.athlete_b
            key_a, key_b = (weapon, gender, a), (weapon, gender, b)
            for athlete, key in ((a, key_a), (b, key_b)):
                if athlete not in pre:
                    pre[athlete] = ratings[key]

            k_base = K_POULE if bout.phase == "poule" else K_DE
            k_a = k_base * 2 if bout_counts[key_a] < PROVISIONAL_BOUTS else k_base
            k_b = k_base * 2 if bout_counts[key_b] < PROVISIONAL_BOUTS else k_base

            ra, rb = ratings[key_a], ratings[key_b]
            expected_a = 1 / (1 + 10 ** ((rb - ra) / 400))
            actual_a = 1.0 if bout.winner == a else 0.0

            ratings[key_a] = ra + k_a * (actual_a - expected_a)
            ratings[key_b] = rb + k_b * ((1 - actual_a) - (1 - expected_a))
            bout_counts[key_a] += 1
            bout_counts[key_b] += 1

            post[a] = ratings[key_a]
            post[b] = ratings[key_b]

        for athlete_id in pre:
            history_rows.append(
                {
                    "competition_id": competition_id,
                    "athlete_id": athlete_id,
                    "weapon": weapon,
                    "gender": gender,
                    "pre": pre[athlete_id],
                    "post": post[athlete_id],
                }
            )

    return pd.DataFrame(history_rows, columns=["competition_id", "athlete_id", "weapon", "gender", "pre", "post"])


def current_ratings(ratings_history: pd.DataFrame, competitions: pd.DataFrame) -> pd.DataFrame:
    """Each athlete's latest `post` rating per (weapon, gender) pool, using
    `competitions.start_date` to find each athlete's most recent competition."""
    if ratings_history.empty:
        return pd.DataFrame(columns=["athlete_id", "weapon", "gender", "rating"])
    merged = ratings_history.merge(
        competitions[["competition_id", "start_date"]], on="competition_id", how="left"
    )
    merged = merged.sort_values("start_date")
    latest = merged.groupby(["athlete_id", "weapon", "gender"], as_index=False).last()
    return latest[["athlete_id", "weapon", "gender", "post"]].rename(columns={"post": "rating"})
