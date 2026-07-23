"""Tests for `build_site`'s artifact builders.

These use small hand-written tables rather than the parquet fixtures: the
builders are pure table->dict transforms, and the interesting behaviour
(shard pruning, pool scoping, the h2h perspective flip) is easier to pin
down on data whose expected output can be read off by eye.
"""
import pandas as pd
import pytest

from ffs import build_site, metrics


@pytest.fixture
def tables():
    competitions = pd.DataFrame([
        # (weapon, gender) pools: EM has two comps, EF one, FM one.
        {"competition_id": "2024-1", "season": 2024, "tournament_id": 1, "name": "Coupe du Monde",
         "city": "Bern", "country": "Switzerland", "start_date": "2024-03-01", "weapon": "E",
         "gender": "M", "category": "S", "level": "A", "n_entries": 200},
        {"competition_id": "2024-2", "season": 2024, "tournament_id": 2, "name": "Grand Prix",
         "city": "Doha", "country": "Qatar", "start_date": "2024-05-01", "weapon": "E",
         "gender": "M", "category": "S", "level": "GP", "n_entries": 150},
        {"competition_id": "2023-3", "season": 2023, "tournament_id": 3, "name": "Championnats du Monde",
         "city": "Milan", "country": "Italy", "start_date": "2023-07-01", "weapon": "E",
         "gender": "F", "category": "S", "level": "CHM", "n_entries": 120},
        {"competition_id": "2024-4", "season": 2024, "tournament_id": 4, "name": "Coupe du Monde",
         "city": "Paris", "country": "France", "start_date": "2024-02-01", "weapon": "F",
         "gender": "M", "category": "S", "level": "A", "n_entries": 180},
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
         "PIND": 0.83, "TTR": 10.0, "TTD": 15.0, "TMVAVG": 4, "T64+": 1, "TPRE64": 1},
        {"competition_id": "2024-1", "athlete_id": 2, "POS": 2, "Q": 1, "PVICT": 4, "PTR": 15, "PTD": 22,
         "PIND": 0.67, "TTR": 12.0, "TTD": 14.0, "TMVAVG": 3, "T64+": 1, "TPRE64": 1},
        {"competition_id": "2024-2", "athlete_id": 1, "POS": 3, "Q": 1, "PVICT": 4, "PTR": 14, "PTD": 23,
         "PIND": 0.67, "TTR": 11.0, "TTD": 13.0, "TMVAVG": 2, "T64+": 1, "TPRE64": 1},
        {"competition_id": "2024-2", "athlete_id": 2, "POS": 1, "Q": 1, "PVICT": 6, "PTR": 10, "PTD": 30,
         "PIND": 1.0, "TTR": 9.0, "TTD": 15.0, "TMVAVG": 4, "T64+": 1, "TPRE64": 1},
        {"competition_id": "2024-4", "athlete_id": 3, "POS": 5, "Q": 1, "PVICT": 3, "PTR": 18, "PTD": 20,
         "PIND": 0.5, "TTR": 13.0, "TTD": 12.0, "TMVAVG": 1, "T64+": 1, "TPRE64": 1},
    ])
    # The builders read every registry metric; the ones not spelled out above
    # are absent (NaN) -- exactly what an archive gap looks like in real data.
    stats = stats.reindex(columns=["competition_id", "athlete_id", *metrics.METRIC_CODES])
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


def _metric(result_row, code):
    """One metric off a shard's fixed-order `m` array (see build_site)."""
    return result_row["m"][metrics.METRIC_CODES.index(code)]


def _context(tables):
    primary_gender = build_site._athlete_primary_gender(tables["results"], tables["competitions"])
    return build_site.ProfileContext(tables, primary_gender)


def test_fencer_profile_career_results_and_timeline(tables):
    profile = build_site.build_fencer_profile(1, _context(tables))

    assert profile["id"] == 1
    assert profile["name"] == "ALPHA Ann"
    assert profile["birth_year"] == 1990
    assert profile["hand"] == "Right"

    # Athlete 1's 1555.5 is the pool's best peak, so rank 1 of the two profiles.
    assert profile["career"] == [
        {"weapon": "E", "n_comps": 2, "best_rank": 1, "titles": 1, "current_rating": 1555.5,
         "peak_rating": 1555.5, "peak_pool_rank": 1}
    ]

    # Results are newest-first and carry the stats row for that competition,
    # as a registry-ordered array rather than named metric keys.
    assert [r["competition_id"] for r in profile["results"]] == ["2024-2", "2024-1"]
    assert _metric(profile["results"][1], "POS") == 1
    assert _metric(profile["results"][1], "PVICT") == 5
    # A metric with no data for that competition is null, not zero.
    assert _metric(profile["results"][1], "p_tr_std") is None
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


# ------------------------------------------------------- metrics registry

def test_meta_carries_the_metric_registry_and_level_groups(tables):
    meta = build_site.build_meta(tables, bouts_count=987)

    # Registry order is the contract between shards, explorer rows and JS.
    assert [m["code"] for m in meta["metrics"]] == metrics.METRIC_CODES
    assert {m["group"] for m in meta["metrics"]} <= {"overall", "poule", "de"}
    assert {m["agg"] for m in meta["metrics"]} == {"mean", "sum"}
    assert {m["better"] for m in meta["metrics"]} <= {"low", "high", None}
    # Legacy's own aggregation choices, ported verbatim.
    by_code = {m["code"]: m for m in meta["metrics"]}
    assert by_code["POS"]["agg"] == "mean" and by_code["POS"]["better"] == "low"
    assert by_code["T64+"]["agg"] == "sum" and by_code["TPRE64"]["agg"] == "sum"
    # Every metric's denominator names a real counter.
    assert {m["den"] for m in meta["metrics"]} <= set(meta["counts"])

    assert [g["code"] for g in meta["level_groups"]] == build_site.LEVEL_GROUP_CODES
    assert meta["default_level_groups"] == ["WC", "GP"]


def test_level_groups_cover_every_level_in_the_archive_exactly_once():
    seen = [level for _, _, levels in build_site.LEVEL_GROUPS for level in levels]

    assert len(seen) == len(set(seen))
    # Every fie.org level code in the canonical data has a home.
    for level in ["A", "SA", "GP", "CHZ", "NF", "CHM", "OF", "JO"]:
        assert level in build_site.LEVEL_TO_GROUP
    # ...and anything unseen falls to the catch-all rather than vanishing.
    assert "OTH" in build_site.LEVEL_GROUP_CODES
    assert "ZZZ" not in build_site.LEVEL_TO_GROUP


# ------------------------------------------------------------------ explore

def _explore_row(explore, athlete_id, season, level_group):
    lg = explore["level_groups"].index(level_group)
    return next(r for r in explore["rows"] if r[:3] == [athlete_id, season, lg])


def _explore_value(explore, row, code):
    return row[3 + len(explore["counts"]) + explore["metrics"].index(code)]


def _explore_count(explore, row, key):
    return row[3 + explore["counts"].index(key)]


def test_explore_rows_are_keyed_by_athlete_season_and_level_group(tables):
    explore = build_site.build_explore("E", "M", tables, shard_ids={1, 2})

    # 2024-1 is a World Cup, 2024-2 a Grand Prix: two fencers x two groups.
    assert len(explore["rows"]) == 4
    assert {tuple(r[:3]) for r in explore["rows"]} == {
        (1, 2024, explore["level_groups"].index("WC")),
        (1, 2024, explore["level_groups"].index("GP")),
        (2, 2024, explore["level_groups"].index("WC")),
        (2, 2024, explore["level_groups"].index("GP")),
    }
    assert explore["metrics"] == metrics.METRIC_CODES


def test_explore_rows_hold_sums_and_the_counts_needed_to_average_them(tables):
    explore = build_site.build_explore("E", "M", tables, shard_ids={1, 2})

    wc = _explore_row(explore, 1, 2024, "WC")
    gp = _explore_row(explore, 1, 2024, "GP")

    # Sums, not means: one competition each here, so they read off directly.
    assert _explore_value(explore, wc, "PVICT") == 5
    assert _explore_value(explore, gp, "PVICT") == 4
    assert _explore_count(explore, wc, "poule") == 1

    # The client's job: sum over the selected rows, divide by the metric's own
    # denominator. Athlete 1 across both level groups averages 4.5 poule wins.
    total = _explore_value(explore, wc, "PVICT") + _explore_value(explore, gp, "PVICT")
    denominator = _explore_count(explore, wc, "poule") + _explore_count(explore, gp, "poule")
    assert total / denominator == 4.5

    # A metric with no data anywhere is a null sum with a zero count, so the
    # client shows "—" rather than dividing by zero.
    assert _explore_value(explore, wc, "p_tr_std") is None
    assert _explore_count(explore, wc, "pstd") == 0


def test_explore_is_pool_scoped_and_respects_shard_pruning(tables):
    # Athlete 3's only competition is Men's Foil, and they have no shard.
    em = build_site.build_explore("E", "M", tables, shard_ids={1, 2})
    fm = build_site.build_explore("F", "M", tables, shard_ids={1, 2})

    assert all(r[0] != 3 for r in em["rows"])
    assert fm["rows"] == []


# ------------------------------------------------------------------- paths

def test_peak_ratings_rank_within_the_pool(tables):
    peaks = build_site.compute_peak_ratings(tables["ratings_history"], shard_ids={1, 2})

    by_athlete = {int(r.athlete_id): (r.peak, r.rank) for r in peaks.itertuples(index=False)}
    assert by_athlete == {1: (1555.5, 1), 2: (1530.0, 2)}


def test_paths_cohorts_come_from_peak_rating_rank(tables, monkeypatch):
    # Two fencers only, so accept an age bucket of one for the fixture.
    monkeypatch.setattr(build_site, "MIN_COHORT_AGE_SAMPLE", 1)

    paths = build_site.build_paths("E", "M", tables, shard_ids={1, 2})

    # Both fencers rank 1 and 2 on peak rating, so both are in every tier.
    assert paths["tiers"]["top10"]["n_athletes"] == 2
    assert paths["cohort_ids"]["top10"] == [1, 2]
    assert "all" not in paths["cohort_ids"]  # the "all" tier needs no id list

    # Membership really is peak-rank based: narrow the pool to one place and
    # only the higher peak survives.
    monkeypatch.setattr(build_site, "COHORT_TIERS", [("top1", 1), ("all", None)])
    narrowed = build_site.build_paths("E", "M", tables, shard_ids={1, 2})
    assert narrowed["cohort_ids"]["top1"] == [1]
    assert narrowed["tiers"]["all"]["n_athletes"] == 2


def test_paths_series_are_by_age_distributions(tables, monkeypatch):
    monkeypatch.setattr(build_site, "MIN_COHORT_AGE_SAMPLE", 1)

    paths = build_site.build_paths("E", "M", tables, shard_ids={1, 2})
    series = paths["tiers"]["all"]["series"]

    # Athlete 1 (b. 1990) fenced both 2024 competitions at 34; athlete 2 at 29.
    assert set(series["POS"]) == {"34", "29"}
    n, mean, p25, p50, p75 = series["POS"]["34"]
    assert n == 1
    # POS aggregates as a mean within the year: (1 + 3) / 2.
    assert mean == p25 == p50 == p75 == 2

    # T64+ sums within the year instead, per the registry.
    assert series["T64+"]["34"][1] == 2

    # Rating at that age is the last rating of the year, not its average.
    assert series["rating"]["34"][1] == 1555.5
    # Round-entry rates are shares of the year's entries.
    assert series["rate_podium"]["34"][1] == 1.0
    assert series["rate_title"]["34"][1] == 0.5
    assert series["n_comps"]["34"][1] == 2


def test_paths_drops_age_buckets_below_the_sample_floor(tables):
    paths = build_site.build_paths("E", "M", tables, shard_ids={1, 2})

    # Default floor is 3 and the fixture has one fencer per age: nothing to plot.
    assert paths["tiers"]["all"]["series"]["POS"] == {}
