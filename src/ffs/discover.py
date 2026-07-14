"""Competition discovery: list Senior Individual competitions for a season.

Uses `FieClient.fetch_competitions_list` (the `/api/fie/competitions` REST
endpoint) rather than an SSR page — fie.org has no SSR-rendered page that
lists a season's competitions (the `/events` page only embeds upcoming
tournaments + the seasons list; per-tournament competition listings live on
`/tournaments/{season}/{id}`, one tournament at a time). See
`fie_client.fetch_competitions_list`'s docstring for the `category`
server-side filter bug this module works around client-side, and the
`season` validation footgun.
"""
from __future__ import annotations

from ffs.fie_client import FieClient

SENIOR = "S"
INDIVIDUAL = "I"


def list_competitions(
    client: FieClient,
    season: int,
    category: str = SENIOR,
    type_: str = INDIVIDUAL,
    weapon: str | None = None,
    gender: str | None = None,
    force: bool = False,
) -> list[dict]:
    """Senior, Individual competitions for a season (fie.org's raw metadata
    rows: `competitionId`, `season`, `name`, `weapon`, `gender`, `category`,
    `startDate`, `hasResults`, ...). `category` is filtered client-side since
    the server ignores that query param.
    """
    items = client.fetch_competitions_list(season, type_=type_, force=force)
    out = [i for i in items if i.get("category") == category]
    if weapon:
        out = [i for i in out if i.get("weapon") == weapon]
    if gender:
        out = [i for i in out if i.get("gender") == gender]
    return out
