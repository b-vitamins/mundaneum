"""
CLI entrypoint for rebuilding the Meilisearch index.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.app_context import build_app_context
from app.models import Entry, EntryAuthor
from app.services.sync import (
    FILTERABLE_ATTRS,
    INDEX_NAME,
    SEARCHABLE_ATTRS,
    SORTABLE_ATTRS,
    SearchIndexService,
    entry_to_document,
)


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="mundaneum-sync-meilisearch",
        description="Sync all PostgreSQL entries into the Meilisearch index.",
    )


async def get_all_entries(context):
    session_factory = context.services.database.session_factory
    async with session_factory() as session:
        result = await session.execute(
            select(Entry).options(
                selectinload(Entry.authors).selectinload(EntryAuthor.author)
            )
        )
        return result.scalars().all()


async def sync_index() -> int:
    print("Fetching entries from PostgreSQL...")
    context = build_app_context()
    entries = await get_all_entries(context)
    print(f"Found {len(entries)} entries")

    if not entries:
        print("No entries to sync")
        await context.services.database.engine.dispose()
        await context.services.s2_runtime.close()
        return 0

    print("Converting to Meilisearch documents...")
    docs = [entry_to_document(entry) for entry in entries]

    print("Connecting to Meilisearch...")
    search_index: SearchIndexService = context.services.search.indexer
    client = search_index.client
    index = client.index(INDEX_NAME)

    print("Configuring index...")
    index.update_searchable_attributes(SEARCHABLE_ATTRS)
    index.update_filterable_attributes(FILTERABLE_ATTRS)
    index.update_sortable_attributes(SORTABLE_ATTRS)

    batch_size = 500
    for index_offset in range(0, len(docs), batch_size):
        batch = docs[index_offset : index_offset + batch_size]
        print(
            f"Syncing batch {index_offset // batch_size + 1} ({len(batch)} documents)..."
        )
        task = index.add_documents(batch)
        print(f"  Task {task.task_uid} enqueued")

    print(f"\nDone! Synced {len(docs)} entries to Meilisearch")
    print("Note: indexing happens in the background, search may take a moment to work")
    await context.services.database.engine.dispose()
    await context.services.s2_runtime.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return asyncio.run(sync_index())


def run() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    run()
