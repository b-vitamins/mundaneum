from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models import Entry, S2Paper
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
    service = S2Service()

    # Mock data structure using SimpleNamespace
    mock_data = SimpleNamespace(
        paperId="s2-123",
        title="Rich Paper",
        year=2024,
        venue="ArXiv",
        authors=[SimpleNamespace(authorId="a1", name="Alice")],
        tldr=SimpleNamespace(model="v1", text="Startling discovery."),
        embedding=SimpleNamespace(model="v1", vector=[0.1, 0.2]),
        citationCount=10,
        referenceCount=5,
        influentialCitationCount=1,
        isOpenAccess=True,
        openAccessPdf=None,
        fieldsOfStudy=["CS"],
        publicationTypes=["Journal"],
        externalIds={"ArXiv": "1234.5678"},
        citations=[],
        references=[],
    )

    await service._upsert_s2_paper(db_session, mock_data)
    await db_session.commit()

    # Verify
    result = await db_session.execute(select(S2Paper).where(S2Paper.s2_id == "s2-123"))
    paper = result.scalar_one()
    assert paper.title == "Rich Paper"
    assert paper.tldr["text"] == "Startling discovery."
    # Check JSON structure
    assert isinstance(paper.authors, list)
    assert paper.authors[0]["name"] == "Alice"
