"""
CLI entrypoint for importing BibTeX directories.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.app_context import build_app_context
from app.config import settings
from app.services.ingest import ingest_directory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mundaneum-import-bibtex",
        description="Import BibTeX from an explicit directory or the configured bibliography repository.",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        help="Directory containing .bib files. Omit to sync from the configured bibliography repository.",
    )
    return parser


async def import_directory(directory: str | None) -> int:
    context = build_app_context()
    if directory is None:
        target = await context.services.bibliography.repository.ensure_checkout(
            refresh=settings.bibliography_runtime_sync_enabled
        )
    else:
        target = Path(directory)
        if not target.exists():
            print(f"Error: Directory not found: {target}")
            await context.services.database.engine.dispose()
            await context.services.s2_runtime.close()
            return 1

    print(f"Importing BibTeX files from: {target}")
    session_factory = context.services.database.session_factory
    async with session_factory() as session:
        result = await ingest_directory(
            session,
            target,
            search_index=context.services.search.indexer,
            event_bus=context.events,
        )

    await context.services.database.engine.dispose()
    await context.services.s2_runtime.close()

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
