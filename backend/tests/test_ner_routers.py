import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modeling.library_models import Entry, EntryType
from app.modeling.ner_models import EntryNerEntity, NerEntity


@pytest.mark.asyncio
async def test_ner_entities_list(client: AsyncClient, db_session: AsyncSession):
    label = "unit_entities_list_label_3f11"
    db_session.add_all(
        [
            NerEntity(
                canonical_id="test_id_1",
                canonical_surface="Test Entity 1",
                label=label,
                paper_hits=10,
            ),
            NerEntity(
                canonical_id="test_id_2",
                canonical_surface="Test Entity 2",
                label=label,
                paper_hits=5,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(f"/api/ner/entities?label={label}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["canonical_id"] == "test_id_1"
    assert data[1]["canonical_id"] == "test_id_2"

    response = await client.get("/api/ner/entities?label=unit_entities_list_absent")
    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_ner_entity_labels(client: AsyncClient, db_session: AsyncSession):
    method_label = "unit_label_method_7a22"
    task_label = "unit_label_task_7a22"
    db_session.add_all(
        [
            NerEntity(
                canonical_id="lbl_method_1",
                canonical_surface="Method A",
                label=method_label,
                paper_hits=10,
            ),
            NerEntity(
                canonical_id="lbl_method_2",
                canonical_surface="Method B",
                label=method_label,
                paper_hits=5,
            ),
            NerEntity(
                canonical_id="lbl_task_1",
                canonical_surface="Task A",
                label=task_label,
                paper_hits=2,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/ner/labels")
    assert response.status_code == 200
    data = {row["label"]: row for row in response.json()}
    assert data[method_label]["entities"] == 2
    assert data[method_label]["paper_hits"] == 15
    assert data[task_label]["entities"] == 1
    assert data[task_label]["paper_hits"] == 2


@pytest.mark.asyncio
async def test_ner_entity_detail(client: AsyncClient, db_session: AsyncSession):
    db_session.add(
        NerEntity(
            canonical_id="test_id_detail",
            canonical_surface="Test Detail Entity",
            label="dataset",
            first_year=2020,
            last_year=2023,
            paper_hits=15,
            mention_total=40,
            venue_count=2,
            venues=["neurips", "iclr"],
            years_active=4,
        )
    )
    await db_session.commit()

    response = await client.get("/api/ner/entities/test_id_detail")
    assert response.status_code == 200
    data = response.json()
    assert data["canonical_surface"] == "Test Detail Entity"
    assert data["venues"] == ["neurips", "iclr"]

    response = await client.get("/api/ner/entities/does_not_exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_ner_entity_entries(client: AsyncClient, db_session: AsyncSession):
    entity = NerEntity(
        canonical_id="test_e_entries",
        canonical_surface="Entity Entries",
        label="method",
    )
    entry1 = Entry(
        citation_key="entry_1",
        entry_type=EntryType.ARTICLE,
        title="Paper 1",
        year=2021,
        source_file="test.bib",
    )
    entry2 = Entry(
        citation_key="entry_2",
        entry_type=EntryType.ARTICLE,
        title="Paper 2",
        year=2022,
        source_file="test.bib",
    )
    db_session.add_all([entity, entry1, entry2])
    await db_session.flush()

    db_session.add_all(
        [
            EntryNerEntity(
                entry_id=entry1.id,
                ner_entity_id=entity.id,
                label=entity.label,
                confidence=0.9,
            ),
            EntryNerEntity(
                entry_id=entry2.id,
                ner_entity_id=entity.id,
                label=entity.label,
                confidence=0.8,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(f"/api/ner/entities/{entity.canonical_id}/entries")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["title"] == "Paper 2"
    assert data[1]["title"] == "Paper 1"


@pytest.mark.asyncio
async def test_ner_entry_entities(client: AsyncClient, db_session: AsyncSession):
    entity1 = NerEntity(canonical_id="lbl1", canonical_surface="L1", label="task")
    entity2 = NerEntity(canonical_id="lbl2", canonical_surface="L2", label="method")
    entry = Entry(
        citation_key="entry_facts",
        entry_type=EntryType.ARTICLE,
        title="Paper Facts",
        source_file="test.bib",
    )
    db_session.add_all([entity1, entity2, entry])
    await db_session.flush()

    db_session.add_all(
        [
            EntryNerEntity(
                entry_id=entry.id,
                ner_entity_id=entity1.id,
                label=entity1.label,
                confidence=0.95,
            ),
            EntryNerEntity(
                entry_id=entry.id,
                ner_entity_id=entity2.id,
                label=entity2.label,
                confidence=0.85,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(f"/api/ner/entries/{entry.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["canonical_id"] == "lbl1"
    assert data[1]["canonical_id"] == "lbl2"
