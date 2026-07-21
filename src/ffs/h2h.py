"""Head-to-head aggregates, grouped by unordered athlete pair within
(weapon, gender).

`build_h2h` returns two tables:

- `h2h_bouts`: one row per real encounter (`status` in `'ok'`/`'forfeit'` --
  byes have no real opponent so are excluded) with the pair normalized to
  `(athlete_lo, athlete_hi)` = sorted athlete ids, so each pair has a single
  canonical key regardless of who's listed first in the underlying bout.
- `h2h`: one row per (athlete_lo, athlete_hi, weapon, gender) with bout/win
  counts (touches only summed over `status == 'ok'` bouts, since forfeits
  carry no real score) and `last_met`.
"""
from __future__ import annotations

import pandas as pd

KEY = ["athlete_lo", "athlete_hi", "weapon", "gender"]


def build_h2h(bouts: pd.DataFrame, competitions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    real = bouts[bouts["status"].isin(["ok", "forfeit"])].copy()
    comp_info = competitions.set_index("competition_id")[["weapon", "gender", "start_date"]]
    real = real.join(comp_info, on="competition_id")

    swap = real["athlete_a"] > real["athlete_b"]
    real["athlete_lo"] = real["athlete_a"].where(~swap, real["athlete_b"])
    real["athlete_hi"] = real["athlete_b"].where(~swap, real["athlete_a"])
    real["score_lo"] = real["score_a"].where(~swap, real["score_b"])
    real["score_hi"] = real["score_b"].where(~swap, real["score_a"])

    h2h_bouts = real[[
        "competition_id", "weapon", "gender", "phase", "round", "start_date",
        "athlete_lo", "athlete_hi", "score_lo", "score_hi", "winner", "status",
    ]].reset_index(drop=True)

    win_lo = (h2h_bouts["winner"] == h2h_bouts["athlete_lo"]).astype(int)
    grp = h2h_bouts.assign(win_lo=win_lo).groupby(KEY)
    h2h = grp.agg(
        bouts=("winner", "size"),
        wins_lo=("win_lo", "sum"),
        poule_bouts=("phase", lambda s: int((s == "poule").sum())),
        de_bouts=("phase", lambda s: int((s == "de").sum())),
        last_met=("start_date", "max"),
    ).reset_index()
    h2h["wins_hi"] = h2h["bouts"] - h2h["wins_lo"]

    ok = h2h_bouts[h2h_bouts["status"] == "ok"]
    touches = ok.groupby(KEY).agg(td_lo=("score_lo", "sum"), td_hi=("score_hi", "sum")).reset_index()
    h2h = h2h.merge(touches, on=KEY, how="left")

    h2h = h2h[KEY + ["bouts", "wins_lo", "wins_hi", "td_lo", "td_hi", "poule_bouts", "de_bouts", "last_met"]]
    return h2h, h2h_bouts
