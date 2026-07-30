"""Tests for the scrape/update season loop -- pure logic, no network.

`_scrape_seasons` is driven with a stub client that only implements
`fetch_competitions_list`, so nothing here touches fie.org.
"""
from pathlib import Path

import pandas as pd
import pytest

from ffs import cli
from ffs.cli import (
    _default_update_seasons,
    _existing_competition_ids,
    _latest_canonical_season,
    _scrape_seasons,
)


def test_existing_competition_ids_missing_file(tmp_path: Path):
    assert _existing_competition_ids(tmp_path) == set()


def test_existing_competition_ids_reads_column(tmp_path: Path):
    df = pd.DataFrame({"competition_id": ["2020-1", "2020-2", "2021-5"], "name": ["a", "b", "c"]})
    df.to_parquet(tmp_path / "competitions.parquet", index=False)
    assert _existing_competition_ids(tmp_path) == {"2020-1", "2020-2", "2021-5"}


class StubClient:
    """Records every `fetch_competitions_list` call and serves canned rows."""

    def __init__(self, rows_by_season: dict[int, list[dict]] | None = None):
        self.rows_by_season = rows_by_season or {}
        self.calls: list[tuple[int, bool]] = []

    def fetch_competitions_list(self, season, type_="I", force=False, page_size=1000):
        self.calls.append((season, force))
        return self.rows_by_season.get(season, [])


def _row(season: int, comp_id: int, name: str = "Comp") -> dict:
    return {
        "competitionId": comp_id, "season": season, "name": name,
        "category": "S", "weapon": "E", "gender": "M",
    }


def _tables(season: int, comp_id: int) -> dict[str, pd.DataFrame]:
    competition_id = f"{season}-{comp_id}"
    return {
        "competitions": pd.DataFrame([{"competition_id": competition_id, "season": season}]),
        "athletes": pd.DataFrame([{"athlete_id": comp_id, "name": "A"}]),
        "results": pd.DataFrame([{"competition_id": competition_id, "athlete_id": comp_id}]),
        "bouts": pd.DataFrame([{"competition_id": competition_id, "bout_id": 1}]),
    }


@pytest.fixture
def canonical(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "CANONICAL_DIR", tmp_path)
    monkeypatch.setattr(cli, "_write_failures", lambda failures: None)
    return tmp_path


def test_only_the_newest_season_list_is_refetched(canonical):
    """A closed season cannot gain competitions, but the one still in progress
    can -- honouring the cache there is what made `scrape-all` blind to newly
    finished events."""
    client = StubClient()
    _scrape_seasons(client, [2024, 2025, 2026])
    assert client.calls == [(2024, False), (2025, False), (2026, True)]


def test_refresh_lists_refetches_every_season(canonical):
    client = StubClient()
    _scrape_seasons(client, [2024, 2025, 2026], refresh_lists=True)
    assert client.calls == [(2024, True), (2025, True), (2026, True)]


def test_single_season_range_still_refetches(canonical):
    client = StubClient()
    _scrape_seasons(client, [2026])
    assert client.calls == [(2026, True)]


def test_skips_existing_and_reports_what_is_new(canonical, monkeypatch):
    pd.DataFrame({"competition_id": ["2026-1"], "season": [2026]}).to_parquet(
        canonical / "competitions.parquet", index=False
    )
    client = StubClient({2026: [_row(2026, 1), _row(2026, 2), _row(2026, 3)]})
    monkeypatch.setattr(cli, "_scrape_one", lambda c, s, cid, force=False: _tables(s, cid))

    outcome = _scrape_seasons(client, [2026])

    assert outcome["ok"] == 2
    assert outcome["skipped"] == 1
    assert outcome["failed"] == 0
    assert outcome["aborted"] is False
    assert outcome["new_competition_ids"] == ["2026-2", "2026-3"]
    written = pd.read_parquet(canonical / "competitions.parquet")
    assert set(written["competition_id"]) == {"2026-1", "2026-2", "2026-3"}


def test_failures_are_counted_not_fatal(canonical, monkeypatch):
    client = StubClient({2026: [_row(2026, 1), _row(2026, 2)]})

    def flaky(c, season, comp_id, force=False):
        if comp_id == 1:
            raise ValueError("no results")
        return _tables(season, comp_id)

    monkeypatch.setattr(cli, "_scrape_one", flaky)
    outcome = _scrape_seasons(client, [2026])

    assert outcome["ok"] == 1
    assert outcome["failed"] == 1
    assert outcome["aborted"] is False
    assert outcome["new_competition_ids"] == ["2026-2"]


def test_aborts_after_consecutive_failures(canonical, monkeypatch):
    client = StubClient({2026: [_row(2026, i) for i in range(1, 6)]})

    def always_fail(c, season, comp_id, force=False):
        raise ValueError("boom")

    monkeypatch.setattr(cli, "_scrape_one", always_fail)
    outcome = _scrape_seasons(client, [2026], max_consecutive_fails=2)

    assert outcome["aborted"] is True
    assert outcome["failed"] == 2


def test_latest_canonical_season(canonical):
    assert _latest_canonical_season(canonical) is None
    pd.DataFrame({"competition_id": ["2024-1", "2026-2"], "season": [2024, 2026]}).to_parquet(
        canonical / "competitions.parquet", index=False
    )
    assert _latest_canonical_season(canonical) == 2026


def test_default_update_seasons_spans_the_rollover():
    known = list(range(1953, 2028))
    # the season in progress, plus the next one -- so the September rollover
    # into a season the archive has never seen needs no flag.
    assert _default_update_seasons(known, 2026) == [2026, 2027]


def test_default_update_seasons_clamps_to_known_seasons():
    known = list(range(1953, 2028))
    assert _default_update_seasons(known, 2027) == [2027]
    assert _default_update_seasons(known, None) == [2027]
    assert _default_update_seasons([], None) == []
