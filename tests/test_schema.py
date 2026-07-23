import pandas as pd

from ffs import schema


def _clean_tables():
    competitions = schema.coerce_dtypes(
        "competitions",
        pd.DataFrame([{"competition_id": "2025-1", "season": 2025, "tournament_id": 1, "name": "Test",
                        "city": None, "country": None, "start_date": None, "weapon": "E", "gender": "M",
                        "category": "S", "level": None, "n_entries": 2}]),
    )
    athletes = schema.coerce_dtypes(
        "athletes",
        pd.DataFrame([
            {"athlete_id": 1, "name": "A", "country": "FRA", "birth_year": None, "hand": None},
            {"athlete_id": 2, "name": "B", "country": "ITA", "birth_year": None, "hand": None},
        ]),
    )
    results = schema.coerce_dtypes(
        "results",
        pd.DataFrame([
            {"competition_id": "2025-1", "athlete_id": 1, "final_rank": 1, "seed": None, "exempt": False, "points": None},
            {"competition_id": "2025-1", "athlete_id": 2, "final_rank": 2, "seed": None, "exempt": False, "points": None},
        ]),
    )
    bouts = schema.coerce_dtypes(
        "bouts",
        pd.DataFrame([
            {"competition_id": "2025-1", "phase": "de", "round": "B2", "poule_no": None, "bout_order": 0,
             "athlete_a": 1, "athlete_b": 2, "score_a": 15, "score_b": 10, "winner": 1, "status": "ok"},
        ]),
    )
    return {"competitions": competitions, "athletes": athletes, "results": results, "bouts": bouts}


def test_empty_table_has_expected_columns():
    for name, dtypes in schema.TABLE_DTYPES.items():
        empty = schema.empty_table(name)
        assert list(empty.columns) == list(dtypes)
        assert len(empty) == 0


def test_validate_tables_clean_data_has_no_issues():
    assert schema.validate_tables(_clean_tables()) == []


def test_validate_tables_flags_unknown_bout_athlete():
    tables = _clean_tables()
    tables["bouts"].loc[0, "athlete_a"] = 999
    issues = schema.validate_tables(tables)
    assert any("not present in athletes table" in i for i in issues)


def test_validate_tables_flags_bad_winner():
    tables = _clean_tables()
    tables["bouts"].loc[0, "winner"] = 999
    issues = schema.validate_tables(tables)
    assert any("winner is neither athlete_a nor athlete_b" in i for i in issues)


def test_validate_tables_flags_self_bout():
    tables = _clean_tables()
    tables["bouts"].loc[0, "athlete_b"] = tables["bouts"].loc[0, "athlete_a"]
    issues = schema.validate_tables(tables)
    assert any("athlete_a == athlete_b" in i for i in issues)


def test_validate_tables_flags_negative_score():
    tables = _clean_tables()
    tables["bouts"].loc[0, "score_a"] = -1
    issues = schema.validate_tables(tables)
    assert any("negative score" in i for i in issues)


def test_validate_tables_flags_bad_final_rank():
    tables = _clean_tables()
    tables["results"].loc[0, "final_rank"] = 0
    issues = schema.validate_tables(tables)
    assert any("final_rank < 1" in i for i in issues)


def test_clean_final_rank_nulls_sentinels_only():
    results = schema.coerce_dtypes(
        "results",
        pd.DataFrame([
            {"competition_id": "2025-1", "athlete_id": 1, "final_rank": 1,
             "seed": None, "exempt": False, "points": 0.0},
            {"competition_id": "2025-1", "athlete_id": 2, "final_rank": 369,
             "seed": None, "exempt": False, "points": 0.0},
            {"competition_id": "2025-1", "athlete_id": 3, "final_rank": 999,
             "seed": None, "exempt": False, "points": 0.0},
            {"competition_id": "2025-1", "athlete_id": 4, "final_rank": 9999,
             "seed": None, "exempt": False, "points": 0.0},
        ]),
    )
    cleaned = schema.clean_final_rank(results)
    assert cleaned["final_rank"].tolist()[:2] == [1, 369]
    assert cleaned["final_rank"].isna().tolist() == [False, False, True, True]
    # The input frame is left alone -- callers pass canonical tables around.
    assert results["final_rank"].notna().all()
