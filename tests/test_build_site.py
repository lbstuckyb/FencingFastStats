"""Tests for `build_site`'s artifact builders.

These use small hand-written tables rather than the parquet fixtures: the
builders are pure table->dict transforms, and the interesting behaviour
(shard pruning, pool scoping, the h2h perspective flip) is easier to pin
down on data whose expected output can be read off by eye.
"""
import pandas as pd
import pytest

from ffs import build_site


@pytest.fixture
def tables():
    competitions = pd.DataFrame([
        # (weapon, gender) pools: EM has two comps, EF one, FM one.
        {"competition_id": "2024-1", "season": 2024, "tournament_id": 1, "name": "Coupe du Monde",
         "city": "Bern", "country": "Switzerland", "start_date": "2024-03-01", "weapon": "E",
         "gender": "M", "category": "S", "level": "CDM", "n_entries": 200},
        {"competition_id": "2024-2", "season": 2024, "tournament_id": 2, "name": "Grand Prix",
         "city": "Doha", "country": "Qatar", "start_date": "2024-05-01", "weapon": "E",
         "gender": "M", "category": "S", "level": "GP", "n_entries": 150},
        {"competition_id": "2023-3", "season": 2023, "tournament_id": 3, "name": "Championnats du Monde",
         "city": "Milan", "country": "Italy", "start_date": "2023-07-01", "weapon": "E",
         "gender": "F", "category": "S", "level": "CM", "n_entries": 120},
        {"competition_id": "2024-4", "season": 2024, "tournament_id": 4, "name": "Coupe du Monde",
         "city": "Paris", "country": "France", "start_date": "2024-02-01", "weapon": "F",
         "gender": "M", "category": "S", "level": "CDM", "n_entries": 180},
    ])
    athletes = pd.DataFrame([
        {"athlete_id": 1, "name": "ALPHA Ann", "country": "FRA", "birth_year": 1990, "hand": "Right"},
        {"athlete_id": 2, "name": "BETA Bob", "country": "ITA", "birth_year": 1995, "hand": None},
        {"athlete_id": 3, "name": "GAMMA Gil", "country": "JPN", "birth_year": None, "hand": None},
    ])
    results = pd.DataFrame([
        {"competition_id": "2024-1", "athlete_id": 1, "final_rank": 1, "seed": 3, "exempt": False, "points": 32},
        {"competition_id": "2024-1", "athlete_id": 2, "final_rank": 2, "seed": 1, "exempt": True, "points": 26},
        {"competition_id": "2024-2", "athlete_id": 1, "final_rank": 3, "seed": 2, "exempt": False, "points": 20},
        {"competition_id": "2024-2", "athlete_id": 2, "final_rank": 1, "seed": 4, "exempt": False, "points": 32},
        # Athlete 3 has a single competition -- below the shard threshold.
        {"competition_id": "2024-4", "athlete_id": 3, "final_rank": 5, "seed": 9, "exempt": False, "points": 10},
    ])
    stats = pd.DataFrame([
        {"competition_id": "2024-1", "athlete_id": 1, "POS": 1, "Q": 1, "PVICT": 5, "PTR": 12, "PTD": 25,
         "PIND": 0.83, "TTR": 10.0, "TTD": 15.0, "TMVAVG": 4, "T64+": 1, "T96+": 1},
        {"competition_id": "2024-1", "athlete_id": 2, "POS": 2, "Q": 1, "PVICT": 4, "PTR": 15, "PTD": 22,
         "PIND": 0.67, "TTR": 12.0, "TTD": 14.0, "TMVAVG": 3, "T64+": 1, "T96+": 1},
        {"competition_id": "2024-2", "athlete_id": 1, "POS": 3, "Q": 1, "PVICT": 4, "PTR": 14, "PTD": 23,
         "PIND": 0.67, "TTR": 11.0, "TTD": 13.0, "TMVAVG": 2, "T64+": 1, "T96+": 1},
        {"competition_id": "2024-2", "athlete_id": 2, "POS": 1, "Q": 1, "PVICT": 6, "PTR": 10, "PTD": 30,
         "PIND": 1.0, "TTR": 9.0, "TTD": 15.0, "TMVAVG": 4, "T64+": 1, "T96+": 1},
        {"competition_id": "2024-4", "athlete_id": 3, "POS": 5, "Q": 1, "PVICT": 3, "PTR": 18, "PTD": 20,
         "PIND": 0.5, "TTR": 13.0, "TTD": 12.0, "TMVAVG": 1, "T64+": 1, "T96+": 1},
    ])
    ratings = pd.DataFrame([
        {"competition_id": "2024-1", "athlete_id": 1, "weapon": "E", "gender": "M", "pre": 1500.0, "post": 1540.0},
        {"competition_id": "2024-2", "athlete_id": 1, "weapon": "E", "gender": "M", "pre": 1540.0, "post": 1555.5},
        {"competition_id": "2024-1", "athlete_id": 2, "weapon": "E", "gender": "M", "pre": 1500.0, "post": 1480.0},
        {"competition_id": "2024-2", "athlete_id": 2, "weapon": "E", "gender": "M", "pre": 1480.0, "post": 1530.0},
    ])
    h2h = pd.DataFrame([
        {"athlete_lo": 1, "athlete_hi": 2, "weapon": "E", "gender": "M", "bouts": 5, "wins_lo": 3,
         "wins_hi": 2, "td_lo": 60, "td_hi": 55, "poule_bouts": 3, "de_bouts": 2, "last_met": "2024-05-01"},
        # Below MIN_H2H_BOUTS_FOR_SUMMARY -- must not appear as a rival.
        {"athlete_lo": 1, "athlete_hi": 3, "weapon": "E", "gender": "M", "bouts": 1, "wins_lo": 1,
         "wins_hi": 0, "td_lo": 15, "td_hi": 9, "poule_bouts": 1, "de_bouts": 0, "last_met": "2024-03-01"},
    ])
    return {
        "competitions": competitions, "athletes": athletes, "results": results,
        "stats_fencer_comp": stats, "ratings_history": ratings, "h2h": h2h,
    }


def test_build_meta_counts_the_canonical_tables(tables):
    meta = build_site.build_meta(tables, bouts_count=987)

    assert meta["season_min"] == 2023
    assert meta["season_max"] == 2024
    assert meta["n_competitions"] == 4
    assert meta["n_athletes"] == 3
    assert meta["n_bouts"] == 987
    assert meta["weapons"] == ["E", "F", "S"]


def test_fencer_index_prunes_single_competition_athletes(tables):
    entries, shard_ids = build_site.build_fencer_index(
        tables["results"], tables["competitions"], tables["athletes"]
    )

    # Athlete 3 fenced one competition -> no shard, and no index entry either,
    # so search can never link to a profile that was never written.
    assert shard_ids == {1, 2}
    assert [e["i"] for e in entries] == [1, 2]
    assert entries[0] == {"i": 1, "n": "ALPHA Ann", "c": "FRA", "w": "E", "g": "M"}


def test_fencer_index_records_every_weapon_fenced(tables):
    tables["results"] = pd.concat([
        tables["results"],
        pd.DataFrame([{"competition_id": "2024-4", "athlete_id": 1, "final_rank": 8,
                       "seed": 5, "exempt": False, "points": 8}]),
    ], ignore_index=True)

    entries, _ = build_site.build_fencer_index(
        tables["results"], tables["competitions"], tables["athletes"]
    )

    assert next(e for e in entries if e["i"] == 1)["w"] == "EF"


def test_load_tables_strips_athlete_names(tmp_path, monkeypatch, tables):
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    tables["athletes"].loc[0, "name"] = "  ALPHA Ann "
    tables["bouts"] = pd.DataFrame({"competition_id": ["2024-1"]})
    for name, df in tables.items():
        df.to_parquet(canonical / f"{name}.parquet")
    monkeypatch.setattr(build_site, "CANONICAL_DIR", canonical)

    loaded = build_site._load_tables()

    assert loaded["athletes"].loc[0, "name"] == "ALPHA Ann"


def test_summary_is_scoped_to_one_pool(tables):
    summary = build_site.build_summary("E", "M", tables)

    assert summary["weapon"] == "E" and summary["gender"] == "M"
    # Latest rating per athlete, best first: athlete 1 ends on 1555.5.
    assert [(f["id"], f["rating"]) for f in summary["elo_top"]] == [(1, 1555.5), (2, 1530.0)]
    # Newest competition first, with the winner attached.
    assert [c["id"] for c in summary["recent_competitions"]] == ["2024-2", "2024-1"]
    assert summary["recent_competitions"][0]["champion"] == {"id": 2, "name": "BETA Bob"}
    assert summary["recent_competitions"][0]["n_entries"] == 150
    # One title each, and both fencers podiumed twice -- the F pools' rows
    # (athlete 3) must not leak into this pool's leaderboards.
    assert {(f["id"], f["count"]) for f in summary["leaderboards"]["titles"]} == {(1, 1), (2, 1)}
    assert {(f["id"], f["count"]) for f in summary["leaderboards"]["podiums"]} == {(1, 2), (2, 2)}
    assert all(f["id"] != 3 for f in summary["leaderboards"]["podiums"])


def test_summary_of_an_empty_pool_is_still_valid(tables):
    summary = build_site.build_summary("S", "F", tables)

    assert summary["elo_top"] == []
    assert summary["recent_competitions"] == []
    assert summary["leaderboards"] == {"titles": [], "podiums": []}


def _context(tables):
    primary_gender = build_site._athlete_primary_gender(tables["results"], tables["competitions"])
    return build_site.ProfileContext(tables, primary_gender)


def test_fencer_profile_career_results_and_timeline(tables):
    profile = build_site.build_fencer_profile(1, _context(tables))

    assert profile["id"] == 1
    assert profile["name"] == "ALPHA Ann"
    assert profile["birth_year"] == 1990
    assert profile["hand"] == "Right"

    assert profile["career"] == [
        {"weapon": "E", "n_comps": 2, "best_rank": 1, "titles": 1, "current_rating": 1555.5}
    ]

    # Results are newest-first and carry the stats row for that competition.
    assert [r["competition_id"] for r in profile["results"]] == ["2024-2", "2024-1"]
    assert profile["results"][1]["POS"] == 1
    assert profile["results"][1]["PVICT"] == 5
    assert profile["results"][1]["city"] == "Bern"

    # The timeline is oldest-first (chart x-axis order) and keeps pre/post.
    assert [(p["date"], p["post"]) for p in profile["rating_timeline"]] == [
        ("2024-03-01", 1540.0), ("2024-05-01", 1555.5)
    ]


def test_fencer_profile_rivals_use_this_athletes_perspective(tables):
    ctx = _context(tables)

    mine = build_site.build_fencer_profile(1, ctx)["top_rivals"]
    theirs = build_site.build_fencer_profile(2, ctx)["top_rivals"]

    # Athlete 3 met athlete 1 only once -- under the >=3 bout floor.
    assert [r["id"] for r in mine] == [2]
    assert (mine[0]["wins"], mine[0]["losses"]) == (3, 2)
    # The same unordered h2h row, seen from the other side, flips W-L.
    assert [r["id"] for r in theirs] == [1]
    assert (theirs[0]["wins"], theirs[0]["losses"]) == (2, 3)
    assert theirs[0]["last_met"] == "2024-05-01"


def test_fencer_profile_missing_optional_fields_are_null(tables):
    profile = build_site.build_fencer_profile(2, _context(tables))

    assert profile["hand"] is None
    assert profile["birth_year"] == 1995
