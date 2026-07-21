"""Competition-matching report against the legacy CSV validation oracle
(`data/legacy/updated_results.csv`, 48,535 rows / 286 competition-events,
2015-2022, Senior only).

The legacy CSV has no competition id, so a "competition" there is a distinct
`(comp, place, date, weapon, gender)` tuple — one weapon/gender event, same
granularity as one row in the canonical `competitions` table. Matching to
canonical rows is by `(weapon, gender)` exact + `start_date` within `TOL_DAYS`
(the legacy `date` field is not perfectly consistent about which day of a
multi-day event it records).

`normalize_name` is a reusable helper for M4's fencer-level parity work
(legacy ids are collision-prone `name[:11].lower()` slugs, not real FIE ids
-- fencer matching there will need normalized-name + country, same idea).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

LEGACY_CSV = Path("data/legacy/updated_results.csv")
TOL_DAYS = 1
PARITY_METRICS = ["POS", "PVICT", "PTD", "PTR", "PIND", "Q", "TMVAVG"]


def normalize_name(name: str | None) -> str:
    """Uppercase, strip accents/punctuation/extra whitespace -- for matching
    fencer names across the legacy CSV and fie.org's canonical `athletes`."""
    if not name:
        return ""
    stripped = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    stripped = re.sub(r"[^A-Za-z ]", " ", stripped).upper()
    return re.sub(r"\s+", " ", stripped).strip()


def load_legacy_competitions(csv_path: Path | str = LEGACY_CSV) -> pd.DataFrame:
    """One row per distinct legacy `(comp, place, date, weapon, gender)`
    competition-event, with `n_entries` (row count) for reference."""
    df = pd.read_csv(csv_path, usecols=["comp", "place", "date", "weapon", "gender"])
    df["date"] = pd.to_datetime(df["date"], format="mixed").dt.date
    comps = (
        df.groupby(["comp", "place", "date", "weapon", "gender"], as_index=False)
        .size()
        .rename(columns={"size": "n_entries"})
    )
    return comps


def match_competitions(legacy_comps: pd.DataFrame, canonical: pd.DataFrame) -> list[dict]:
    """For each legacy competition-event, find a canonical competition with
    the same `(weapon, gender)` and a `start_date` within `TOL_DAYS`. Returns
    one dict per legacy row: `{"legacy": {...}, "competition_id": str|None}`
    (`None` = no match found).
    """
    canonical = canonical.dropna(subset=["start_date"]).copy()
    canonical["start_date"] = pd.to_datetime(canonical["start_date"]).dt.date

    by_wg: dict[tuple, pd.DataFrame] = {
        key: group for key, group in canonical.groupby(["weapon", "gender"])
    }

    results = []
    for row in legacy_comps.to_dict("records"):
        candidates = by_wg.get((row["weapon"], row["gender"]))
        matched_id = None
        if candidates is not None:
            delta = (candidates["start_date"] - row["date"]).abs()
            within = candidates[delta <= timedelta(days=TOL_DAYS)]
            if not within.empty:
                matched_id = within.iloc[0]["competition_id"]
        results.append({"legacy": row, "competition_id": matched_id})
    return results


def load_legacy_results(csv_path: Path | str = LEGACY_CSV) -> pd.DataFrame:
    """Full per-fencer legacy rows, with `comp`/`place`/`date`/`weapon`/`gender`
    (the same competition-event key `match_competitions` uses) plus the
    metric columns M4's parity check needs -- already legacy-named the same
    as `stats.compute_stats`'s output (POS, PVICT, PTD, PTR, PIND, Q, TMVAVG)."""
    cols = ["comp", "place", "date", "weapon", "gender", "name", "country"] + PARITY_METRICS
    df = pd.read_csv(csv_path, usecols=cols)
    df["date"] = pd.to_datetime(df["date"], format="mixed").dt.date
    df["norm_name"] = df["name"].apply(normalize_name)
    return df


def _agree(legacy: pd.Series, canonical: pd.Series) -> pd.Series:
    """Element-wise agreement, tolerant of float rounding; both-NaN counts
    as agreement (e.g. TMVAVG null on both sides when Q==0)."""
    legacy = pd.to_numeric(legacy, errors="coerce")
    canonical = pd.to_numeric(canonical, errors="coerce")
    both_na = legacy.isna() & canonical.isna()
    valid = legacy.notna() & canonical.notna()
    close = pd.Series(False, index=legacy.index)
    close[valid] = np.isclose(legacy[valid].astype(float), canonical[valid].astype(float), atol=0.01)
    return both_na | close


def compute_parity(
    legacy_results: pd.DataFrame,
    legacy_comps: pd.DataFrame,
    canonical_competitions: pd.DataFrame,
    canonical_stats: pd.DataFrame,
    canonical_athletes: pd.DataFrame,
) -> dict:
    """Fencer-level parity report: matches legacy competitions to canonical
    ones (same logic as `match_competitions`), then matches individual
    fencers within each by normalized name + country, and reports per-metric
    and overall agreement rates over `PARITY_METRICS`.
    """
    comp_matches = match_competitions(legacy_comps, canonical_competitions)
    match_map = {
        (m["legacy"]["comp"], m["legacy"]["place"], m["legacy"]["date"], m["legacy"]["weapon"], m["legacy"]["gender"]): m["competition_id"]
        for m in comp_matches
        if m["competition_id"] is not None
    }

    legacy_results = legacy_results.copy()
    legacy_results["competition_id"] = legacy_results.apply(
        lambda r: match_map.get((r["comp"], r["place"], r["date"], r["weapon"], r["gender"])), axis=1
    )
    matched_legacy = legacy_results.dropna(subset=["competition_id"])

    athletes = canonical_athletes.copy()
    athletes["norm_name"] = athletes["name"].apply(normalize_name)
    stats_with_name = canonical_stats.merge(
        athletes[["athlete_id", "norm_name", "country"]], on="athlete_id", how="left"
    )

    joined = matched_legacy.merge(
        stats_with_name, on=["competition_id", "norm_name", "country"], how="inner", suffixes=("_legacy", "")
    )

    n_competitions = joined["competition_id"].nunique()
    n_fencers = len(joined)

    per_metric = {}
    for metric in PARITY_METRICS:
        agree = _agree(joined[f"{metric}_legacy"], joined[metric])
        per_metric[metric] = agree.mean() if len(agree) else float("nan")

    overall_agree = pd.concat(
        [_agree(joined[f"{m}_legacy"], joined[m]) for m in PARITY_METRICS], ignore_index=True
    )
    overall_rate = overall_agree.mean() if len(overall_agree) else 0.0

    return {
        "n_competitions": n_competitions,
        "n_fencers": n_fencers,
        "per_metric": per_metric,
        "overall_rate": overall_rate,
    }
