"""Canonical LONG-format table schemas for parsed FIE competition data.

Four tables per competition, joined by `competition_id` (`"{season}-{comp_id}"`):

- `competitions` — one row per competition.
- `athletes` — one row per athlete (deduplicated across competitions by caller).
- `results` — one row per (competition_id, athlete_id): final ranking.
- `bouts` — one row per bout, phase `'poule'` or `'de'`.

Bout `round`/`poule_no`/`bout_order` convention (a documented interpretation,
not literally specified by any FIE API contract — flag in methodology.md if
older seasons don't fit):

- `phase='poule'`: `round='poule'`, `poule_no` = 1-indexed pool number,
  `bout_order` = opponent's 1-indexed seed position within the pool (matches
  legacy's p1..p6 columns, needed for PM1V% / PM1&2V%).
- `phase='de'`: `round` = FIE's own tableau round code (e.g. `'A256'`,
  `'B64'`, `'B2'` for the final), `poule_no=None`, `bout_order` = 0-indexed
  bracket slot position within that round (for reproducibility; not a
  legacy-parity field).

`status`: `'ok'` | `'forfeit'` (FIE status `'E'`/`'EXC'` — excused/withdrawal)
| `'bye'`. Only `'ok'` bouts should feed the stats engine (M4), mirroring
legacy's drop of "D with tr=0" no-show rows.
"""
from __future__ import annotations

import pandas as pd

COMPETITIONS_DTYPES: dict[str, str] = {
    "competition_id": "string",
    "season": "Int64",
    "tournament_id": "Int64",
    "name": "string",
    "city": "string",
    "country": "string",
    "start_date": "string",
    "weapon": "string",
    "gender": "string",
    "category": "string",
    "level": "string",
    "n_entries": "Int64",
}

ATHLETES_DTYPES: dict[str, str] = {
    "athlete_id": "Int64",
    "name": "string",
    "country": "string",
    "birth_year": "Int64",
    "hand": "string",
}

RESULTS_DTYPES: dict[str, str] = {
    "competition_id": "string",
    "athlete_id": "Int64",
    "final_rank": "Int64",
    "seed": "Int64",
    "exempt": "boolean",
    "points": "Float64",
}

BOUTS_DTYPES: dict[str, str] = {
    "competition_id": "string",
    "phase": "string",
    "round": "string",
    "poule_no": "Int64",
    "bout_order": "Int64",
    "athlete_a": "Int64",
    "athlete_b": "Int64",
    "score_a": "Int64",
    "score_b": "Int64",
    "winner": "Int64",
    "status": "string",
}

TABLE_DTYPES = {
    "competitions": COMPETITIONS_DTYPES,
    "athletes": ATHLETES_DTYPES,
    "results": RESULTS_DTYPES,
    "bouts": BOUTS_DTYPES,
}


def empty_table(name: str) -> pd.DataFrame:
    dtypes = TABLE_DTYPES[name]
    return pd.DataFrame({col: pd.Series(dtype=dt) for col, dt in dtypes.items()})


def coerce_dtypes(name: str, df: pd.DataFrame) -> pd.DataFrame:
    dtypes = TABLE_DTYPES[name]
    df = df.reindex(columns=list(dtypes))
    return df.astype(dtypes)


def validate_tables(tables: dict[str, pd.DataFrame]) -> list[str]:
    """Check structural invariants across the four canonical tables.
    Returns a list of human-readable problems; empty means clean.
    """
    issues: list[str] = []
    competitions = tables.get("competitions", pd.DataFrame())
    athletes = tables.get("athletes", pd.DataFrame())
    results = tables.get("results", pd.DataFrame())
    bouts = tables.get("bouts", pd.DataFrame())

    for name, df in tables.items():
        expected = set(TABLE_DTYPES[name])
        missing = expected - set(df.columns)
        if missing:
            issues.append(f"{name}: missing columns {sorted(missing)}")

    known_athlete_ids = set(athletes["athlete_id"].dropna()) if "athlete_id" in athletes else set()
    known_comp_ids = set(competitions["competition_id"].dropna()) if "competition_id" in competitions else set()

    if "athlete_id" in results.columns:
        unknown = set(results["athlete_id"].dropna()) - known_athlete_ids
        if unknown:
            issues.append(f"results: {len(unknown)} athlete_id(s) not present in athletes table")
    if "competition_id" in results.columns:
        unknown = set(results["competition_id"].dropna()) - known_comp_ids
        if unknown:
            issues.append(f"results: {len(unknown)} competition_id(s) not present in competitions table")

    if "competition_id" in bouts.columns:
        unknown = set(bouts["competition_id"].dropna()) - known_comp_ids
        if unknown:
            issues.append(f"bouts: {len(unknown)} competition_id(s) not present in competitions table")

    if not bouts.empty:
        bout_athlete_ids = set(bouts["athlete_a"].dropna()) | set(bouts["athlete_b"].dropna())
        unknown = bout_athlete_ids - known_athlete_ids
        if unknown:
            issues.append(f"bouts: {len(unknown)} athlete_id(s) not present in athletes table")

        for comp_id, group in bouts.groupby("competition_id"):
            result_ids = set(results.loc[results["competition_id"] == comp_id, "athlete_id"])
            bout_ids = set(group["athlete_a"].dropna()) | set(group["athlete_b"].dropna())
            missing_from_results = bout_ids - result_ids
            if missing_from_results:
                issues.append(
                    f"bouts: competition {comp_id} has {len(missing_from_results)} "
                    "bout athlete(s) missing from results"
                )

        same_athlete = bouts["athlete_a"] == bouts["athlete_b"]
        if same_athlete.any():
            issues.append(f"bouts: {int(same_athlete.sum())} row(s) with athlete_a == athlete_b")

        ok_bouts = bouts[bouts["status"] == "ok"]
        bad_scores = ok_bouts[(ok_bouts["score_a"] < 0) | (ok_bouts["score_b"] < 0)]
        if not bad_scores.empty:
            issues.append(f"bouts: {len(bad_scores)} 'ok' row(s) with a negative score")

        # winner must equal athlete_a or athlete_b on the same row
        mismatched = ok_bouts[(ok_bouts["winner"] != ok_bouts["athlete_a"]) & (ok_bouts["winner"] != ok_bouts["athlete_b"])]
        if not mismatched.empty:
            issues.append(f"bouts: {len(mismatched)} 'ok' row(s) where winner is neither athlete_a nor athlete_b")

    if not results.empty and "final_rank" in results.columns:
        bad_rank = results[results["final_rank"] < 1]
        if not bad_rank.empty:
            issues.append(f"results: {len(bad_rank)} row(s) with final_rank < 1")

    return issues
