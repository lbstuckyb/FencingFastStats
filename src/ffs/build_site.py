"""Builds `site/data/*.json` artifacts from `data/canonical/*.parquet` for
the static site (`ffs build-site` CLI command).

Output layout (all paths relative to `site/data/`):

- `meta.json` — season range, table row counts, weapon/gender codes.
- `fencers/index.json` — client-side search index: one entry per athlete
  who has a profile shard (see below). Kept to short keys (`i/n/c/w/g`) to
  stay well under the 1.5 MB eager-file guardrail.
- `summary/{weapon}{gender}.json` (6 files, e.g. `ef.json` = Epee/Female) —
  feeds the Home page: ELO top-200, recent competitions, titles/podiums
  leaderboards, all scoped to that (weapon, gender) pool. `{weapon}{gender}`
  (not the plan's literal `me/mf/we/wf/se/sf` list, which double-books `w`
  between "women" and "weapon") avoids ambiguity: weapon is always `e/f/s`,
  gender always `m/f`, so all 6 codes are unambiguous two-letter pairs.
- `fencers/{id % 100}/{id}.json` — full profile: career summary per weapon,
  every competition result + stats row, rating timeline (for the profile's
  rating chart), and a top-10 rivals list (>=3 head-to-head bouts).

Per the plan's size guardrail ("prune per-fencer shards to athletes with
>=2 comps"), athletes with exactly one competition result get no shard —
and are excluded from the search index too, so search never links to a
missing profile.

Competition browser/detail artifacts (`competitions/index.json`,
`competitions/{id}.json`, poule grids, DE brackets) are explicitly M6 scope
per `PLAN.md` and are not built here.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pandas as pd

CANONICAL_DIR = Path("data/canonical")
SITE_DATA_DIR = Path("site/data")

WEAPONS = ["E", "F", "S"]
GENDERS = ["M", "F"]

MIN_COMPS_FOR_SHARD = 2
MIN_H2H_BOUTS_FOR_SUMMARY = 3
TOP_N_ELO = 200
TOP_N_LEADERBOARD = 50
RECENT_N_COMPS = 20
TOP_N_RIVALS = 10

EAGER_SIZE_WARN_BYTES = 1_500_000


def _write_json(path: Path, obj) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, separators=(",", ":"))
    path.write_text(text)
    return len(text.encode("utf-8"))


def _load_tables() -> dict[str, pd.DataFrame]:
    names = [
        "competitions", "athletes", "results", "stats_fencer_comp",
        "ratings_history", "h2h",
    ]
    return {name: pd.read_parquet(CANONICAL_DIR / f"{name}.parquet") for name in names}


def _athlete_primary_gender(results: pd.DataFrame, competitions: pd.DataFrame) -> pd.Series:
    """Each athlete's most-common competition gender (senior individual
    fencers essentially never cross gender pools, but the odd archive
    artifact is possible -- take the mode rather than assuming)."""
    merged = results[["athlete_id", "competition_id"]].merge(
        competitions[["competition_id", "gender"]], on="competition_id", how="left"
    )
    return merged.groupby("athlete_id")["gender"].agg(lambda s: Counter(s.dropna()).most_common(1)[0][0])


def build_meta(tables: dict[str, pd.DataFrame], bouts_count: int) -> dict:
    competitions = tables["competitions"]
    seasons = competitions["season"].dropna()
    return {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "season_min": int(seasons.min()),
        "season_max": int(seasons.max()),
        "n_competitions": int(len(competitions)),
        "n_athletes": int(len(tables["athletes"])),
        "n_bouts": bouts_count,
        "weapons": WEAPONS,
        "genders": GENDERS,
    }


def build_fencer_index(
    results: pd.DataFrame, competitions: pd.DataFrame, athletes: pd.DataFrame
) -> tuple[list[dict], set[int]]:
    counts = results.groupby("athlete_id").size()
    shard_ids = set(counts[counts >= MIN_COMPS_FOR_SHARD].index)

    merged = results[["athlete_id", "competition_id"]].merge(
        competitions[["competition_id", "weapon"]], on="competition_id", how="left"
    )
    weapons_by_athlete = merged.groupby("athlete_id")["weapon"].agg(
        lambda s: "".join(sorted(set(s.dropna())))
    )
    genders_by_athlete = _athlete_primary_gender(results, competitions)

    entries = []
    for row in athletes.itertuples(index=False):
        if row.athlete_id not in shard_ids:
            continue
        entries.append({
            "i": int(row.athlete_id),
            "n": row.name,
            "c": row.country,
            "w": weapons_by_athlete.get(row.athlete_id, ""),
            "g": genders_by_athlete.get(row.athlete_id),
        })
    entries.sort(key=lambda e: e["n"] or "")
    return entries, shard_ids


def build_summary(
    weapon: str,
    gender: str,
    tables: dict[str, pd.DataFrame],
) -> dict:
    competitions = tables["competitions"]
    athletes = tables["athletes"].set_index("athlete_id")
    results = tables["results"]
    stats_df = tables["stats_fencer_comp"]
    ratings_history = tables["ratings_history"]

    pool_comps = competitions[(competitions["weapon"] == weapon) & (competitions["gender"] == gender)]
    pool_comp_ids = set(pool_comps["competition_id"])

    # --- ELO top N (current rating = latest `post` per athlete in this pool) ---
    pool_ratings = ratings_history[(ratings_history["weapon"] == weapon) & (ratings_history["gender"] == gender)]
    pool_ratings = pool_ratings.merge(
        competitions[["competition_id", "start_date"]], on="competition_id", how="left"
    ).sort_values("start_date")
    latest = pool_ratings.groupby("athlete_id", as_index=False).last()
    latest = latest.sort_values("post", ascending=False).head(TOP_N_ELO)
    elo_top = [
        {
            "id": int(r.athlete_id),
            "name": athletes.at[r.athlete_id, "name"] if r.athlete_id in athletes.index else None,
            "country": athletes.at[r.athlete_id, "country"] if r.athlete_id in athletes.index else None,
            "rating": round(float(r.post), 1),
        }
        for r in latest.itertuples(index=False)
    ]

    # --- Recent competitions (with champion) ---
    recent = pool_comps.sort_values("start_date", ascending=False).head(RECENT_N_COMPS)
    champions = results[(results["competition_id"].isin(pool_comp_ids)) & (results["final_rank"] == 1)]
    champ_by_comp = dict(zip(champions["competition_id"], champions["athlete_id"]))
    recent_competitions = []
    for r in recent.itertuples(index=False):
        champ_id = champ_by_comp.get(r.competition_id)
        recent_competitions.append({
            "id": r.competition_id,
            "name": r.name,
            "city": r.city,
            "country": r.country,
            "date": r.start_date,
            "n_entries": int(r.n_entries) if pd.notna(r.n_entries) else None,
            "champion": {
                "id": int(champ_id),
                "name": athletes.at[champ_id, "name"] if champ_id in athletes.index else None,
            } if champ_id is not None and pd.notna(champ_id) else None,
        })

    # --- Leaderboards: titles (POS==1) and podiums (POS<=3), pool-scoped ---
    pool_stats = stats_df[stats_df["competition_id"].isin(pool_comp_ids)]
    titles = pool_stats[pool_stats["POS"] == 1].groupby("athlete_id").size()
    podiums = pool_stats[pool_stats["POS"] <= 3].groupby("athlete_id").size()

    def _leaderboard(counts: pd.Series) -> list[dict]:
        top = counts.sort_values(ascending=False).head(TOP_N_LEADERBOARD)
        return [
            {
                "id": int(athlete_id),
                "name": athletes.at[athlete_id, "name"] if athlete_id in athletes.index else None,
                "country": athletes.at[athlete_id, "country"] if athlete_id in athletes.index else None,
                "count": int(count),
            }
            for athlete_id, count in top.items()
        ]

    return {
        "weapon": weapon,
        "gender": gender,
        "elo_top": elo_top,
        "recent_competitions": recent_competitions,
        "leaderboards": {
            "titles": _leaderboard(titles),
            "podiums": _leaderboard(podiums),
        },
    }


STATS_PROFILE_COLS = [
    "POS", "Q", "PVICT", "PTR", "PTD", "PIND", "TTR", "TTD", "TMVAVG", "T64+", "T96+",
]


def _group_dict(df: pd.DataFrame, key: str) -> dict:
    """One pass of `groupby` turned into a dict for O(1) per-athlete lookup
    (the naive per-athlete boolean-mask filter over full-size tables is
    O(n_athletes * n_rows) and takes tens of minutes over the full dataset;
    this is O(n_rows) total)."""
    return {k: g for k, g in df.groupby(key)}


def _h2h_by_athlete(h2h_df: pd.DataFrame) -> dict:
    cols = ["athlete_id", "opponent_id", "weapon", "gender", "bouts", "wins", "last_met"]
    a = h2h_df.rename(columns={"athlete_lo": "athlete_id", "athlete_hi": "opponent_id", "wins_lo": "wins"})[cols]
    b = h2h_df.rename(columns={"athlete_hi": "athlete_id", "athlete_lo": "opponent_id", "wins_hi": "wins"})[cols]
    combined = pd.concat([a, b], ignore_index=True)
    combined["losses"] = combined["bouts"] - combined["wins"]
    return _group_dict(combined, "athlete_id")


class ProfileContext:
    """Pre-grouped lookups so `build_fencer_profile` never re-scans a
    full-size table -- built once in `build_site()`, reused per athlete."""

    def __init__(self, tables: dict[str, pd.DataFrame], primary_gender_by_athlete: pd.Series):
        self.athletes_idx = tables["athletes"].set_index("athlete_id")
        self.competitions_idx = tables["competitions"].set_index("competition_id")
        self.results_by_athlete = _group_dict(tables["results"], "athlete_id")
        self.stats_by_athlete = _group_dict(tables["stats_fencer_comp"], "athlete_id")
        self.ratings_by_athlete = _group_dict(tables["ratings_history"], "athlete_id")
        self.h2h_by_athlete = _h2h_by_athlete(tables["h2h"])
        self.primary_gender_by_athlete = primary_gender_by_athlete
        self.empty_results = tables["results"].iloc[0:0]
        self.empty_stats = tables["stats_fencer_comp"].iloc[0:0]
        self.empty_ratings = tables["ratings_history"].iloc[0:0]


def build_fencer_profile(athlete_id: int, ctx: ProfileContext) -> dict:
    athletes_idx = ctx.athletes_idx
    competitions = ctx.competitions_idx

    athlete_row = athletes_idx.loc[athlete_id]

    my_results = ctx.results_by_athlete.get(athlete_id, ctx.empty_results)
    my_stats = ctx.stats_by_athlete.get(athlete_id, ctx.empty_stats)
    merged = my_results.merge(my_stats, on=["competition_id", "athlete_id"], how="left")
    merged = merged.join(competitions[["name", "city", "country", "start_date", "weapon", "gender", "category", "level"]], on="competition_id")
    merged = merged.sort_values("start_date", ascending=False)

    base_cols = ["competition_id", "name", "city", "country", "start_date", "weapon", "gender", "category", "level"]
    results_out = []
    for row in merged[base_cols + STATS_PROFILE_COLS].to_dict("records"):
        entry = {
            "competition_id": row["competition_id"],
            "name": row["name"],
            "city": row["city"],
            "country": row["country"],
            "date": row["start_date"],
            "weapon": row["weapon"],
            "gender": row["gender"],
            "category": row["category"],
            "level": row["level"],
        }
        for col in STATS_PROFILE_COLS:
            entry[col] = row[col]
        results_out.append(entry)

    # --- Career summary per weapon ---
    my_ratings_all = ctx.ratings_by_athlete.get(athlete_id, ctx.empty_ratings)
    gender = ctx.primary_gender_by_athlete.get(athlete_id)
    by_weapon = merged.groupby("weapon")
    career = []
    for weapon, group in by_weapon:
        pool_ratings = my_ratings_all[
            (my_ratings_all["weapon"] == weapon) & (my_ratings_all["gender"] == gender)
        ]
        current_rating = None
        if not pool_ratings.empty:
            pool_ratings = pool_ratings.join(competitions[["start_date"]], on="competition_id")
            current_rating = round(float(pool_ratings.sort_values("start_date").iloc[-1]["post"]), 1)
        best_rank = group["POS"].min()
        career.append({
            "weapon": weapon,
            "n_comps": int(len(group)),
            "best_rank": None if pd.isna(best_rank) else int(best_rank),
            "titles": int((group["POS"] == 1).sum()),
            "current_rating": current_rating,
        })
    career.sort(key=lambda c: c["n_comps"], reverse=True)

    # --- Rating timeline (all pools this athlete has rated bouts in) ---
    my_ratings = my_ratings_all.join(competitions[["start_date", "name"]], on="competition_id")
    my_ratings = my_ratings.sort_values("start_date")
    timeline = [
        {
            "competition_id": r.competition_id,
            "date": r.start_date,
            "weapon": r.weapon,
            "gender": r.gender,
            "pre": round(float(r.pre), 1),
            "post": round(float(r.post), 1),
        }
        for r in my_ratings.itertuples(index=False)
    ]

    # --- Top rivals (>= MIN_H2H_BOUTS_FOR_SUMMARY bouts, already in this
    # athlete's own perspective courtesy of `_h2h_by_athlete`) ---
    mine = ctx.h2h_by_athlete.get(athlete_id)
    rivals = []
    if mine is not None:
        mine = mine[mine["bouts"] >= MIN_H2H_BOUTS_FOR_SUMMARY]
        mine = mine.sort_values("bouts", ascending=False).head(TOP_N_RIVALS)
        for r in mine.itertuples(index=False):
            opp_id = r.opponent_id
            rivals.append({
                "id": int(opp_id),
                "name": athletes_idx.at[opp_id, "name"] if opp_id in athletes_idx.index else None,
                "country": athletes_idx.at[opp_id, "country"] if opp_id in athletes_idx.index else None,
                "weapon": r.weapon,
                "gender": r.gender,
                "bouts": int(r.bouts),
                "wins": int(r.wins),
                "losses": int(r.losses),
                "last_met": r.last_met,
            })

    return {
        "id": int(athlete_id),
        "name": athlete_row["name"],
        "country": athlete_row["country"],
        "birth_year": None if pd.isna(athlete_row["birth_year"]) else int(athlete_row["birth_year"]),
        "hand": athlete_row["hand"] if pd.notna(athlete_row["hand"]) else None,
        "career": career,
        "results": results_out,
        "rating_timeline": timeline,
        "top_rivals": rivals,
    }


def build_site() -> dict:
    """Builds all artifacts, writes them under `site/data/`, returns a
    size report dict (path -> bytes) for the caller to print / gate on."""
    tables = _load_tables()
    bouts_count = int(pd.read_parquet(CANONICAL_DIR / "bouts.parquet", columns=["competition_id"]).shape[0])

    report: dict[str, int] = {}

    meta = build_meta(tables, bouts_count)
    report["meta.json"] = _write_json(SITE_DATA_DIR / "meta.json", meta)

    index_entries, shard_ids = build_fencer_index(tables["results"], tables["competitions"], tables["athletes"])
    report["fencers/index.json"] = _write_json(SITE_DATA_DIR / "fencers" / "index.json", index_entries)

    for weapon in WEAPONS:
        for gender in GENDERS:
            summary = build_summary(weapon, gender, tables)
            rel = f"summary/{weapon.lower()}{gender.lower()}.json"
            report[rel] = _write_json(SITE_DATA_DIR / rel, summary)

    primary_gender = _athlete_primary_gender(tables["results"], tables["competitions"])
    ctx = ProfileContext(tables, primary_gender)
    shard_bytes_total = 0
    for athlete_id in shard_ids:
        profile = build_fencer_profile(athlete_id, ctx)
        shard = athlete_id % 100
        rel_path = SITE_DATA_DIR / "fencers" / str(shard) / f"{athlete_id}.json"
        shard_bytes_total += _write_json(rel_path, profile)
    report[f"fencers/{{shard}}/*.json ({len(shard_ids)} files)"] = shard_bytes_total

    return report
