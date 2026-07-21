"""Unit tests for `h2h.build_h2h` on toy bout sequences (H2H, like ELO, only
needs toy-sequence coverage per PLAN.md's verification section)."""
import pandas as pd
import pytest

from ffs import h2h


def _competitions(*rows):
    return pd.DataFrame(rows)


def test_pair_normalized_regardless_of_athlete_a_b_order():
    bouts = pd.DataFrame([
        {"competition_id": "c1", "phase": "poule", "round": "poule", "poule_no": 1, "bout_order": 1,
         "athlete_a": 2, "athlete_b": 1, "score_a": 3, "score_b": 5, "winner": 1, "status": "ok"},
    ])
    competitions = _competitions({"competition_id": "c1", "weapon": "E", "gender": "M", "start_date": "2020-01-01"})
    h2h_df, h2h_bouts_df = h2h.build_h2h(bouts, competitions)

    row = h2h_bouts_df.iloc[0]
    assert row["athlete_lo"] == 1
    assert row["athlete_hi"] == 2
    assert row["score_lo"] == 5
    assert row["score_hi"] == 3

    pair = h2h_df.iloc[0]
    assert (pair["athlete_lo"], pair["athlete_hi"]) == (1, 2)
    assert pair["bouts"] == 1
    assert pair["wins_lo"] == 1
    assert pair["wins_hi"] == 0
    assert pair["td_lo"] == 5
    assert pair["td_hi"] == 3


def test_byes_excluded_but_forfeits_kept():
    bouts = pd.DataFrame([
        {"competition_id": "c1", "phase": "de", "round": "B32", "poule_no": None, "bout_order": 0,
         "athlete_a": 5, "athlete_b": None, "score_a": 10, "score_b": None, "winner": 5, "status": "bye"},
        {"competition_id": "c1", "phase": "de", "round": "B64", "poule_no": None, "bout_order": 0,
         "athlete_a": 1, "athlete_b": 2, "score_a": 0, "score_b": 0, "winner": 2, "status": "forfeit"},
    ])
    competitions = _competitions({"competition_id": "c1", "weapon": "E", "gender": "M", "start_date": "2020-01-01"})
    h2h_df, h2h_bouts_df = h2h.build_h2h(bouts, competitions)

    # The bye involves no real opponent -- excluded entirely.
    assert len(h2h_bouts_df) == 1
    assert h2h_bouts_df.iloc[0]["status"] == "forfeit"

    pair = h2h_df.iloc[0]
    assert pair["bouts"] == 1
    assert pair["wins_lo"] == 0  # athlete_lo=1, winner=2
    assert pair["wins_hi"] == 1
    # Forfeits carry no real score -- excluded from touch sums.
    assert pd.isna(pair["td_lo"])
    assert pd.isna(pair["td_hi"])


def test_touches_summed_only_over_ok_bouts():
    bouts = pd.DataFrame([
        {"competition_id": "c1", "phase": "poule", "round": "poule", "poule_no": 1, "bout_order": 1,
         "athlete_a": 1, "athlete_b": 2, "score_a": 5, "score_b": 3, "winner": 1, "status": "ok"},
        {"competition_id": "c2", "phase": "de", "round": "B64", "poule_no": None, "bout_order": 0,
         "athlete_a": 1, "athlete_b": 2, "score_a": 0, "score_b": 0, "winner": 1, "status": "forfeit"},
    ])
    competitions = _competitions(
        {"competition_id": "c1", "weapon": "E", "gender": "M", "start_date": "2020-01-01"},
        {"competition_id": "c2", "weapon": "E", "gender": "M", "start_date": "2020-02-01"},
    )
    h2h_df, h2h_bouts_df = h2h.build_h2h(bouts, competitions)

    pair = h2h_df.iloc[0]
    assert pair["bouts"] == 2
    assert pair["wins_lo"] == 2
    assert pair["poule_bouts"] == 1
    assert pair["de_bouts"] == 1
    # Only the 'ok' poule bout's touches count.
    assert pair["td_lo"] == 5
    assert pair["td_hi"] == 3
    assert pair["last_met"] == "2020-02-01"


def test_different_weapon_gender_pools_kept_separate():
    bouts = pd.DataFrame([
        {"competition_id": "c1", "phase": "poule", "round": "poule", "poule_no": 1, "bout_order": 1,
         "athlete_a": 1, "athlete_b": 2, "score_a": 5, "score_b": 3, "winner": 1, "status": "ok"},
        {"competition_id": "c2", "phase": "poule", "round": "poule", "poule_no": 1, "bout_order": 1,
         "athlete_a": 1, "athlete_b": 2, "score_a": 4, "score_b": 5, "winner": 2, "status": "ok"},
    ])
    competitions = _competitions(
        {"competition_id": "c1", "weapon": "E", "gender": "M", "start_date": "2020-01-01"},
        {"competition_id": "c2", "weapon": "S", "gender": "M", "start_date": "2020-02-01"},
    )
    h2h_df, h2h_bouts_df = h2h.build_h2h(bouts, competitions)

    assert len(h2h_df) == 2
    weapons = set(h2h_df["weapon"])
    assert weapons == {"E", "S"}
    for _, pair in h2h_df.iterrows():
        assert pair["bouts"] == 1
