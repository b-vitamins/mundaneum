#!/usr/bin/env python3
"""
CLI script to import BibTeX files into Folio.

Usage:
    python import_bibtex.py /path/to/bib/directory

Or via Docker:
    docker compose exec backend python scripts/import_bibtex.py /data
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import async_session
from app.services.ingest import ingest_directory


async def main():
    if len(sys.argv) < 2:
        print("Usage: python import_bibtex.py <directory>")
        print("  Recursively imports all .bib files from the directory")
        sys.exit(1)

    directory = sys.argv[1]

    if not Path(directory).exists():
        print(f"Error: Directory not found: {directory}")
        sys.exit(1)

    print(f"Importing BibTeX files from: {directory}")

    async with async_session() as session:
        result = await ingest_directory(session, directory)

    print("\nImport complete!")
    print(f"  Parsed:   {result['total_parsed']} entries")
    print(f"  Imported: {result['imported']} entries")
    print(f"  Errors:   {result['errors']} entries")


if __name__ == "__main__":
    asyncio.run(main())
