"""Tests for `stats.compute_stats`, using the frozen 2025/242 and 2025/245
fixtures (same fixtures/loading pattern as `test_parse.py`, no network hit)
plus a couple of toy DataFrames for edge cases that are awkward to find in
real data.

Golden values below were hand-checked against the parsed fixture data (see
`M4_HANDOFF.md` and the module docstring in `src/ffs/stats.py` for how
PIND/Q/PEXMPT were derived and verified).
"""
from pathlib import Path

import pandas as pd
import pytest

from ffs import devalue, stats
from ffs.fie_client import FieClient
from ffs.parse import parse_competition

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def client():
    return FieClient(cache_dir=FIXTURES_DIR)


def _parse(client, season, comp_id):
    comp = client.fetch_competition(season, comp_id)
    decoded = devalue.unflatten(comp["raw"])
    queries = devalue.extract_queries(decoded)
    ranking_items = client.fetch_results_ranking(season, comp_id)
    return parse_competition(
        season=season,
        comp_id=comp_id,
        tournament_id=comp["tournament_id"],
        queries=queries,
        ranking_items=ranking_items,
    )


@pytest.fixture(scope="module")
def tables_242(client):
    return _parse(client, 2025, 242)


@pytest.fixture(scope="module")
def stats_242(tables_242):
    return stats.compute_stats(tables_242["bouts"], tables_242["results"])


def test_242_row_count_matches_results(tables_242, stats_242):
    assert len(stats_242) == len(tables_242["results"])


def test_242_champion_has_no_poule_data_but_qualified(stats_242):
    # KANO Koki (34385): fie.org's own pool-results summary lists a
    # placeholder row for him (never appears in any pool's actual fencer
    # list) -- see stats.py's module docstring. PEXMPT=1, every poule
    # numeric column NaN, but he still won the tableau (Q=1, T64+=1,
    # TPRE64=0 -- never played an A64-round bout).
    row = stats_242[stats_242["athlete_id"] == 34385].iloc[0]
    assert row["POS"] == 1
    assert row["Q"] == 1
    assert row["PEXMPT"] == 1
    assert row["T64+"] == 1
    assert row["TPRE64"] == 0
    for col in stats.POULE_COLS:
        if col == "PEXMPT":
            continue
        assert pd.isna(row[col]), f"{col} should be NaN"


def test_242_poule_stats_full_pool_winner(stats_242):
    # Athlete 53707 (pool 1) won all 6 of their poule matches -- see
    # test_242_full_poule in test_parse.py for the raw bout rows.
    row = stats_242[stats_242["athlete_id"] == 53707].iloc[0]
    assert row["PVICT"] == 6
    assert row["PTR"] == 14
    assert row["PTD"] == 30
    assert row["PIND"] == 1.0
    assert row["PT-DIFF"] == 16
    assert row["PEXMPT"] == 0


def test_242_pool_participant_pind_is_win_ratio_not_touch_diff(stats_242):
    # Athlete 42729 (pool 1): 3 wins out of 6 poule matches -> PIND=0.5,
    # NOT the touch differential (PTD-PTR=3, which would be wrong).
    row = stats_242[stats_242["athlete_id"] == 42729].iloc[0]
    assert row["PVICT"] == 3
    assert row["PIND"] == pytest.approx(0.5)
    assert row["PIND"] != row["PT-DIFF"]


def test_242_non_qualifier_has_explicit_q_zero(stats_242, tables_242):
    # Any athlete with a result in this DE-having competition who never
    # appears in a DE bout must get Q=0 (not NaN) -- see stats.py bug #2.
    de_bouts = tables_242["bouts"]
    de_athletes = set(de_bouts.loc[de_bouts["phase"] == "de", "athlete_a"].dropna()) | set(
        de_bouts.loc[de_bouts["phase"] == "de", "athlete_b"].dropna()
    )
    non_qualifiers = stats_242[~stats_242["athlete_id"].isin(de_athletes)]
    assert len(non_qualifiers) > 0
    assert (non_qualifiers["Q"] == 0).all()
    assert non_qualifiers["T64+"].eq(0).all()
    assert non_qualifiers["TPRE64"].eq(0).all()
    assert non_qualifiers["TMVAVG"].isna().all()


def test_pm1v_toy_seed_order_proxy():
    # Toy pool of 3: seeds 1/2/3 by bout_order. Athlete 10 (seed-adjacent
    # opponent 20) beats both opponents.
    bouts = pd.DataFrame(
        [
            {"competition_id": "c1", "phase": "poule", "round": "poule", "poule_no": 1,
             "bout_order": 2, "athlete_a": 10, "athlete_b": 20, "score_a": 5, "score_b": 1,
             "winner": 10, "status": "ok"},
            {"competition_id": "c1", "phase": "poule", "round": "poule", "poule_no": 1,
             "bout_order": 3, "athlete_a": 10, "athlete_b": 30, "score_a": 5, "score_b": 2,
             "winner": 10, "status": "ok"},
            {"competition_id": "c1", "phase": "poule", "round": "poule", "poule_no": 1,
             "bout_order": 3, "athlete_a": 20, "athlete_b": 30, "score_a": 3, "score_b": 5,
             "winner": 30, "status": "ok"},
        ]
    )
    results = pd.DataFrame(
        [
            {"competition_id": "c1", "athlete_id": 10, "final_rank": 1},
            {"competition_id": "c1", "athlete_id": 20, "final_rank": 3},
            {"competition_id": "c1", "athlete_id": 30, "final_rank": 2},
        ]
    )
    out = stats.compute_stats(bouts, results)
    row10 = out[out["athlete_id"] == 10].iloc[0]
    # athlete 10's lowest-seed opponent is 20 (seed 2, since 10 has no
    # own seed entry and falls back to bout_order); beat both -> both flags 1.
    assert row10["PM1V%"] == 1
    assert row10["PM1&2V%"] == 1


def test_forfeit_bouts_excluded_from_poule_numeric_stats():
    bouts = pd.DataFrame(
        [
            {"competition_id": "c1", "phase": "poule", "round": "poule", "poule_no": 1,
             "bout_order": 2, "athlete_a": 1, "athlete_b": 2, "score_a": 0, "score_b": 0,
             "winner": 1, "status": "forfeit"},
        ]
    )
    results = pd.DataFrame(
        [
            {"competition_id": "c1", "athlete_id": 1, "final_rank": 1},
            {"competition_id": "c1", "athlete_id": 2, "final_rank": 2},
        ]
    )
    out = stats.compute_stats(bouts, results)
    # Both athletes have a poule-having competition but zero *ok* poule
    # bouts -- PEXMPT=1, all poule numeric columns NaN.
    assert (out["PEXMPT"] == 1).all()
    for col in stats.POULE_COLS:
        if col == "PEXMPT":
            continue
        assert out[col].isna().all()
