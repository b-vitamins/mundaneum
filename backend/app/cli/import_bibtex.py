"""
CLI entrypoint for importing BibTeX directories.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.database import async_session
from app.services.ingest import ingest_directory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mundaneum-import-bibtex",
        description="Recursively import all BibTeX files from a directory.",
    )
    parser.add_argument("directory", help="Directory containing .bib files")
    return parser


async def import_directory(directory: str) -> int:
    target = Path(directory)
    if not target.exists():
        print(f"Error: Directory not found: {target}")
        return 1

    print(f"Importing BibTeX files from: {target}")
    async with async_session() as session:
        result = await ingest_directory(session, str(target))

    print("\nImport complete!")
    print(f"  Parsed:   {result['total_parsed']} entries")
    print(f"  Imported: {result['imported']} entries")
    print(f"  Errors:   {result['errors']} entries")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(import_directory(args.directory))


def run() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    run()
