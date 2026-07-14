"""Tests for `validate_legacy` against the real committed legacy CSV
(`data/legacy/updated_results.csv`) -- pure logic, no network."""
from pathlib import Path

import pandas as pd

from ffs.validate_legacy import load_legacy_competitions, match_competitions, normalize_name

LEGACY_CSV = Path(__file__).parent.parent / "data" / "legacy" / "updated_results.csv"


def test_normalize_name():
    assert normalize_name("Éric O'Brien-Smith") == "ERIC O BRIEN SMITH"
    assert normalize_name("  extra   spaces  ") == "EXTRA SPACES"
    assert normalize_name(None) == ""
    assert normalize_name("") == ""


def test_load_legacy_competitions_row_count():
    comps = load_legacy_competitions(LEGACY_CSV)
    # documented in PLAN.md's M3b progress notes: 286 distinct
    # (comp, place, date, weapon, gender) competition-events.
    assert len(comps) == 286
    assert set(comps.columns) == {"comp", "place", "date", "weapon", "gender", "n_entries"}
    assert (comps["n_entries"] > 0).all()


def test_match_competitions_exact_date_and_weapon_gender():
    legacy_comps = pd.DataFrame(
        [{"comp": "Test Open", "place": "Testville", "date": pd.Timestamp("2020-01-15").date(),
          "weapon": "E", "gender": "M", "n_entries": 10}]
    )
    canonical = pd.DataFrame(
        [{"competition_id": "2020-1", "start_date": "2020-01-15", "weapon": "E", "gender": "M"}]
    )
    matches = match_competitions(legacy_comps, canonical)
    assert len(matches) == 1
    assert matches[0]["competition_id"] == "2020-1"


def test_match_competitions_within_tolerance():
    legacy_comps = pd.DataFrame(
        [{"comp": "Test Open", "place": "Testville", "date": pd.Timestamp("2020-01-15").date(),
          "weapon": "E", "gender": "M", "n_entries": 10}]
    )
    canonical = pd.DataFrame(
        [{"competition_id": "2020-1", "start_date": "2020-01-16", "weapon": "E", "gender": "M"}]
    )
    matches = match_competitions(legacy_comps, canonical)
    assert matches[0]["competition_id"] == "2020-1"


def test_match_competitions_no_match_outside_tolerance_or_wrong_weapon():
    legacy_comps = pd.DataFrame(
        [
            {"comp": "Too Far", "place": "X", "date": pd.Timestamp("2020-01-15").date(),
             "weapon": "E", "gender": "M", "n_entries": 10},
            {"comp": "Wrong Weapon", "place": "X", "date": pd.Timestamp("2020-01-15").date(),
             "weapon": "F", "gender": "M", "n_entries": 10},
        ]
    )
    canonical = pd.DataFrame(
        [{"competition_id": "2020-1", "start_date": "2020-01-20", "weapon": "E", "gender": "M"}]
    )
    matches = match_competitions(legacy_comps, canonical)
    assert all(m["competition_id"] is None for m in matches)
