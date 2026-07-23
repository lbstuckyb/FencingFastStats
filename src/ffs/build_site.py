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
  rating chart), a top-10 rivals list (>=3 head-to-head bouts), and `h2h_all`:
  a compact `[opponent_id, weapon, bouts, wins, last_met]` row for *every*
  opponent this fencer has ever met (see below).
- `competitions/index.json` — the competition browser's list: one short-key
  row per competition (id, name, city, country, date, weapon, gender, level,
  entries, champion).
- `competitions/{competition_id}.json` — competition detail: final ranking,
  one entry per poule (fencer roster in fie.org's own row order plus the
  bout grid) and the DE bouts grouped by round, oldest round first.
- `h2h/{lo}-{hi}.json` — head-to-head detail for pairs with **>=5** bouts
  (`lo`/`hi` = the two athlete ids sorted ascending, matching `h2h.parquet`'s
  canonical pair key): per-pool aggregates plus the bout-by-bout list.
- `explore/{weapon}{gender}.json` — the metrics explorer's source data: one
  pre-aggregated row per (athlete, season, competition-level group) holding
  per-metric **sums** plus the population counts of `metrics.COUNT_SOURCE`,
  so the client can re-aggregate any season range × level-group subset
  correctly without re-fetching. Lazy: only the explorer page loads one.
- `paths/{weapon}{gender}.json` — the trajectories page's cohort curves: for
  each cohort tier and each metric, a by-age distribution (n / mean /
  p25 / p50 / p75). Cohorts are "this athlete's peak rating ever placed them
  in the top N of their pool" — a FencingFastStats measure, not an FIE
  ranking (there is no FIE ranking anywhere in this dataset). Also lazy.

Per the plan's size guardrail ("prune per-fencer shards to athletes with
>=2 comps"), athletes with exactly one competition result get no shard —
and are excluded from the search index too, so search never links to a
missing profile.

The H2H explorer has to answer "have these two ever met?" for *any* pair of
indexed fencers, but a pair file per pair would be 413k files for what is
usually a single bout. Hence the split: every meeting is in the (compact,
~28 bytes/row) `h2h_all` list of both fencers' shards, which the explorer
already loads for the names; the pair files add the bout-by-bout detail only
where there's a real rivalry to show.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

from ffs import metrics as metrics_registry
from ffs import schema

CANONICAL_DIR = Path("data/canonical")
SITE_DATA_DIR = Path("site/data")

WEAPONS = ["E", "F", "S"]
GENDERS = ["M", "F"]

# fie.org's `level` codes bucketed into the tiers a reader actually filters on
# (legacy's COPA / GP / MUNDIAL / ZONAL competition-type picker, widened to
# cover every code the archive uses). `OTH` is the catch-all so an unseen
# future code still lands somewhere rather than dropping rows silently.
LEVEL_GROUPS: list[tuple[str, str, list[str]]] = [
    ("WC", "World Cup", ["A"]),
    ("GP", "Grand Prix", ["GP"]),
    ("WCH", "World & Olympic", ["CHM", "JO", "OF"]),
    ("ZON", "Zonal championships", ["CHZ", "CHE"]),
    ("SAT", "Satellite", ["SA"]),
    ("NAT", "National / other FIE", ["NF"]),
    ("OTH", "Other", []),
]
LEVEL_GROUP_CODES = [code for code, _, _ in LEVEL_GROUPS]
LEVEL_TO_GROUP = {level: code for code, _, levels in LEVEL_GROUPS for level in levels}
DEFAULT_LEVEL_GROUPS = ["WC", "GP"]

# Trajectory cohorts: "the athlete's peak rating ever placed them this high in
# their (weapon, gender) pool". `all` = every athlete with a profile.
COHORT_TIERS: list[tuple[str, int | None]] = [
    ("top10", 10), ("top32", 32), ("top100", 100), ("all", None),
]
PATH_AGES = list(range(12, 46))
MIN_COHORT_AGE_SAMPLE = 3

MIN_COMPS_FOR_SHARD = 2
MIN_H2H_BOUTS_FOR_SUMMARY = 3
MIN_H2H_BOUTS_FOR_PAIR_FILE = 5
TOP_N_ELO = 200
TOP_N_LEADERBOARD = 50
RECENT_N_COMPS = 20
TOP_N_RIVALS = 10

EAGER_SIZE_WARN_BYTES = 1_500_000

# Files the site fetches on a normal first visit -- these are what the 1.5 MB
# guardrail is about. Everything else (`fencers/{shard}`, `competitions/{id}`,
# `h2h`, `explore`, `paths`) is fetched only by the one page that needs it.
EAGER_PREFIXES = ("meta.json", "fencers/index.json", "competitions/index.json", "summary/")


def is_eager(rel_path: str) -> bool:
    return rel_path.startswith(EAGER_PREFIXES)


def _json_default(obj):
    """Values read straight off a nullable-dtype column arrive as `pd.NA` /
    `pd.NaT` rather than `None` (e.g. a competition with no recorded city).
    Every builder would otherwise need a `pd.notna` guard per field."""
    if obj is pd.NA or obj is pd.NaT:
        return None
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _write_json(path: Path, obj) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, separators=(",", ":"), default=_json_default)
    path.write_text(text)
    return len(text.encode("utf-8"))


def _load_tables() -> dict[str, pd.DataFrame]:
    names = [
        "competitions", "athletes", "results", "stats_fencer_comp",
        "ratings_history", "h2h",
    ]
    tables = {name: pd.read_parquet(CANONICAL_DIR / f"{name}.parquet") for name in names}
    # fie.org's no-ranking sentinels would otherwise print as "#9999" in a
    # competition's results table (see schema.RANK_SENTINEL_MIN).
    tables["results"] = schema.clean_final_rank(tables["results"])
    # A few hundred fie.org athlete names carry leading/trailing whitespace,
    # which otherwise sorts them ahead of everything in the search index.
    tables["athletes"]["name"] = tables["athletes"]["name"].str.strip()
    return tables


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
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "season_min": int(seasons.min()),
        "season_max": int(seasons.max()),
        "n_competitions": int(len(competitions)),
        "n_athletes": int(len(tables["athletes"])),
        "n_bouts": bouts_count,
        "weapons": WEAPONS,
        "genders": GENDERS,
        # The metric registry travels with the data so no JS view ever
        # hardcodes a label, an aggregation or a sort direction.
        **metrics_registry.registry_json(),
        "level_groups": [
            {"code": code, "label": label, "levels": levels}
            for code, label, levels in LEVEL_GROUPS
        ],
        "default_level_groups": DEFAULT_LEVEL_GROUPS,
        "cohort_tiers": [
            {"code": code, "label": "All rated fencers" if n is None else f"Top {n}", "n": n}
            for code, n in COHORT_TIERS
        ],
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


# Shards carry *every* metric, as a fixed-order array keyed by
# `meta.json`'s `metrics` list rather than 23 named keys -- 23 short repeated
# key strings per result row would have cost more than the 12 extra values.
STATS_PROFILE_COLS = metrics_registry.METRIC_CODES


def _metric_value(value):
    """One metric value, JSON-ready: `None` for missing, a plain int when the
    value is integral (most of them are -- `"POS":1` rather than `"POS":1.0`
    across 260k result rows is worth the branch), otherwise rounded to 4dp
    (the source metrics are means of small integers; more digits is noise)."""
    if pd.isna(value):
        return None
    value = float(value)
    return int(value) if value.is_integer() else round(value, 4)


def compute_peak_ratings(
    ratings_history: pd.DataFrame, shard_ids: set[int] | None = None
) -> pd.DataFrame:
    """Each athlete's highest rating ever in each (weapon, gender) pool, plus
    that peak's rank within the pool — the basis for the profile's peak-rating
    figure and for the trajectory cohorts.

    Ranking is over athletes who have a profile shard, so a rank shown on the
    site always refers to a set the reader can actually browse, and a
    one-competition fencer's single lucky result can't displace a career.

    Columns: `athlete_id, weapon, gender, peak, rank`.
    """
    if shard_ids is not None:
        ratings_history = ratings_history[ratings_history["athlete_id"].isin(shard_ids)]
    peak = (
        ratings_history.groupby(["athlete_id", "weapon", "gender"], as_index=False)["post"]
        .max()
        .rename(columns={"post": "peak"})
    )
    peak["rank"] = (
        peak.groupby(["weapon", "gender"])["peak"].rank(method="min", ascending=False).astype(int)
    )
    return peak


def _group_dict(df: pd.DataFrame, key) -> dict:
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

    def __init__(
        self,
        tables: dict[str, pd.DataFrame],
        primary_gender_by_athlete: pd.Series,
        shard_ids: set[int] | None = None,
    ):
        # `h2h_all` only lists opponents who have a profile of their own --
        # the explorer picks both fencers out of the search index, so rows for
        # unindexed opponents would be dead weight in every shard.
        self.shard_ids = shard_ids
        self.athletes_idx = tables["athletes"].set_index("athlete_id")
        self.competitions_idx = tables["competitions"].set_index("competition_id")
        self.results_by_athlete = _group_dict(tables["results"], "athlete_id")
        self.stats_by_athlete = _group_dict(tables["stats_fencer_comp"], "athlete_id")
        self.ratings_by_athlete = _group_dict(tables["ratings_history"], "athlete_id")
        self.h2h_by_athlete = _h2h_by_athlete(tables["h2h"])
        self.primary_gender_by_athlete = primary_gender_by_athlete
        peaks = compute_peak_ratings(tables["ratings_history"], shard_ids)
        # (athlete_id, weapon, gender) -> (peak rating, rank in that pool)
        self.peak_by_pool = {
            (int(r.athlete_id), r.weapon, r.gender): (round(float(r.peak), 1), int(r.rank))
            for r in peaks.itertuples(index=False)
        }
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
            # Fixed-order metric values, keyed by `meta.json`'s `metrics`.
            "m": [_metric_value(row[col]) for col in STATS_PROFILE_COLS],
        }
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
        # Peak rating and where that peak stands among every profiled fencer
        # of this pool -- a FencingFastStats measure, not an FIE ranking.
        peak_rating, peak_pool_rank = ctx.peak_by_pool.get((int(athlete_id), weapon, gender), (None, None))
        career.append({
            "weapon": weapon,
            "n_comps": int(len(group)),
            "best_rank": None if pd.isna(best_rank) else int(best_rank),
            "titles": int((group["POS"] == 1).sum()),
            "current_rating": current_rating,
            "peak_rating": peak_rating,
            "peak_pool_rank": peak_pool_rank,
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
    h2h_all = []
    if mine is not None:
        listed = mine if ctx.shard_ids is None else mine[mine["opponent_id"].isin(ctx.shard_ids)]
        h2h_all = [
            [int(r.opponent_id), r.weapon, int(r.bouts), int(r.wins), r.last_met]
            for r in listed.sort_values("opponent_id").itertuples(index=False)
        ]

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
        # [opponent_id, weapon, bouts, wins, last_met] -- every opponent, for
        # the H2H explorer. Gender is the fencer's own pool (see `_h2h_by_athlete`).
        "h2h_all": h2h_all,
    }


# ---------------------------------------------------------------- competitions

# Round codes come straight from fie.org's tableau payloads and are not one
# scheme: the modern one runs a preliminary "A" tableau (A256 -> A64) into the
# main "B" tableau (B64 -> B2, the final), while older seasons also use `F*`,
# `pre*`, `PD*` and bare round numbers. Ordering is therefore a best-effort
# interpretation: {prefix: (stage rank, +1 if the number counts up through the
# event, -1 if it counts down)}.
_ROUND_PREFIXES: dict[str, tuple[int, int]] = {
    "pre": (0, -1), "PD": (0, +1), "A": (1, -1), "F": (2, -1), "": (3, -1), "B": (4, -1),
}


def _round_sort_key(code: str) -> tuple:
    match = re.fullmatch(r"([A-Za-z]*)(\d*)", code or "")
    prefix, digits = match.groups() if match else ("?", "")
    rank, direction = _ROUND_PREFIXES.get(prefix, (3, -1))
    return (rank, direction * (int(digits) if digits else 0), code or "")


def _poule_roster(group: pd.DataFrame) -> list[int]:
    """fie.org's own row order for one poule, recovered from `bout_order`.

    `bout_order` on a poule bout is the row position of `athlete_b`, which is
    always the *larger* of the pair's two ids -- so every fencer but the
    lowest-id one is placed directly, and that one takes the position left
    over. Fencers whose position can't be recovered (archive gaps where their
    bouts are missing entirely) are appended by id, so the grid is still
    complete even when the order isn't authentic.
    """
    positions: dict[int, int] = {}
    for row in group.itertuples(index=False):
        if pd.notna(row.athlete_b) and pd.notna(row.bout_order):
            positions[int(row.athlete_b)] = int(row.bout_order)

    members = {int(a) for a in group["athlete_a"].dropna()} | {int(b) for b in group["athlete_b"].dropna()}
    unplaced = sorted(members - set(positions))
    free = [p for p in range(1, len(members) + 1) if p not in set(positions.values())]
    for athlete_id, position in zip(unplaced, free):
        positions[athlete_id] = position

    return sorted(members, key=lambda a: (positions.get(a, 10**6), a))


class CompetitionContext:
    """Pre-grouped per-competition lookups, same motivation as `ProfileContext`."""

    def __init__(self, tables: dict[str, pd.DataFrame], bouts: pd.DataFrame):
        self.competitions_idx = tables["competitions"].set_index("competition_id")
        self.athletes_idx = tables["athletes"].set_index("athlete_id")
        self.results_by_comp = _group_dict(tables["results"], "competition_id")
        self.bouts_by_comp = _group_dict(bouts, "competition_id")
        self.empty_results = tables["results"].iloc[0:0]
        self.empty_bouts = bouts.iloc[0:0]


def build_competitions_index(tables: dict[str, pd.DataFrame]) -> list[dict]:
    """One short-key row per competition, newest first, for the browser page:
    `id/n(ame)/ci(ty)/co(untry)/d(ate)/w(eapon)/g(ender)/l(evel)/e(ntries)`
    plus `c` = `[champion_id, champion_name]`."""
    competitions = tables["competitions"].sort_values("start_date", ascending=False)
    athletes = tables["athletes"].set_index("athlete_id")
    results = tables["results"]

    champions = results[results["final_rank"] == 1]
    champ_by_comp = dict(zip(champions["competition_id"], champions["athlete_id"]))

    rows = []
    for r in competitions.itertuples(index=False):
        champ_id = champ_by_comp.get(r.competition_id)
        champion = None
        if champ_id is not None and pd.notna(champ_id):
            name = athletes.at[champ_id, "name"] if champ_id in athletes.index else None
            champion = [int(champ_id), name]
        rows.append({
            "id": r.competition_id,
            "n": r.name,
            "ci": r.city,
            "co": r.country,
            "d": r.start_date,
            "w": r.weapon,
            "g": r.gender,
            "l": r.level,
            "e": int(r.n_entries) if pd.notna(r.n_entries) else None,
            "c": champion,
        })
    return rows


def build_competition_detail(competition_id: str, ctx: CompetitionContext) -> dict:
    comp = ctx.competitions_idx.loc[competition_id]
    results = ctx.results_by_comp.get(competition_id, ctx.empty_results).sort_values("final_rank")
    bouts = ctx.bouts_by_comp.get(competition_id, ctx.empty_bouts)

    athlete_ids = {int(a) for a in results["athlete_id"].dropna()}
    if not bouts.empty:
        athlete_ids |= {int(a) for a in bouts["athlete_a"].dropna()}
        athlete_ids |= {int(b) for b in bouts["athlete_b"].dropna()}

    athletes = {}
    for athlete_id in sorted(athlete_ids):
        if athlete_id in ctx.athletes_idx.index:
            row = ctx.athletes_idx.loc[athlete_id]
            athletes[str(athlete_id)] = [row["name"], row["country"]]
        else:
            athletes[str(athlete_id)] = [None, None]

    ranking = [
        {
            "a": int(r.athlete_id),
            "r": int(r.final_rank) if pd.notna(r.final_rank) else None,
            "s": int(r.seed) if pd.notna(r.seed) else None,
            "p": round(float(r.points), 2) if pd.notna(r.points) else None,
        }
        for r in results.itertuples(index=False)
    ]

    poules = []
    poule_bouts = bouts[bouts["phase"] == "poule"] if not bouts.empty else bouts
    if not poule_bouts.empty:
        for poule_no, group in poule_bouts.groupby("poule_no"):
            roster = _poule_roster(group)
            slot = {athlete_id: i for i, athlete_id in enumerate(roster)}
            # [row_a, row_b, score_a, score_b, status, winner_row] -- all
            # positions are indices into `fencers`, so the grid renders without
            # a lookup, and the winner is explicit (a forfeit has a winner but
            # no meaningful score).
            grid = [
                [
                    slot[int(r.athlete_a)], slot[int(r.athlete_b)],
                    int(r.score_a) if pd.notna(r.score_a) else None,
                    int(r.score_b) if pd.notna(r.score_b) else None,
                    r.status,
                    slot.get(int(r.winner)) if pd.notna(r.winner) else None,
                ]
                for r in group.itertuples(index=False)
                if pd.notna(r.athlete_a) and pd.notna(r.athlete_b)
            ]
            poules.append({"no": int(poule_no), "fencers": roster, "bouts": grid})

    de_rounds = []
    de_bouts = bouts[bouts["phase"] == "de"] if not bouts.empty else bouts
    if not de_bouts.empty:
        for round_code, group in sorted(de_bouts.groupby("round"), key=lambda kv: _round_sort_key(kv[0])):
            group = group.sort_values("bout_order")
            de_rounds.append({
                "round": round_code,
                "bouts": [
                    [
                        int(r.athlete_a) if pd.notna(r.athlete_a) else None,
                        int(r.athlete_b) if pd.notna(r.athlete_b) else None,
                        int(r.score_a) if pd.notna(r.score_a) else None,
                        int(r.score_b) if pd.notna(r.score_b) else None,
                        int(r.winner) if pd.notna(r.winner) else None,
                        r.status,
                    ]
                    for r in group.itertuples(index=False)
                ],
            })

    return {
        "id": competition_id,
        "name": comp["name"],
        "city": comp["city"],
        "country": comp["country"],
        "date": comp["start_date"],
        "season": int(comp["season"]) if pd.notna(comp["season"]) else None,
        "weapon": comp["weapon"],
        "gender": comp["gender"],
        "category": comp["category"],
        "level": comp["level"],
        "n_entries": int(comp["n_entries"]) if pd.notna(comp["n_entries"]) else None,
        "athletes": athletes,
        "results": ranking,
        "poules": poules,
        "de": de_rounds,
    }


# ------------------------------------------------------------------------ h2h

def build_h2h_pair(
    pair_h2h: pd.DataFrame,
    pair_bouts: pd.DataFrame,
    athletes_idx: pd.DataFrame,
    competitions_idx: pd.DataFrame,
) -> dict:
    """Detail file for one pair. `a` is always the lower athlete id (the
    `athlete_lo` of `h2h.parquet`), so scores need no re-orientation."""
    lo = int(pair_h2h["athlete_lo"].iloc[0])
    hi = int(pair_h2h["athlete_hi"].iloc[0])

    def _who(athlete_id: int) -> dict:
        row = athletes_idx.loc[athlete_id] if athlete_id in athletes_idx.index else None
        return {
            "id": athlete_id,
            "name": None if row is None else row["name"],
            "country": None if row is None else row["country"],
        }

    pools = [
        {
            "weapon": r.weapon,
            "gender": r.gender,
            "bouts": int(r.bouts),
            "wins_a": int(r.wins_lo),
            "wins_b": int(r.wins_hi),
            "td_a": int(r.td_lo) if pd.notna(r.td_lo) else None,
            "td_b": int(r.td_hi) if pd.notna(r.td_hi) else None,
            "poule_bouts": int(r.poule_bouts),
            "de_bouts": int(r.de_bouts),
            "last_met": r.last_met,
        }
        for r in pair_h2h.itertuples(index=False)
    ]

    pair_bouts = pair_bouts.sort_values("start_date", ascending=False)
    bouts = [
        {
            "competition_id": r.competition_id,
            "competition": competitions_idx.at[r.competition_id, "name"]
            if r.competition_id in competitions_idx.index else None,
            "date": r.start_date,
            "weapon": r.weapon,
            "gender": r.gender,
            "phase": r.phase,
            "round": r.round,
            "score_a": int(r.score_lo) if pd.notna(r.score_lo) else None,
            "score_b": int(r.score_hi) if pd.notna(r.score_hi) else None,
            "winner": int(r.winner) if pd.notna(r.winner) else None,
            "status": r.status,
        }
        for r in pair_bouts.itertuples(index=False)
    ]

    return {
        "a": _who(lo),
        "b": _who(hi),
        "totals": {
            "bouts": sum(p["bouts"] for p in pools),
            "wins_a": sum(p["wins_a"] for p in pools),
            "wins_b": sum(p["wins_b"] for p in pools),
            "last_met": max(p["last_met"] for p in pools if p["last_met"]) if pools else None,
        },
        "pools": pools,
        "bouts": bouts,
    }


# ------------------------------------------------------- explore / trajectories

def _pool_metric_rows(
    tables: dict[str, pd.DataFrame], weapon: str, gender: str, shard_ids: set[int] | None
) -> pd.DataFrame:
    """Every stats row of one (weapon, gender) pool, restricted to athletes
    with a profile shard and carrying the competition's `season`, `start_date`
    and level group. Metric columns are plain float64 so the aggregations
    below don't have to care which nullable dtype the parquet used."""
    competitions = tables["competitions"]
    pool = competitions[(competitions["weapon"] == weapon) & (competitions["gender"] == gender)]

    stats = tables["stats_fencer_comp"]
    df = stats[stats["competition_id"].isin(set(pool["competition_id"]))]
    if shard_ids is not None:
        df = df[df["athlete_id"].isin(shard_ids)]
    df = df.merge(
        pool[["competition_id", "season", "start_date", "level"]], on="competition_id", how="left"
    )
    df["lg"] = df["level"].map(LEVEL_TO_GROUP).fillna("OTH")
    df["athlete_id"] = df["athlete_id"].astype("int64")
    df["season"] = df["season"].astype("int64")
    codes = metrics_registry.METRIC_CODES
    df[codes] = df[codes].astype("float64")
    return df


def build_explore(
    weapon: str, gender: str, tables: dict[str, pd.DataFrame], shard_ids: set[int] | None = None
) -> dict:
    """Pre-aggregated explorer rows for one pool: one row per (athlete,
    season, level group).

    Rows hold **sums**, not means, plus the population counts of
    `metrics.COUNT_SOURCE` — so the client can add up any season range ×
    level-group subset the reader picks and divide once at the end, and get
    the same number a full re-aggregation would. Means can't be pre-computed
    here for the same reason: the mean of per-season means is not the mean.

    Row layout (see `row_format` in the output):
    `[athlete_id, season, level_group_index, *counts, *metric_sums]`.
    """
    df = _pool_metric_rows(tables, weapon, gender, shard_ids)
    codes = metrics_registry.METRIC_CODES

    grouped = df.groupby(["athlete_id", "season", "lg"], sort=True)
    sums = grouped[codes].sum(min_count=1)
    counts = pd.DataFrame(
        {key: grouped[source].count() for key, source in metrics_registry.COUNT_SOURCE.items()}
    )

    lg_index = {code: i for i, code in enumerate(LEVEL_GROUP_CODES)}
    rows = []
    for key, count_row in counts.iterrows():
        athlete_id, season, lg = key
        sum_row = sums.loc[key]
        rows.append(
            [int(athlete_id), int(season), lg_index[lg]]
            + [int(count_row[k]) for k in metrics_registry.COUNT_KEYS]
            + [_metric_value(sum_row[c]) for c in codes]
        )

    return {
        "weapon": weapon,
        "gender": gender,
        "level_groups": LEVEL_GROUP_CODES,
        "counts": metrics_registry.COUNT_KEYS,
        "metrics": codes,
        "row_format": "[athlete_id, season, level_group_index, ...counts, ...metric_sums]",
        "rows": rows,
    }


def _rating_by_age(
    tables: dict[str, pd.DataFrame], weapon: str, gender: str, birth_year: pd.Series
) -> pd.Series:
    """Each athlete's rating *at* a given age: the last rating they carried
    away from a competition in that calendar year, not the year's average —
    "where they had got to by then" is the quantity a trajectory compares."""
    ratings = tables["ratings_history"]
    ratings = ratings[(ratings["weapon"] == weapon) & (ratings["gender"] == gender)]
    ratings = ratings.merge(
        tables["competitions"][["competition_id", "start_date"]], on="competition_id", how="left"
    )
    ratings["age"] = (
        pd.to_datetime(ratings["start_date"]).dt.year
        - ratings["athlete_id"].map(birth_year)
    )
    ratings = ratings.dropna(subset=["age"]).sort_values("start_date")
    ratings["athlete_id"] = ratings["athlete_id"].astype("int64")
    ratings["age"] = ratings["age"].astype("int64")
    return ratings.groupby(["athlete_id", "age"])["post"].last().astype("float64")


def build_paths(
    weapon: str, gender: str, tables: dict[str, pd.DataFrame], shard_ids: set[int] | None = None
) -> dict:
    """By-age cohort curves for one pool — the "is this fencer on the path of
    a future top-10?" view.

    A cohort is every profiled fencer whose **peak FencingFastStats rating**
    ever placed them in the top N of this pool. That is a rating computed
    here from bout results, not an FIE ranking: the FIE's official points and
    rankings are not part of this dataset at all, so the tiers must always be
    labelled as this project's own measure.

    For every cohort tier and every series, the output holds the by-age
    distribution across the cohort's members: `{age: [n, mean, p25, p50,
    p75]}`. The median and the quartile band, rather than legacy's bare mean,
    are what make "on track" legible — a single mean can't show how wide the
    path is. Ages with fewer than `MIN_COHORT_AGE_SAMPLE` members are omitted
    rather than shown as a spike of one.
    """
    df = _pool_metric_rows(tables, weapon, gender, shard_ids)
    codes = metrics_registry.METRIC_CODES

    birth_year = tables["athletes"].set_index("athlete_id")["birth_year"]
    df["age"] = pd.to_datetime(df["start_date"]).dt.year - df["athlete_id"].map(birth_year)
    df = df.dropna(subset=["age"])
    df["age"] = df["age"].astype("int64")
    df = df[df["age"].between(PATH_AGES[0], PATH_AGES[-1])]

    df["_podium"] = (df["POS"] <= 3).astype("float64")
    df["_title"] = (df["POS"] == 1).astype("float64")

    # --- one value per (athlete, age): their own season, aggregated their way
    grouped = df.groupby(["athlete_id", "age"])
    mean_codes = [c for c in codes if metrics_registry.BY_CODE[c].agg == "mean"]
    sum_codes = [c for c in codes if metrics_registry.BY_CODE[c].agg == "sum"]
    per_athlete = grouped[mean_codes].mean()
    for code in sum_codes:
        per_athlete[code] = grouped[code].sum(min_count=1)
    per_athlete["n_comps"] = grouped.size().astype("float64")
    per_athlete["rate_t64"] = grouped["T64+"].mean()
    per_athlete["rate_tpre64"] = grouped["TPRE64"].mean()
    per_athlete["rate_podium"] = grouped["_podium"].mean()
    per_athlete["rate_title"] = grouped["_title"].mean()
    per_athlete["rating"] = _rating_by_age(tables, weapon, gender, birth_year)

    series_codes = codes + [s["code"] for s in metrics_registry.PATH_EXTRA_SERIES]
    per_athlete = per_athlete[series_codes].reset_index()

    peaks = compute_peak_ratings(tables["ratings_history"], shard_ids)
    peaks = peaks[(peaks["weapon"] == weapon) & (peaks["gender"] == gender)]

    tiers = {}
    cohort_ids = {}
    for tier_code, top_n in COHORT_TIERS:
        if top_n is None:
            members = set(per_athlete["athlete_id"])
        else:
            members = {int(a) for a in peaks[peaks["rank"] <= top_n]["athlete_id"]}
            cohort_ids[tier_code] = sorted(members)
        subset = per_athlete[per_athlete["athlete_id"].isin(members)]
        tiers[tier_code] = {
            "n_athletes": int(subset["athlete_id"].nunique()),
            "series": _by_age_distribution(subset, series_codes),
        }

    return {
        "weapon": weapon,
        "gender": gender,
        "ages": PATH_AGES,
        "series": series_codes,
        "point_format": "[n, mean, p25, p50, p75]",
        "tiers": tiers,
        "cohort_ids": cohort_ids,
    }


def _by_age_distribution(per_athlete: pd.DataFrame, series_codes: list[str]) -> dict:
    """`{series: {age: [n, mean, p25, p50, p75]}}` over one cohort's
    per-(athlete, age) values."""
    if per_athlete.empty:
        return {code: {} for code in series_codes}

    by_age = per_athlete.groupby("age")[series_codes]
    n = by_age.count()
    mean = by_age.mean()
    q25, q50, q75 = (by_age.quantile(q) for q in (0.25, 0.5, 0.75))

    out: dict[str, dict] = {}
    for code in series_codes:
        points = {}
        for age in n.index:
            count = int(n.at[age, code])
            if count < MIN_COHORT_AGE_SAMPLE:
                continue
            points[str(int(age))] = [count] + [
                _metric_value(frame.at[age, code]) for frame in (mean, q25, q50, q75)
            ]
        out[code] = points
    return out


def build_site() -> dict:
    """Builds all artifacts, writes them under `site/data/`, returns a
    size report dict (path -> bytes) for the caller to print / gate on."""
    tables = _load_tables()
    bouts = pd.read_parquet(CANONICAL_DIR / "bouts.parquet")
    bouts_count = int(len(bouts))

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

    # --- explorer + trajectory sources (lazy, page-scoped: not eager files) ---
    for weapon in WEAPONS:
        for gender in GENDERS:
            pool = f"{weapon.lower()}{gender.lower()}"
            explore = build_explore(weapon, gender, tables, shard_ids)
            report[f"explore/{pool}.json"] = _write_json(
                SITE_DATA_DIR / "explore" / f"{pool}.json", explore
            )
            paths = build_paths(weapon, gender, tables, shard_ids)
            report[f"paths/{pool}.json"] = _write_json(
                SITE_DATA_DIR / "paths" / f"{pool}.json", paths
            )

    primary_gender = _athlete_primary_gender(tables["results"], tables["competitions"])
    ctx = ProfileContext(tables, primary_gender, shard_ids)
    shard_bytes_total = 0
    for athlete_id in shard_ids:
        profile = build_fencer_profile(athlete_id, ctx)
        shard = athlete_id % 100
        rel_path = SITE_DATA_DIR / "fencers" / str(shard) / f"{athlete_id}.json"
        shard_bytes_total += _write_json(rel_path, profile)
    report[f"fencers/{{shard}}/*.json ({len(shard_ids)} files)"] = shard_bytes_total

    # --- competitions ---
    comp_index = build_competitions_index(tables)
    report["competitions/index.json"] = _write_json(
        SITE_DATA_DIR / "competitions" / "index.json", comp_index
    )

    comp_ctx = CompetitionContext(tables, bouts)
    comp_bytes_total = 0
    comp_ids = list(tables["competitions"]["competition_id"])
    for competition_id in comp_ids:
        detail = build_competition_detail(competition_id, comp_ctx)
        comp_bytes_total += _write_json(
            SITE_DATA_DIR / "competitions" / f"{competition_id}.json", detail
        )
    report[f"competitions/*.json ({len(comp_ids)} files)"] = comp_bytes_total

    # --- head-to-head pair files (real rivalries only, see module docstring) ---
    h2h_bouts = pd.read_parquet(CANONICAL_DIR / "h2h_bouts.parquet")
    h2h = tables["h2h"]
    pair_bouts = h2h.groupby(["athlete_lo", "athlete_hi"])["bouts"].sum()
    wanted = {
        (int(lo), int(hi))
        for (lo, hi), n in pair_bouts.items()
        if n >= MIN_H2H_BOUTS_FOR_PAIR_FILE and int(lo) in shard_ids and int(hi) in shard_ids
    }
    athletes_idx = tables["athletes"].set_index("athlete_id")
    competitions_idx = tables["competitions"].set_index("competition_id")
    h2h_by_pair = _group_dict(h2h, ["athlete_lo", "athlete_hi"])
    bouts_by_pair = _group_dict(h2h_bouts, ["athlete_lo", "athlete_hi"])
    pair_bytes_total = 0
    for pair in sorted(wanted):
        detail = build_h2h_pair(
            h2h_by_pair[pair], bouts_by_pair.get(pair, h2h_bouts.iloc[0:0]),
            athletes_idx, competitions_idx,
        )
        pair_bytes_total += _write_json(
            SITE_DATA_DIR / "h2h" / f"{pair[0]}-{pair[1]}.json", detail
        )
    report[f"h2h/*.json ({len(wanted)} files)"] = pair_bytes_total

    return report
