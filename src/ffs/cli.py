import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from ffs import __version__
from ffs import devalue, schema
from ffs.discover import list_competitions
from ffs.fie_client import FieClient
from ffs.parse import parse_competition
from ffs.validate_legacy import load_legacy_competitions, match_competitions

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
    if issues:
        raise ValueError("validate_tables() found issues: " + "; ".join(issues))
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


def cmd_scrape_all(args: argparse.Namespace) -> int:
    """Bulk historical scrape: Senior Individual competitions across a season
    range, all weapons/genders. Resumable — competitions already present in
    `data/canonical/competitions.parquet` are skipped (unless `--force`), and
    `FieClient`'s disk cache means a crashed/interrupted run mostly replays
    from cache on the next invocation rather than re-hitting fie.org.

    Writes are flushed once per season (not per competition) to keep parquet
    read/concat/write overhead bounded across ~3000 competitions; a crash
    mid-season loses that season's progress but it replays fast from cache.
    """
    client = FieClient()
    known_seasons = client.fetch_seasons()
    seasons = [s for s in range(args.from_season, args.to_season + 1) if s in known_seasons]

    existing_ids = _existing_competition_ids(CANONICAL_DIR)
    total_ok = total_skip = total_fail = 0
    failures: list[dict] = []
    consecutive_fails = 0

    for season in seasons:
        comps = list_competitions(client, season, weapon=args.weapon, gender=args.gender)
        season_tables: dict[str, list[pd.DataFrame]] = {
            "competitions": [], "athletes": [], "results": [], "bouts": []
        }
        season_new = 0
        for i, c in enumerate(comps, 1):
            comp_id = c["competitionId"]
            competition_id = f"{season}-{comp_id}"
            if not args.force and competition_id in existing_ids:
                total_skip += 1
                continue
            try:
                tables = _scrape_one(client, season, comp_id, force=args.force)
            except Exception as e:
                total_fail += 1
                consecutive_fails += 1
                failures.append({"season": season, "comp_id": comp_id, "error": str(e)})
                print(f"[{season}] {i}/{len(comps)} FAIL {comp_id}: {e}", file=sys.stderr)
                if consecutive_fails >= args.max_consecutive_fails:
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
                    return 1
                continue
            consecutive_fails = 0
            for name, df in tables.items():
                season_tables[name].append(df)
            existing_ids.add(competition_id)
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
    return 0


def _write_failures(failures: list[dict]) -> None:
    fail_path = Path("data/raw_cache/scrape_failures.json")
    if failures:
        fail_path.parent.mkdir(parents=True, exist_ok=True)
        fail_path.write_text(json.dumps(failures, indent=2))
        print(f"{len(failures)} failure(s) written to {fail_path}", file=sys.stderr)
    elif fail_path.exists():
        fail_path.unlink()


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

    return 0 if rate >= 0.95 else 1


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
        "--max-consecutive-fails", type=int, default=15,
        help="Abort the run after this many consecutive per-competition failures",
    )
    scrape_all_parser.set_defaults(func=cmd_scrape_all)

    validate_parser = subparsers.add_parser("validate", help="Competition-matching report against legacy CSV")
    validate_parser.set_defaults(func=cmd_validate)

    subparsers.add_parser("build-stats", help="Build stats/ELO/H2H tables (not yet implemented)")

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return
    if not hasattr(args, "func"):
        parser.error(f"'{args.command}' is not implemented yet")
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
