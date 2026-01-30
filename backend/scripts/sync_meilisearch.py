#!/usr/bin/env python3
"""Sync all entries from PostgreSQL to Meilisearch.

This script re-syncs all entries from the database to Meilisearch.
Useful for rebuilding the search index or after schema changes.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models import Entry, EntryAuthor
from app.services.sync import (
    FILTERABLE_ATTRS,
    INDEX_NAME,
    SEARCHABLE_ATTRS,
    SORTABLE_ATTRS,
    entry_to_document,
    get_client,
)


async def get_all_entries():
    """Fetch all entries with authors from database."""
    async with async_session() as session:
        result = await session.execute(
            select(Entry).options(
                selectinload(Entry.authors).selectinload(EntryAuthor.author)
            )
        )
        return result.scalars().all()


async def main():
    print("Fetching entries from PostgreSQL...")
    entries = await get_all_entries()
    print(f"Found {len(entries)} entries")

    if not entries:
        print("No entries to sync")
        return

    # Convert to documents using the shared function
    print("Converting to Meilisearch documents...")
    docs = [entry_to_document(e) for e in entries]

    # Connect and configure index using shared settings
    print("Connecting to Meilisearch...")
    client = get_client()
    index = client.index(INDEX_NAME)

    # Configure index with shared attribute lists
    print("Configuring index...")
    index.update_searchable_attributes(SEARCHABLE_ATTRS)
    index.update_filterable_attributes(FILTERABLE_ATTRS)
    index.update_sortable_attributes(SORTABLE_ATTRS)

    # Add documents in batches
    batch_size = 500
    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        print(f"Syncing batch {i // batch_size + 1} ({len(batch)} documents)...")
        task = index.add_documents(batch)
        print(f"  Task {task.task_uid} enqueued")

    print(f"\nDone! Synced {len(docs)} entries to Meilisearch")
    print("Note: Indexing happens in the background, search may take a moment to work")


if __name__ == "__main__":
    asyncio.run(main())
