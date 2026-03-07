import asyncio
import logging
import sys

# Add backend directory to path
sys.path.append("/app")

from sqlalchemy import select

from app.database import async_session
from app.models import Entry, S2Citation, S2Paper
from app.services.s2 import sync_entry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting S2 Backend Verification...")

    # 1. Create a dummy entry or find existing one
    async with async_session() as session:
        # Check for "Attention Is All You Need" entry
        stmt = select(Entry).where(Entry.title == "Attention Is All You Need")
        result = await session.execute(stmt)
        entry = result.scalar_one_or_none()

        if not entry:
            logger.error(
                "Entry 'Attention Is All You Need' not found in DB. Please import it first."
            )
            return

        logger.info(f"Found Entry: {entry.title} (ID: {entry.id})")
        entry_id = str(entry.id)

    # 2. Trigger Sync
    logger.info("Triggering sync_entry...")
    status = await sync_entry(entry_id)
    logger.info("Sync status: %s", status.value)

    # 3. Verify Data
    async with async_session() as session:
        # Re-fetch entry to check s2_id
        entry = await session.get(Entry, entry_id)
        if not entry.s2_id:
            logger.error("FAILURE: Entry.s2_id is still None after sync.")
        else:
            logger.info(f"SUCCESS: Entry.s2_id updated to {entry.s2_id}")

            # Check S2Paper
            s2_paper = await session.get(S2Paper, entry.s2_id)
            if s2_paper:
                logger.info(f"SUCCESS: Found S2Paper: {s2_paper.title}")
                logger.info(f"  - Citation Count: {s2_paper.citation_count}")
            else:
                logger.error("FAILURE: S2Paper record not found.")

            # Check Citations
            stmt = select(S2Citation).where(S2Citation.target_id == entry.s2_id)
            result = await session.execute(stmt)
            citations = result.scalars().all()
            logger.info(f"Found {len(citations)} citations in DB.")

            if citations:
                logger.info(f"Sample Citation: {citations[0].source_id}")
                # Check if we have the source paper for the citation
                stmt_source = select(S2Paper).where(
                    S2Paper.s2_id == citations[0].source_id
                )
                res_source = await session.execute(stmt_source)
                source_paper = res_source.scalar_one_or_none()
                if source_paper:
                    logger.info(
                        f"SUCCESS: Found Source Paper for citation: {source_paper.title}"
                    )
                else:
                    logger.warning(
                        "WARNING: Source Paper for citation not found (Validation of shadow graph)."
                    )
            else:
                logger.warning(
                    "WARNING: No citations found. This might be correct if purely new or API failed silently."
                )


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
