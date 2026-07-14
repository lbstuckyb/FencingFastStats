import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from ffs import __version__
from ffs import devalue, schema
from ffs.fie_client import FieClient
from ffs.parse import parse_competition

CANONICAL_DIR = Path("data/canonical")


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
    comp = client.fetch_competition(season, comp_id, force=args.force)
    decoded = devalue.unflatten(comp["raw"])
    queries = devalue.extract_queries(decoded)
    ranking_items = client.fetch_results_ranking(season, comp_id, force=args.force)

    if args.dump:
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
        print("validate_tables() found issues:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return 1

    _write_canonical(tables, CANONICAL_DIR)
    for name, df in tables.items():
        print(f"{name}: {len(df)} rows")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="ffs", description="FencingFastStats CLI")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")

    scrape_parser = subparsers.add_parser("scrape", help="Scrape a competition from fie.org")
    scrape_parser.add_argument("--comp", required=True, help="Competition as SEASON/ID, e.g. 2025/242")
    scrape_parser.add_argument("--dump", action="store_true", help="Dump decoded query bodies to data/raw_cache/ for inspection")
    scrape_parser.add_argument("--force", action="store_true", help="Bypass the disk cache and re-fetch from fie.org")
    scrape_parser.set_defaults(func=cmd_scrape)

    subparsers.add_parser("build-stats", help="Build stats/ELO/H2H tables (not yet implemented)")
    subparsers.add_parser("validate", help="Validate parity against legacy data (not yet implemented)")

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return
    if not hasattr(args, "func"):
        parser.error(f"'{args.command}' is not implemented yet")
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
