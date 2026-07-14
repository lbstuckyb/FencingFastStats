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

import pandas as pd

LEGACY_CSV = Path("data/legacy/updated_results.csv")
TOL_DAYS = 1


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
