"""Unit tests for `elo.compute_elo` / `elo.current_ratings` on toy bout
sequences (per PLAN.md's verification section, ELO only needs toy-sequence
tests, not fixture-scale) -- plus a real-data sniff test against the frozen
2025/242 fixture."""
from pathlib import Path

import pandas as pd
import pytest

from ffs import devalue, elo
from ffs.fie_client import FieClient
from ffs.parse import parse_competition

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _competitions(*rows):
    return pd.DataFrame(rows)


def _bout(**kw):
    base = {
        "competition_id": "c1", "phase": "poule", "round": "poule",
        "poule_no": 1, "bout_order": 1, "status": "ok",
    }
    base.update(kw)
    return base


def test_single_bout_updates_both_ratings_symmetrically():
    bouts = pd.DataFrame([_bout(athlete_a=1, athlete_b=2, score_a=5, score_b=3, winner=1)])
    competitions = _competitions({"competition_id": "c1", "weapon": "E", "gender": "M", "start_date": "2020-01-01"})
    history = elo.compute_elo(bouts, competitions)

    assert len(history) == 2
    a = history[history["athlete_id"] == 1].iloc[0]
    b = history[history["athlete_id"] == 2].iloc[0]
    assert a["pre"] == pytest.approx(elo.START_RATING)
    assert b["pre"] == pytest.approx(elo.START_RATING)
    # Equal pre-ratings -> expected=0.5; both provisional -> K = 2*16 = 32.
    assert a["post"] == pytest.approx(1500 + 32 * 0.5)
    assert b["post"] == pytest.approx(1500 - 32 * 0.5)
    # Zero-sum: gain for the winner exactly offsets the loser's loss.
    assert (a["post"] - a["pre"]) == pytest.approx(-(b["post"] - b["pre"]))


def test_de_bouts_use_higher_k_than_poule():
    poule_bouts = pd.DataFrame([_bout(phase="poule", round="poule", athlete_a=1, athlete_b=2, score_a=5, score_b=3, winner=1)])
    de_bouts = pd.DataFrame([_bout(phase="de", round="B64", poule_no=None, athlete_a=1, athlete_b=2, score_a=15, score_b=10, winner=1)])
    competitions = _competitions({"competition_id": "c1", "weapon": "E", "gender": "M", "start_date": "2020-01-01"})

    poule_history = elo.compute_elo(poule_bouts, competitions)
    de_history = elo.compute_elo(de_bouts, competitions)

    poule_gain = poule_history.loc[poule_history["athlete_id"] == 1, "post"].iloc[0] - elo.START_RATING
    de_gain = de_history.loc[de_history["athlete_id"] == 1, "post"].iloc[0] - elo.START_RATING
    assert de_gain > poule_gain


def test_provisional_k_doubles_until_threshold():
    # Same two athletes play PROVISIONAL_BOUTS + 5 poule bouts across
    # separate competitions, athlete 1 always winning. The rating gain per
    # bout should shrink once bout 31 (K halves from provisional).
    rows = []
    comps = []
    for i in range(elo.PROVISIONAL_BOUTS + 5):
        cid = f"c{i}"
        rows.append(_bout(competition_id=cid, athlete_a=1, athlete_b=2, score_a=5, score_b=0, winner=1))
        comps.append({"competition_id": cid, "weapon": "E", "gender": "M", "start_date": f"2020-01-{i + 1:02d}"})
    bouts = pd.DataFrame(rows)
    competitions = pd.DataFrame(comps)

    history = elo.compute_elo(bouts, competitions).merge(competitions, on="competition_id")
    history = history.sort_values("start_date")
    gains = (history[history["athlete_id"] == 1]["post"] - history[history["athlete_id"] == 1]["pre"]).reset_index(drop=True)

    provisional_gain = gains.iloc[0]
    later_gain = gains.iloc[-1]
    assert later_gain < provisional_gain


def test_only_ok_status_bouts_are_rated():
    bouts = pd.DataFrame([
        _bout(athlete_a=1, athlete_b=2, score_a=0, score_b=0, winner=1, status="forfeit"),
    ])
    competitions = _competitions({"competition_id": "c1", "weapon": "E", "gender": "M", "start_date": "2020-01-01"})
    history = elo.compute_elo(bouts, competitions)
    assert history.empty


def test_current_ratings_takes_latest_by_start_date():
    history = pd.DataFrame([
        {"competition_id": "c1", "athlete_id": 1, "weapon": "E", "gender": "M", "pre": 1500.0, "post": 1516.0},
        {"competition_id": "c2", "athlete_id": 1, "weapon": "E", "gender": "M", "pre": 1516.0, "post": 1530.0},
    ])
    competitions = pd.DataFrame([
        {"competition_id": "c1", "start_date": "2020-01-01"},
        {"competition_id": "c2", "start_date": "2021-01-01"},
    ])
    latest = elo.current_ratings(history, competitions)
    assert len(latest) == 1
    assert latest.iloc[0]["rating"] == pytest.approx(1530.0)


def test_current_ratings_empty_input():
    history = pd.DataFrame(columns=["competition_id", "athlete_id", "weapon", "gender", "pre", "post"])
    competitions = pd.DataFrame(columns=["competition_id", "start_date"])
    latest = elo.current_ratings(history, competitions)
    assert latest.empty


@pytest.fixture(scope="module")
def client():
    return FieClient(cache_dir=FIXTURES_DIR)


def test_elo_sniff_test_top_of_pool_is_a_medalist(client):
    # Sanity check on real data: over just this one fixture competition
    # (2025/242 Men's Epee Worlds), the highest post-rating should belong
    # to a podium finisher, not a first-round loser.
    comp = client.fetch_competition(2025, 242)
    decoded = devalue.unflatten(comp["raw"])
    queries = devalue.extract_queries(decoded)
    ranking_items = client.fetch_results_ranking(2025, 242)
    tables = parse_competition(
        season=2025, comp_id=242, tournament_id=comp["tournament_id"],
        queries=queries, ranking_items=ranking_items,
    )
    competitions = tables["competitions"]
    history = elo.compute_elo(tables["bouts"], competitions)
    top = history.sort_values("post", ascending=False).iloc[0]
    medalist_ranks = tables["results"].set_index("athlete_id")["final_rank"]
    assert medalist_ranks.loc[top["athlete_id"]] <= 8
