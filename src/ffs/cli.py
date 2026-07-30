import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from ffs import __version__
from ffs import devalue, elo, h2h, schema, stats
from ffs.build_site import EAGER_SIZE_WARN_BYTES, build_site, is_eager
from ffs.discover import list_competitions
from ffs.fie_client import FieClient
from ffs.parse import parse_competition
from ffs.validate_legacy import (
    compute_parity,
    load_legacy_competitions,
    load_legacy_results,
    match_competitions,
)

CANONICAL_DIR = Path("data/canonical")


def _existing_competition_ids(out_dir: Path) -> set[str]:
    path = out_dir / "competitions.parquet"
    if not path.exists():
        return set()
    return set(pd.read_parquet(path, columns=["competition_id"])["competition_id"])


def _scrape_one(
    client: FieClient, season: int, comp_id: int, force: bool = False, dump: bool = False
) -> dict[str, pd.DataFrame]:
    """Fetch, decode and parse one competition. Raises on fetch/parse errors
    or `validate_tables()` issues (caller decides how to handle failures)."""
    comp = client.fetch_competition(season, comp_id, force=force)
    decoded = devalue.unflatten(comp["raw"])
    queries = devalue.extract_queries(decoded)
    ranking_items = client.fetch_results_ranking(season, comp_id, force=force)

    if dump:
        dump_path = Path(f"data/raw_cache/dump-{season}-{comp_id}.json")
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        with dump_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "tournament_id": comp["tournament_id"],
                    "queries": {str(k): v for k, v in queries.items()},
                    "ranking_items": ranking_items,
                },
                f,
                indent=2,
                default=str,
            )
        print(f"Dumped decoded queries to {dump_path}", file=sys.stderr)

    tables = parse_competition(
        season=season,
        comp_id=comp_id,
        tournament_id=comp["tournament_id"],
        queries=queries,
        ranking_items=ranking_items,
    )
    issues = schema.validate_tables(tables)
    # fie.org's own archive occasionally omits a pool/DE participant from a
    # competition's final ranking (data gap, not a parser bug) — tolerate that
    # specific issue rather than dropping an otherwise-good competition's data.
    fatal_issues = [i for i in issues if "bout athlete(s) missing from results" not in i]
    if fatal_issues:
        raise ValueError("validate_tables() found issues: " + "; ".join(fatal_issues))
    for issue in issues:
        if issue not in fatal_issues:
            print(f"[{season}-{comp_id}] tolerated: {issue}", file=sys.stderr)
    return tables


def _write_canonical(tables: dict[str, pd.DataFrame], out_dir: Path) -> None:
    """Merge new tables into existing canonical parquet, replacing any rows
    for competition_ids present in the new data (idempotent re-scrape)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    new_comp_ids = set(tables["competitions"]["competition_id"])
    for name, new_df in tables.items():
        path = out_dir / f"{name}.parquet"
        if path.exists():
            existing = pd.read_parquet(path)
            key_col = "competition_id" if "competition_id" in existing.columns else None
            if key_col is not None:
                existing = existing[~existing[key_col].isin(new_comp_ids)]
            elif name == "athletes":
                existing = existing[~existing["athlete_id"].isin(new_df["athlete_id"])]
            combined = pd.concat([existing, new_df], ignore_index=True)
            if name == "athletes":
                combined = combined.drop_duplicates(subset="athlete_id", keep="last")
            combined = schema.coerce_dtypes(name, combined)
        else:
            combined = new_df
        combined.to_parquet(path, index=False)


def cmd_scrape(args: argparse.Namespace) -> int:
    season_str, comp_id_str = args.comp.split("/")
    season, comp_id = int(season_str), int(comp_id_str)

    client = FieClient()
    try:
        tables = _scrape_one(client, season, comp_id, force=args.force, dump=args.dump)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    _write_canonical(tables, CANONICAL_DIR)
    for name, df in tables.items():
        print(f"{name}: {len(df)} rows")
    return 0


def _scrape_seasons(
    client: FieClient,
    seasons: list[int],
    *,
    weapon: str | None = None,
    gender: str | None = None,
    force: bool = False,
    max_consecutive_fails: int = 15,
    refresh_lists: bool = False,
) -> dict:
    """Scrape Senior Individual competitions across `seasons` (ascending).
    Resumable — competitions already present in
    `data/canonical/competitions.parquet` are skipped (unless `force`), and
    `FieClient`'s disk cache means a crashed/interrupted run mostly replays
    from cache on the next invocation rather than re-hitting fie.org.

    Writes are flushed once per season (not per competition) to keep parquet
    read/concat/write overhead bounded across ~3000 competitions; a crash
    mid-season loses that season's progress but it replays fast from cache.

    **The newest requested season's competition list is always re-fetched.**
    Everything else reads the cached list, but a season still in progress
    gains competitions after the list was first cached — that is exactly the
    "catch me up with what just happened" case, and honouring the cache there
    silently finds nothing new. Only the last season in the range can grow, so
    this costs one extra request per run even on a full 2002-2026 replay.
    `refresh_lists=True` re-fetches every season's list, for the rare case
    fie.org backfills a closed season.

    Returns `{"ok", "skipped", "failed", "aborted", "new_competition_ids"}`.
    """
    existing_ids = _existing_competition_ids(CANONICAL_DIR)
    total_ok = total_skip = total_fail = 0
    failures: list[dict] = []
    new_competition_ids: list[str] = []
    consecutive_fails = 0

    def result(aborted: bool) -> dict:
        return {
            "ok": total_ok,
            "skipped": total_skip,
            "failed": total_fail,
            "aborted": aborted,
            "new_competition_ids": new_competition_ids,
        }

    for season in seasons:
        comps = list_competitions(
            client,
            season,
            weapon=weapon,
            gender=gender,
            force=refresh_lists or season == seasons[-1],
        )
        season_tables: dict[str, list[pd.DataFrame]] = {
            "competitions": [], "athletes": [], "results": [], "bouts": []
        }
        season_new = 0
        for i, c in enumerate(comps, 1):
            comp_id = c["competitionId"]
            competition_id = f"{season}-{comp_id}"
            if not force and competition_id in existing_ids:
                total_skip += 1
                continue
            try:
                tables = _scrape_one(client, season, comp_id, force=force)
            except Exception as e:
                total_fail += 1
                consecutive_fails += 1
                failures.append({"season": season, "comp_id": comp_id, "error": str(e)})
                print(f"[{season}] {i}/{len(comps)} FAIL {comp_id}: {e}", file=sys.stderr)
                if consecutive_fails >= max_consecutive_fails:
                    print(
                        f"aborting: {consecutive_fails} consecutive failures "
                        "(possible network/site issue)",
                        file=sys.stderr,
                    )
                    if season_new:
                        merged = {
                            name: pd.concat(dfs, ignore_index=True)
                            for name, dfs in season_tables.items()
                        }
                        _write_canonical(merged, CANONICAL_DIR)
                    _write_failures(failures)
                    print(
                        f"done (aborted): {total_ok} ok, {total_skip} skipped, "
                        f"{total_fail} failed",
                        file=sys.stderr,
                    )
                    return result(aborted=True)
                continue
            consecutive_fails = 0
            for name, df in tables.items():
                season_tables[name].append(df)
            existing_ids.add(competition_id)
            new_competition_ids.append(competition_id)
            season_new += 1
            total_ok += 1
            print(f"[{season}] {i}/{len(comps)} ok {comp_id} ({c.get('name')})", file=sys.stderr)

        if season_new:
            merged = {
                name: pd.concat(dfs, ignore_index=True) for name, dfs in season_tables.items()
            }
            _write_canonical(merged, CANONICAL_DIR)
            print(f"[{season}] flushed {season_new} new competition(s)", file=sys.stderr)

    _write_failures(failures)
    print(f"done: {total_ok} ok, {total_skip} skipped, {total_fail} failed", file=sys.stderr)
    return result(aborted=False)


def cmd_scrape_all(args: argparse.Namespace) -> int:
    """Bulk historical scrape: Senior Individual competitions across a season
    range, all weapons/genders. See `_scrape_seasons` for the resume, flush and
    list-refresh semantics."""
    client = FieClient()
    known_seasons = client.fetch_seasons()
    seasons = [s for s in range(args.from_season, args.to_season + 1) if s in known_seasons]
    if not seasons:
        print(
            f"no known season in range {args.from_season}-{args.to_season} "
            f"(fie.org knows {min(known_seasons)}-{max(known_seasons)})",
            file=sys.stderr,
        )
        return 1

    outcome = _scrape_seasons(
        client,
        seasons,
        weapon=args.weapon,
        gender=args.gender,
        force=args.force,
        max_consecutive_fails=args.max_consecutive_fails,
        refresh_lists=args.refresh_lists,
    )
    return 1 if outcome["aborted"] else 0


def _write_failures(failures: list[dict]) -> None:
    fail_path = Path("data/raw_cache/scrape_failures.json")
    if failures:
        fail_path.parent.mkdir(parents=True, exist_ok=True)
        fail_path.write_text(json.dumps(failures, indent=2))
        print(f"{len(failures)} failure(s) written to {fail_path}", file=sys.stderr)
    elif fail_path.exists():
        fail_path.unlink()


def _latest_canonical_season(out_dir: Path) -> int | None:
    path = out_dir / "competitions.parquet"
    if not path.exists():
        return None
    seasons = pd.read_parquet(path, columns=["season"])["season"]
    return int(seasons.max()) if len(seasons) else None


def _default_update_seasons(known_seasons: list[int], latest: int | None) -> list[int]:
    """Seasons `ffs update` scrapes when none are named: the newest season the
    archive already holds, plus the one after it. The `+1` is what makes the
    September season rollover work without anyone passing a flag — on 1 Sep the
    new season's first competitions appear under a season the archive has never
    seen. Both are intersected with fie.org's own season list, since
    `fetch_competitions_list` silently returns its *entire* table for an
    out-of-range season rather than an empty page."""
    if latest is None:
        return [max(known_seasons)] if known_seasons else []
    return [s for s in (latest, latest + 1) if s in known_seasons]


def cmd_update(args: argparse.Namespace) -> int:
    """Catch the archive up with recently-finished competitions: re-fetch the
    relevant season listing(s), scrape whatever is new, then recompute stats.

    This is the routine "a competition just finished" path; `scrape-all` is the
    bulk historical one. Note that a competition's `hasResults` flag in the
    season listing is `0` even for finished events, so it is deliberately not
    used as a gate — a competition that has no results simply fails to parse
    and is recorded in `data/raw_cache/scrape_failures.json`.
    """
    client = FieClient()
    known_seasons = client.fetch_seasons(force=True)

    if args.season:
        seasons = sorted(set(args.season))
        unknown = [s for s in seasons if s not in known_seasons]
        if unknown:
            print(
                f"season(s) {unknown} not in fie.org's known seasons "
                f"({min(known_seasons)}-{max(known_seasons)})",
                file=sys.stderr,
            )
            return 1
    else:
        seasons = _default_update_seasons(known_seasons, _latest_canonical_season(CANONICAL_DIR))
        if not seasons:
            print("nothing to update: no canonical data and no known seasons", file=sys.stderr)
            return 1

    print(f"updating season(s): {', '.join(str(s) for s in seasons)}", file=sys.stderr)
    outcome = _scrape_seasons(
        client,
        seasons,
        weapon=args.weapon,
        gender=args.gender,
        max_consecutive_fails=args.max_consecutive_fails,
        refresh_lists=True,
    )

    if outcome["ok"]:
        cmd_build_stats(args)
        _print_new_competitions(outcome["new_competition_ids"])
    else:
        print("no new competitions — stats left untouched", file=sys.stderr)

    if args.build_site and outcome["ok"]:
        cmd_build_site(args)

    if outcome["failed"]:
        print(
            f"{outcome['failed']} competition(s) failed — see "
            "data/raw_cache/scrape_failures.json",
            file=sys.stderr,
        )
        return 1
    return 0


def _print_new_competitions(competition_ids: list[str]) -> None:
    if not competition_ids:
        return
    comps = pd.read_parquet(CANONICAL_DIR / "competitions.parquet")
    added = comps[comps["competition_id"].isin(competition_ids)].sort_values("start_date")
    print(f"\n{len(added)} new competition(s):")
    for c in added.itertuples():
        print(
            f"  {c.competition_id:<12} {c.start_date}  {c.weapon}{c.gender}  "
            f"{c.level:<4} {c.name} ({c.city})"
        )


def cmd_discover(args: argparse.Namespace) -> int:
    client = FieClient()
    seasons = client.fetch_seasons(force=args.force)
    if args.season not in seasons:
        print(f"season {args.season} not in fie.org's known seasons ({min(seasons)}-{max(seasons)})", file=sys.stderr)
        return 1

    comps = list_competitions(
        client, args.season, weapon=args.weapon, gender=args.gender, force=args.force
    )
    comps.sort(key=lambda c: (c.get("startDate") or "", c.get("competitionId")))
    for c in comps:
        print(
            f"{c['season']}/{c['competitionId']}\t{c.get('startDate')}\t{c.get('weapon')}"
            f"{c.get('gender')}\t{c.get('hasResults')}\t{c.get('name')}"
        )
    print(f"{len(comps)} Senior Individual competition(s)", file=sys.stderr)
    return 0


def cmd_build_stats(args: argparse.Namespace) -> int:
    bouts = pd.read_parquet(CANONICAL_DIR / "bouts.parquet")
    results = pd.read_parquet(CANONICAL_DIR / "results.parquet")
    competitions = pd.read_parquet(CANONICAL_DIR / "competitions.parquet")

    stats_df = stats.compute_stats(bouts, results)
    ratings_history = elo.compute_elo(bouts, competitions)
    h2h_df, h2h_bouts_df = h2h.build_h2h(bouts, competitions)

    CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
    stats_df.to_parquet(CANONICAL_DIR / "stats_fencer_comp.parquet", index=False)
    ratings_history.to_parquet(CANONICAL_DIR / "ratings_history.parquet", index=False)
    h2h_df.to_parquet(CANONICAL_DIR / "h2h.parquet", index=False)
    h2h_bouts_df.to_parquet(CANONICAL_DIR / "h2h_bouts.parquet", index=False)

    print(f"stats_fencer_comp: {len(stats_df)} rows")
    print(f"ratings_history:   {len(ratings_history)} rows")
    print(f"h2h:               {len(h2h_df)} rows")
    print(f"h2h_bouts:         {len(h2h_bouts_df)} rows")
    return 0


def cmd_build_site(args: argparse.Namespace) -> int:
    report = build_site()
    total = 0
    print("site/data size report:")
    for path, size in report.items():
        total += size
        # The guardrail only applies to files a first visit actually fetches;
        # per-page files (shards, competitions, h2h, explore, paths) are lazy.
        flag = "  [!] >1.5MB eager file" if size > EAGER_SIZE_WARN_BYTES and is_eager(path) else ""
        print(f"  {path:45s} {size / 1024:8.1f} KB{flag}")
    print(f"  {'TOTAL':45s} {total / 1024:8.1f} KB")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    comp_path = CANONICAL_DIR / "competitions.parquet"
    if not comp_path.exists():
        print(f"{comp_path} does not exist yet -- run `ffs scrape-all` first", file=sys.stderr)
        return 1

    legacy_comps = load_legacy_competitions()
    canonical = pd.read_parquet(comp_path)
    matches = match_competitions(legacy_comps, canonical)

    matched = [m for m in matches if m["competition_id"] is not None]
    unmatched = [m for m in matches if m["competition_id"] is None]
    rate = len(matched) / len(matches) if matches else 0.0

    print(f"legacy competitions: {len(matches)}")
    print(f"matched:             {len(matched)} ({rate:.1%})")
    print(f"unmatched:           {len(unmatched)}")
    if unmatched:
        print("\nunmatched legacy competitions:")
        for m in unmatched:
            leg = m["legacy"]
            print(f"  {leg['date']}  {leg['weapon']}{leg['gender']}  {leg['comp']} ({leg['place']})")

    comp_ok = rate >= 0.95

    stats_path = CANONICAL_DIR / "stats_fencer_comp.parquet"
    if not stats_path.exists():
        print(f"\n{stats_path} does not exist yet -- run `ffs build-stats` for the parity report", file=sys.stderr)
        return 0 if comp_ok else 1

    legacy_results = load_legacy_results()
    stats_df = pd.read_parquet(stats_path)
    athletes = pd.read_parquet(CANONICAL_DIR / "athletes.parquet")
    parity = compute_parity(legacy_results, legacy_comps, canonical, stats_df, athletes)

    print(f"\nfencer parity: {parity['n_fencers']} matched fencer-rows across {parity['n_competitions']} competitions")
    for metric, value in parity["per_metric"].items():
        print(f"  {metric:8s} {value:.1%}")
    print(f"  {'overall':8s} {parity['overall_rate']:.1%}")

    parity_ok = parity["n_competitions"] >= 3 and parity["overall_rate"] >= 0.99
    return 0 if comp_ok and parity_ok else 1


def main() -> None:
    parser = argparse.ArgumentParser(prog="ffs", description="FencingFastStats CLI")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")

    scrape_parser = subparsers.add_parser("scrape", help="Scrape a competition from fie.org")
    scrape_parser.add_argument("--comp", required=True, help="Competition as SEASON/ID, e.g. 2025/242")
    scrape_parser.add_argument("--dump", action="store_true", help="Dump decoded query bodies to data/raw_cache/ for inspection")
    scrape_parser.add_argument("--force", action="store_true", help="Bypass the disk cache and re-fetch from fie.org")
    scrape_parser.set_defaults(func=cmd_scrape)

    discover_parser = subparsers.add_parser("discover", help="List Senior Individual competitions for a season")
    discover_parser.add_argument("--season", required=True, type=int)
    discover_parser.add_argument("--weapon", choices=["F", "E", "S"], help="Filter by weapon")
    discover_parser.add_argument("--gender", choices=["M", "F"], help="Filter by gender")
    discover_parser.add_argument("--force", action="store_true", help="Bypass the disk cache and re-fetch from fie.org")
    discover_parser.set_defaults(func=cmd_discover)

    scrape_all_parser = subparsers.add_parser(
        "scrape-all", help="Bulk-scrape Senior Individual competitions across a season range"
    )
    scrape_all_parser.add_argument("--from", dest="from_season", type=int, default=2002)
    scrape_all_parser.add_argument("--to", dest="to_season", type=int, default=2026)
    scrape_all_parser.add_argument("--weapon", choices=["F", "E", "S"], help="Filter by weapon")
    scrape_all_parser.add_argument("--gender", choices=["M", "F"], help="Filter by gender")
    scrape_all_parser.add_argument("--force", action="store_true", help="Re-fetch and re-scrape even if already in canonical parquet")
    scrape_all_parser.add_argument(
        "--refresh-lists", action="store_true",
        help="Re-fetch every season's competition listing (the newest season's is always re-fetched)",
    )
    scrape_all_parser.add_argument(
        "--max-consecutive-fails", type=int, default=15,
        help="Abort the run after this many consecutive per-competition failures",
    )
    scrape_all_parser.set_defaults(func=cmd_scrape_all)

    update_parser = subparsers.add_parser(
        "update", help="Scrape newly-finished competitions and rebuild stats"
    )
    update_parser.add_argument(
        "--season", type=int, action="append",
        help="Season to update (repeatable). Default: the newest season in canonical data, and the one after it",
    )
    update_parser.add_argument("--weapon", choices=["F", "E", "S"], help="Filter by weapon")
    update_parser.add_argument("--gender", choices=["M", "F"], help="Filter by gender")
    update_parser.add_argument(
        "--build-site", action="store_true",
        help="Also regenerate site/data/ afterwards (~23 min; CI does this on push)",
    )
    update_parser.add_argument(
        "--max-consecutive-fails", type=int, default=15,
        help="Abort the run after this many consecutive per-competition failures",
    )
    update_parser.set_defaults(func=cmd_update)

    validate_parser = subparsers.add_parser("validate", help="Competition-matching report against legacy CSV")
    validate_parser.set_defaults(func=cmd_validate)

    build_stats_parser = subparsers.add_parser("build-stats", help="Build stats/ELO/H2H tables from canonical parquet")
    build_stats_parser.set_defaults(func=cmd_build_stats)

    build_site_parser = subparsers.add_parser("build-site", help="Build site/data/*.json artifacts from canonical parquet")
    build_site_parser.set_defaults(func=cmd_build_site)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return
    if not hasattr(args, "func"):
        parser.error(f"'{args.command}' is not implemented yet")
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
