from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models import Entry
from app.models import S2Paper as S2PaperModel
from app.schemas.s2 import S2Author, S2Embedding, S2TLDR
from app.schemas.s2 import S2Paper as S2PaperSchema
from app.services.s2 import S2Service


@pytest.mark.asyncio
async def test_resolve_s2_id_search(db_session):
    # Mock semanticscholar
    with patch("app.services.s2.SemanticScholar") as MockSch:
        mock_instance = MockSch.return_value
        # Mock search result
        mock_paper = SimpleNamespace(paperId="s2-123")
        mock_instance.search_paper.return_value = [mock_paper]

        service = S2Service()

        # Create entry without s2_id
        import uuid

        from app.models import EntryType

        entry = Entry(
            title="Test Paper",
            citation_key=f"test_{uuid.uuid4()}",
            entry_type=EntryType.ARTICLE,
            source_file="test.bib",
        )
        db_session.add(entry)
        await db_session.commit()
        await db_session.refresh(entry)

        # Test resolution
        s2_id = await service.resolve_s2_id(entry, db_session)
        assert s2_id == "s2-123"
        assert entry.s2_id == "s2-123"


@pytest.mark.asyncio
async def test_upsert_s2_paper(db_session):
    import uuid

    service = S2Service()

    # Use unique ID for test isolation
    test_s2_id = f"s2-upsert-{uuid.uuid4().hex[:8]}"

    # Use proper Pydantic models that support model_dump()
    mock_data = S2PaperSchema(
        paperId=test_s2_id,
        title="Rich Paper",
        year=2024,
        venue="ArXiv",
        authors=[S2Author(authorId="a1", name="Alice")],
        tldr=S2TLDR(model="v1", text="Startling discovery."),
        embedding=S2Embedding(model="v1", vector=[0.1, 0.2]),
        citationCount=10,
        referenceCount=5,
        influentialCitationCount=1,
        isOpenAccess=True,
        openAccessPdf=None,
        fieldsOfStudy=["CS"],
        publicationTypes=["Journal"],
        externalIds={"ArXiv": "1234.5678"},
    )

    await service._upsert_s2_paper(db_session, mock_data)
    await db_session.commit()

    # Verify using the SQLAlchemy model
    result = await db_session.execute(
        select(S2PaperModel).where(S2PaperModel.s2_id == test_s2_id)
    )
    paper = result.scalar_one()
    assert paper.title == "Rich Paper"
    assert paper.tldr["text"] == "Startling discovery."
    # Check JSON structure
    assert isinstance(paper.authors, list)
    assert paper.authors[0]["name"] == "Alice"
