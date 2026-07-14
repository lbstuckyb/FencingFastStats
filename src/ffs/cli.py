import argparse

from ffs import __version__


def main() -> None:
    parser = argparse.ArgumentParser(prog="ffs", description="FencingFastStats CLI")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("scrape", help="Scrape a competition from fie.org (not yet implemented)")
    subparsers.add_parser("build-stats", help="Build stats/ELO/H2H tables (not yet implemented)")
    subparsers.add_parser("validate", help="Validate parity against legacy data (not yet implemented)")

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return
    parser.error(f"'{args.command}' is not implemented yet")


if __name__ == "__main__":
    main()
