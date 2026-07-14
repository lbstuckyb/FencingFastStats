"""Parse decoded fie.org query bodies for one competition into the four
canonical LONG-format tables defined in `schema.py`.

Input shapes (verified live against `fie.org/competitions/2025/242` on
2026-07-14 — see `tests/fixtures/`):

- `("competitions", comp_id, season)` -> competition info dict.
- `("competitions", "results", "pools", comp_id, season)` -> `{"pools": [...]}`,
  each pool has `rows` (one per fencer, ordered by seed) with a `matches`
  array indexed by opponent's row position (self = null).
- `("competitions", "pool", "results", comp_id, season)` -> `{"rows": [...]}`,
  post-poule ranking (victory/td/tr/rank/qualified) — used only to detect
  `exempt` (fencers in the final results but absent here skipped poules).
- `("competitions", "results", "tableau", comp_id, season)` -> `{"tableau":
  [{"suiteTableId", "rounds": {round_code: [bout, ...]}}]}`.
- Final ranking list (rank, points, fencer) comes from
  `FieClient.fetch_results_ranking`, not from the SSR payload (see
  `fie_client.py` docstring) — passed in separately as `ranking_items`.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from ffs import schema

QueryMap = dict[tuple, Any]


def _birth_year(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        return int(date_str[:4])
    except ValueError:
        return None


def parse_competition(
    season: int,
    comp_id: int,
    tournament_id: int,
    queries: QueryMap,
    ranking_items: list[dict],
) -> dict[str, pd.DataFrame]:
    competition_id = f"{season}-{comp_id}"
    info = queries[("competitions", comp_id, season)]

    competitions_df = schema.coerce_dtypes(
        "competitions",
        pd.DataFrame(
            [
                {
                    "competition_id": competition_id,
                    "season": season,
                    "tournament_id": tournament_id,
                    "name": info.get("name"),
                    "city": info.get("location"),
                    "country": info.get("country"),
                    "start_date": info.get("startDate"),
                    "weapon": info.get("weapon"),
                    "gender": info.get("gender"),
                    "category": info.get("category"),
                    "level": info.get("competitionCategory"),
                    "n_entries": info.get("entriesCount"),
                }
            ]
        ),
    )

    athletes_rows: dict[int, dict] = {}

    def _upsert_athlete(athlete_id: int | None, **fields: Any) -> None:
        if athlete_id is None:
            return
        row = athletes_rows.setdefault(athlete_id, {"athlete_id": athlete_id})
        for key, value in fields.items():
            if value is not None and not row.get(key):
                row[key] = value

    pools_body = queries.get(("competitions", "results", "pools", comp_id, season), {})
    pools = pools_body.get("pools", [])
    for pool in pools:
        for row in pool["rows"]:
            _upsert_athlete(row["fencerId"], name=row["name"], country=row["nationality"])

    pool_results_body = queries.get(("competitions", "pool", "results", comp_id, season), {})
    pool_result_rows = pool_results_body.get("rows", [])
    pool_result_ids = set()
    for row in pool_result_rows:
        pool_result_ids.add(row["fencerId"])
        _upsert_athlete(row["fencerId"], name=row["name"], country=row["nationality"])

    tableau_body = queries.get(("competitions", "results", "tableau", comp_id, season), {})
    tableau = tableau_body.get("tableau", [])
    for suite in tableau:
        for bouts in suite["rounds"].values():
            for bout in bouts:
                for side in (bout["fencer1"], bout["fencer2"]):
                    if side.get("id") is not None:
                        _upsert_athlete(side["id"], name=side["name"], country=side["nationality"])

    results_rows = []
    for item in ranking_items:
        fencer = item["fencer"]
        _upsert_athlete(
            fencer["id"],
            name=fencer.get("name"),
            country=fencer.get("countryCode"),
            birth_year=_birth_year(fencer.get("date")),
        )
        results_rows.append(
            {
                "competition_id": competition_id,
                "athlete_id": fencer["id"],
                "final_rank": item.get("rank"),
                "seed": None,
                "exempt": fencer["id"] not in pool_result_ids,
                "points": item.get("points"),
            }
        )
    results_df = schema.coerce_dtypes("results", pd.DataFrame(results_rows))

    athletes_df = schema.coerce_dtypes(
        "athletes",
        pd.DataFrame(list(athletes_rows.values())) if athletes_rows else schema.empty_table("athletes"),
    )

    bout_rows: list[dict] = []

    for pool in pools:
        poule_no = pool["poolId"]
        rows = pool["rows"]
        seed_position = {row["fencerId"]: i + 1 for i, row in enumerate(rows)}
        n = len(rows)
        for i in range(n):
            for j in range(i + 1, n):
                fencer_i, fencer_j = rows[i]["fencerId"], rows[j]["fencerId"]
                match_i = rows[i]["matches"][j]
                match_j = rows[j]["matches"][i]
                if match_i is None or match_j is None:
                    continue

                if fencer_i < fencer_j:
                    athlete_a, athlete_b = fencer_i, fencer_j
                    match_a, match_b = match_i, match_j
                else:
                    athlete_a, athlete_b = fencer_j, fencer_i
                    match_a, match_b = match_j, match_i

                score_a, score_b = match_a.get("score"), match_b.get("score")
                if score_a is None or score_b is None:
                    status = "forfeit"
                    winner = None
                else:
                    status = "ok"
                    winner = athlete_a if match_a.get("v") else athlete_b

                bout_rows.append(
                    {
                        "competition_id": competition_id,
                        "phase": "poule",
                        "round": "poule",
                        "poule_no": poule_no,
                        "bout_order": seed_position[athlete_b],
                        "athlete_a": athlete_a,
                        "athlete_b": athlete_b,
                        "score_a": score_a,
                        "score_b": score_b,
                        "winner": winner,
                        "status": status,
                    }
                )

    for suite in tableau:
        for round_code, bouts in suite["rounds"].items():
            for order, bout in enumerate(bouts):
                f1, f2 = bout["fencer1"], bout["fencer2"]
                is_bye = bool(bout.get("isBye")) or f2.get("id") is None or f1.get("id") is None
                if is_bye:
                    real = f1 if f1.get("id") is not None else f2
                    bout_rows.append(
                        {
                            "competition_id": competition_id,
                            "phase": "de",
                            "round": round_code,
                            "poule_no": None,
                            "bout_order": order,
                            "athlete_a": real.get("id"),
                            "athlete_b": None,
                            "score_a": real.get("score"),
                            "score_b": None,
                            "winner": real.get("id"),
                            "status": "bye",
                        }
                    )
                    continue

                id1, id2 = f1["id"], f2["id"]
                if id1 < id2:
                    athlete_a, athlete_b = id1, id2
                    side_a, side_b = f1, f2
                else:
                    athlete_a, athlete_b = id2, id1
                    side_a, side_b = f2, f1

                is_forfeit = side_a.get("status") == "E" or side_b.get("status") == "E"
                winner = id1 if f1.get("isWinner") else id2
                bout_rows.append(
                    {
                        "competition_id": competition_id,
                        "phase": "de",
                        "round": round_code,
                        "poule_no": None,
                        "bout_order": order,
                        "athlete_a": athlete_a,
                        "athlete_b": athlete_b,
                        "score_a": side_a.get("score"),
                        "score_b": side_b.get("score"),
                        "winner": winner,
                        "status": "forfeit" if is_forfeit else "ok",
                    }
                )

    bouts_df = schema.coerce_dtypes(
        "bouts", pd.DataFrame(bout_rows) if bout_rows else schema.empty_table("bouts")
    )

    return {
        "competitions": competitions_df,
        "athletes": athletes_df,
        "results": results_df,
        "bouts": bouts_df,
    }
