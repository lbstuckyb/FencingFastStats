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


@pytest.fixture
def bouts():
    """2024-1: one three-fencer poule whose fie.org row order is [2, 3, 1]
    (so `bout_order`, the row position of the *larger* id in each pair, is 1
    for fencer 2 and 2 for fencer 3, leaving position 3 for fencer 1), plus a
    two-round tableau deliberately listed out of order."""
    return pd.DataFrame([
        {"competition_id": "2024-1", "phase": "de", "round": "B2", "poule_no": None, "bout_order": 0,
         "athlete_a": 1, "athlete_b": 2, "score_a": 15, "score_b": 12, "winner": 1, "status": "ok"},
        {"competition_id": "2024-1", "phase": "poule", "round": "poule", "poule_no": 1, "bout_order": 1,
         "athlete_a": 1, "athlete_b": 2, "score_a": 5, "score_b": 3, "winner": 1, "status": "ok"},
        {"competition_id": "2024-1", "phase": "poule", "round": "poule", "poule_no": 1, "bout_order": 2,
         "athlete_a": 1, "athlete_b": 3, "score_a": 2, "score_b": 5, "winner": 3, "status": "ok"},
        {"competition_id": "2024-1", "phase": "poule", "round": "poule", "poule_no": 1, "bout_order": 2,
         "athlete_a": 2, "athlete_b": 3, "score_a": 0, "score_b": 0, "winner": 2, "status": "forfeit"},
        {"competition_id": "2024-1", "phase": "de", "round": "A4", "poule_no": None, "bout_order": 0,
         "athlete_a": 1, "athlete_b": None, "score_a": None, "score_b": None, "winner": 1, "status": "bye"},
        {"competition_id": "2024-1", "phase": "de", "round": "A4", "poule_no": None, "bout_order": 1,
         "athlete_a": 2, "athlete_b": 3, "score_a": 15, "score_b": 9, "winner": 2, "status": "ok"},
    ])


@pytest.fixture
def h2h_bouts():
    return pd.DataFrame([
        {"competition_id": "2024-1", "weapon": "E", "gender": "M", "phase": "poule", "round": "poule",
         "start_date": "2024-03-01", "athlete_lo": 1, "athlete_hi": 2, "score_lo": 5, "score_hi": 3,
         "winner": 1, "status": "ok"},
        {"competition_id": "2024-2", "weapon": "E", "gender": "M", "phase": "de", "round": "B2",
         "start_date": "2024-05-01", "athlete_lo": 1, "athlete_hi": 2, "score_lo": 12, "score_hi": 15,
         "winner": 2, "status": "ok"},
    ])


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


def test_h2h_all_lists_every_meeting_but_only_profiled_opponents(tables):
    primary_gender = build_site._athlete_primary_gender(tables["results"], tables["competitions"])

    # Athlete 3 has no shard, so the (1, 3) meeting is dropped from the list --
    # the explorer can only pick opponents that have a profile.
    pruned = build_site.build_fencer_profile(
        1, build_site.ProfileContext(tables, primary_gender, shard_ids={1, 2})
    )
    assert pruned["h2h_all"] == [[2, "E", 5, 3, "2024-05-01"]]

    # Unpruned, the single meeting with athlete 3 is there: `h2h_all` is not
    # subject to the >=3 bout floor that `top_rivals` applies.
    everyone = build_site.build_fencer_profile(
        1, build_site.ProfileContext(tables, primary_gender)
    )
    assert [row[0] for row in everyone["h2h_all"]] == [2, 3]
    assert everyone["h2h_all"][1] == [3, "E", 1, 1, "2024-03-01"]


# ---------------------------------------------------------------- competitions

def test_round_sort_key_orders_a_tableau_before_the_b_tableau():
    codes = ["B2", "A64", "B64", "A256", "B32", "A128"]

    assert sorted(codes, key=build_site._round_sort_key) == [
        "A256", "A128", "A64", "B64", "B32", "B2"
    ]
    # Older conventions: `pre*` counts down, `PD*` and bare numbers are their
    # own scheme, and every preliminary code still sorts before the main draw.
    assert sorted(["A16", "pre4", "pre8"], key=build_site._round_sort_key) == ["pre8", "pre4", "A16"]
    assert sorted(["PD2", "PD1"], key=build_site._round_sort_key) == ["PD1", "PD2"]
    assert sorted(["1", "6", "3"], key=build_site._round_sort_key) == ["6", "3", "1"]


def test_poule_roster_recovers_fie_row_order(bouts):
    poule = bouts[bouts["phase"] == "poule"]

    # Positions come from `bout_order` (the row of the larger id in each pair);
    # fencer 1, the lowest id, is placed in the one row left over.
    assert build_site._poule_roster(poule) == [2, 3, 1]


def test_competitions_index_is_newest_first_with_the_champion(tables):
    index = build_site.build_competitions_index(tables)

    assert [c["id"] for c in index] == ["2024-2", "2024-1", "2024-4", "2023-3"]
    first = index[0]
    assert (first["n"], first["ci"], first["w"], first["g"], first["e"]) == (
        "Grand Prix", "Doha", "E", "M", 150
    )
    assert first["c"] == [2, "BETA Bob"]
    # No fencer finished first in 2024-4's recorded results.
    assert next(c for c in index if c["id"] == "2024-4")["c"] is None


def test_competition_detail_grids_poules_and_orders_the_tableau(tables, bouts):
    ctx = build_site.CompetitionContext(tables, bouts)

    detail = build_site.build_competition_detail("2024-1", ctx)

    assert detail["name"] == "Coupe du Monde"
    assert detail["n_entries"] == 200
    assert detail["athletes"]["1"] == ["ALPHA Ann", "FRA"]
    assert [r["a"] for r in detail["results"]] == [1, 2]
    assert detail["results"][0] == {"a": 1, "r": 1, "s": 3, "p": 32.0}

    poule = detail["poules"][0]
    assert poule["no"] == 1
    assert poule["fencers"] == [2, 3, 1]
    # Bouts reference roster *positions*, not athlete ids: fencer 1 (slot 2)
    # beat fencer 2 (slot 0) 5-3, and the 0-0 no-show keeps its winner.
    assert [2, 0, 5, 3, "ok", 2] in poule["bouts"]
    assert [0, 1, 0, 0, "forfeit", 0] in poule["bouts"]

    # A-tableau before B-tableau, byes kept with a null opponent.
    assert [r["round"] for r in detail["de"]] == ["A4", "B2"]
    assert detail["de"][0]["bouts"][0] == [1, None, None, None, 1, "bye"]
    assert detail["de"][1]["bouts"] == [[1, 2, 15, 12, 1, "ok"]]


def test_competition_detail_of_a_results_only_competition(tables, bouts):
    ctx = build_site.CompetitionContext(tables, bouts)

    detail = build_site.build_competition_detail("2023-3", ctx)

    # No bouts in the archive for this one -- empty sections, not an error.
    assert detail["poules"] == [] and detail["de"] == []
    assert detail["results"] == []


# ------------------------------------------------------------------------ h2h

def test_h2h_pair_file_is_oriented_on_the_lower_athlete_id(tables, h2h_bouts):
    athletes_idx = tables["athletes"].set_index("athlete_id")
    competitions_idx = tables["competitions"].set_index("competition_id")

    pair = build_site.build_h2h_pair(tables["h2h"].iloc[:1], h2h_bouts, athletes_idx, competitions_idx)

    assert pair["a"] == {"id": 1, "name": "ALPHA Ann", "country": "FRA"}
    assert pair["b"]["id"] == 2
    assert pair["totals"] == {"bouts": 5, "wins_a": 3, "wins_b": 2, "last_met": "2024-05-01"}
    assert pair["pools"][0]["weapon"] == "E" and pair["pools"][0]["td_a"] == 60
    # Bouts are newest first and carry the competition's name for the link.
    assert [b["date"] for b in pair["bouts"]] == ["2024-05-01", "2024-03-01"]
    assert pair["bouts"][0]["competition"] == "Grand Prix"
    assert (pair["bouts"][0]["score_a"], pair["bouts"][0]["score_b"]) == (12, 15)


def test_write_json_turns_missing_nullable_values_into_null(tmp_path):
    path = tmp_path / "out.json"

    size = build_site._write_json(path, {"city": pd.NA, "date": pd.NaT, "n": 1})

    assert path.read_text() == '{"city":null,"date":null,"n":1}'
    assert size == len(path.read_text())
