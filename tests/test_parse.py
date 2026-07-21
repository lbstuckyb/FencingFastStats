"""Golden tests against frozen fie.org payloads for two 2025 World
Championships events (`tests/fixtures/`):

- 2025/242 (Men's Epee, 215 entries): the large fixture — covers a full 7-fencer
  poule, the B2 gold-medal bout, and the tournament's one DE forfeit.
- 2025/245 (Women's Sabre, 125 entries): a smaller fixture with more DE byes,
  for shape variety.

All values below were hand-checked against the live fie.org page on
2026-07-14 (see PLAN.md Progress Log, M2).
"""
from pathlib import Path

import pytest

from ffs import devalue, schema
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
def tables_245(client):
    return _parse(client, 2025, 245)


def test_242_validates_clean(tables_242):
    assert schema.validate_tables(tables_242) == []


def test_242_competition_info(tables_242):
    comp = tables_242["competitions"].iloc[0]
    assert comp["competition_id"] == "2025-242"
    assert comp["weapon"] == "E"
    assert comp["gender"] == "M"
    assert comp["n_entries"] == 215


def test_242_entry_and_bout_counts(tables_242):
    assert len(tables_242["results"]) == 215
    assert len(tables_242["athletes"]) == 215
    assert len(tables_242["bouts"]) == 866


def test_242_champion(tables_242):
    results = tables_242["results"]
    athletes = tables_242["athletes"]
    champ = results[results["final_rank"] == 1].iloc[0]
    assert champ["athlete_id"] == 34385
    name = athletes.loc[athletes["athlete_id"] == 34385, "name"].iloc[0]
    assert name == "KANO Koki"


def test_242_full_poule(tables_242):
    bouts = tables_242["bouts"]
    pool1 = bouts[(bouts["phase"] == "poule") & (bouts["poule_no"] == 1)]
    # 7 fencers -> C(7,2) round-robin bouts, all completed.
    assert len(pool1) == 21
    assert (pool1["status"] == "ok").all()
    fencers_in_pool = set(pool1["athlete_a"]) | set(pool1["athlete_b"])
    assert fencers_in_pool == {42729, 26206, 39179, 53707, 38901, 40048, 30645}


def test_242_gold_medal_bout(tables_242):
    bouts = tables_242["bouts"]
    b2 = bouts[bouts["round"] == "B2"]
    assert len(b2) == 1
    row = b2.iloc[0]
    assert row["phase"] == "de"
    assert row["status"] == "ok"
    # SIKLOSI (30081) < KANO (34385) so SIKLOSI is athlete_a.
    assert row["athlete_a"] == 30081
    assert row["athlete_b"] == 34385
    assert row["score_a"] == 9
    assert row["score_b"] == 10
    assert row["winner"] == 34385


def test_242_de_forfeit(tables_242):
    bouts = tables_242["bouts"]
    forfeits = bouts[bouts["status"] == "forfeit"]
    assert len(forfeits) == 1
    row = forfeits.iloc[0]
    assert row["round"] == "B64"
    assert row["athlete_a"] == 14714
    assert row["athlete_b"] == 28816
    assert row["winner"] == 14714
    assert row["score_a"] == 0
    assert row["score_b"] == 0


def test_245_validates_clean(tables_245):
    assert schema.validate_tables(tables_245) == []


def test_245_competition_info(tables_245):
    comp = tables_245["competitions"].iloc[0]
    assert comp["competition_id"] == "2025-245"
    assert comp["weapon"] == "S"
    assert comp["gender"] == "F"
    assert comp["n_entries"] == 125


def test_245_champion(tables_245):
    results = tables_245["results"]
    athletes = tables_245["athletes"]
    champ = results[results["final_rank"] == 1].iloc[0]
    assert champ["athlete_id"] == 25208
    name = athletes.loc[athletes["athlete_id"] == 25208, "name"].iloc[0]
    assert name == "EGORIAN Yana"


def test_245_bout_counts(tables_245):
    bouts = tables_245["bouts"]
    assert len(bouts) == 471
    assert (bouts["status"] == "bye").sum() == 62
    assert (bouts["status"] == "forfeit").sum() == 0


def test_poule_0_0_no_show_classified_as_forfeit():
    """A fenced bout can never legitimately end 0-0 -- fie.org still tags
    this no-show case with a normal `v` winner flag, but legacy's pipeline
    excluded it from all poule stats. Construct a minimal synthetic pool
    payload (2 fencers, one 0-0 match) and assert the parser now tags it
    'forfeit' (with the winner kept) instead of 'ok'."""
    queries = {
        ("competitions", 999, 2099): {
            "name": "Test Open", "location": "Testville", "country": "USA",
            "startDate": "2020-01-01", "weapon": "E", "gender": "M",
            "category": "S", "competitionCategory": "1", "entriesCount": 2,
        },
        ("competitions", "results", "pools", 999, 2099): {
            "pools": [
                {
                    "poolId": 1,
                    "rows": [
                        {"fencerId": 100, "name": "A", "nationality": "USA",
                         "matches": [None, {"score": 0, "v": True}]},
                        {"fencerId": 200, "name": "B", "nationality": "FRA",
                         "matches": [{"score": 0, "v": False}, None]},
                    ],
                }
            ]
        },
        ("competitions", "pool", "results", 999, 2099): {"rows": []},
        ("competitions", "results", "tableau", 999, 2099): {"tableau": []},
    }
    ranking_items = [
        {"fencer": {"id": 100, "name": "A", "countryCode": "USA", "date": "1990-01-01"}, "rank": 1, "points": 10},
        {"fencer": {"id": 200, "name": "B", "countryCode": "FRA", "date": "1990-01-01"}, "rank": 2, "points": 8},
    ]
    tables = parse_competition(
        season=2099, comp_id=999, tournament_id=1, queries=queries, ranking_items=ranking_items,
    )
    bouts = tables["bouts"]
    assert len(bouts) == 1
    row = bouts.iloc[0]
    assert row["status"] == "forfeit"
    assert row["score_a"] == 0
    assert row["score_b"] == 0
    assert row["winner"] == 100
