"""Tests for `scrape-all`'s resume/skip helper -- pure logic, no network."""
from pathlib import Path

import pandas as pd

from ffs.cli import _existing_competition_ids


def test_existing_competition_ids_missing_file(tmp_path: Path):
    assert _existing_competition_ids(tmp_path) == set()


def test_existing_competition_ids_reads_column(tmp_path: Path):
    df = pd.DataFrame({"competition_id": ["2020-1", "2020-2", "2021-5"], "name": ["a", "b", "c"]})
    df.to_parquet(tmp_path / "competitions.parquet", index=False)
    assert _existing_competition_ids(tmp_path) == {"2020-1", "2020-2", "2021-5"}
