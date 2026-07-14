"""Tests for `discover.list_competitions` against a frozen 2004 season
listing (`tests/fixtures/competitions-list-2004-I.json.gz`, `type='I'`
already server-filtered — 260 rows across all categories) and the frozen
seasons list (`tests/fixtures/seasons.json.gz`, 1953-2027). Both are real
fie.org responses captured 2026-07-14 during M3a's shape survey.
"""
from pathlib import Path

import pytest

from ffs.discover import list_competitions
from ffs.fie_client import FieClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def client():
    return FieClient(cache_dir=FIXTURES_DIR)


def test_fetch_seasons(client):
    seasons = client.fetch_seasons()
    assert seasons[0] == 1953
    assert seasons[-1] == 2027
    assert 2004 in seasons


def test_list_competitions_filters_category_client_side(client):
    # the cached page has 260 rows total (S/J/C/V mixed) but the server
    # ignores `category` -- list_competitions must filter it itself.
    comps = list_competitions(client, 2004)
    assert len(comps) == 152
    assert all(c["category"] == "S" for c in comps)


def test_list_competitions_weapon_gender_filter(client):
    comps = list_competitions(client, 2004, weapon="E", gender="M")
    assert len(comps) == 33
    assert all(c["weapon"] == "E" and c["gender"] == "M" for c in comps)


def test_list_competitions_empty_filter(client):
    comps = list_competitions(client, 2004, category="GV")
    assert comps == []
