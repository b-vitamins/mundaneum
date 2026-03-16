import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modeling.concept_models import NerBundle, NerCooccurrenceEdge
from app.modeling.ner_models import NerEntity


@pytest.mark.asyncio
async def test_concepts_list_bundles(client: AsyncClient, db_session: AsyncSession):
    bundle_one_index = 990001
    bundle_two_index = 990002
    db_session.add_all(
        [
            NerBundle(
                bundle_index=bundle_one_index,
                bundle_id="bundle_1",
                size=99999,
                venue_count=2,
                venue_coverage=["neurips", "iclr"],
                top_entities=[],
                yearly_paper_counts={"2022": 10, "2023": 20},
                previous_year_papers=10,
            ),
            NerBundle(
                bundle_index=bundle_two_index,
                bundle_id="bundle_2",
                size=99998,
                venue_count=5,
                venue_coverage=["icml"],
                top_entities=[],
                yearly_paper_counts={"2022": 30, "2023": 15},
                previous_year_papers=30,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/concepts/bundles?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["bundle_index"] == bundle_one_index
    assert data[1]["bundle_index"] == bundle_two_index
    assert data[0]["growth_indicator"] == "growing"
    assert data[1]["growth_indicator"] == "declining"


@pytest.mark.asyncio
async def test_concepts_get_bundle(client: AsyncClient, db_session: AsyncSession):
    bundle_index = 990042
    db_session.add(
        NerBundle(
            bundle_index=bundle_index,
            bundle_id="bundle_42",
            size=5,
            venue_count=1,
            venue_coverage=["cvpr"],
            members=["task|ent1", "method|ent2"],
            top_entities=[],
            yearly_paper_counts={"2023": 100},
            previous_year_papers=50,
        )
    )
    await db_session.commit()

    response = await client.get(f"/api/concepts/bundles/{bundle_index}")
    assert response.status_code == 200
    data = response.json()
    assert data["bundle_index"] == bundle_index
    assert data["bundle_id"] == "bundle_42"
    assert data["members"] == ["task|ent1", "method|ent2"]

    response = await client.get("/api/concepts/bundles/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_concepts_entity_neighbors(client: AsyncClient, db_session: AsyncSession):
    db_session.add_all(
        [
            NerEntity(canonical_id="L", canonical_surface="Left Entity", label="task"),
            NerEntity(canonical_id="R1", canonical_surface="Right Entity 1", label="method"),
            NerEntity(canonical_id="R2", canonical_surface="Right Entity 2", label="metric"),
        ]
    )
    db_session.add_all(
        [
            NerCooccurrenceEdge(
                left_node="task|L",
                right_node="method|R1",
                left_label="task",
                right_label="method",
                paper_count=10,
                venue="neurips",
                year=2023,
            ),
            NerCooccurrenceEdge(
                left_node="metric|R2",
                right_node="task|L",
                left_label="metric",
                right_label="task",
                paper_count=5,
                venue="icml",
                year=2023,
            ),
            NerCooccurrenceEdge(
                left_node="task|L",
                right_node="method|R1",
                left_label="task",
                right_label="method",
                paper_count=2,
                venue="neurips",
                year=2022,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/concepts/neighbors/L")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["canonical_id"] == "R1"
    assert data[0]["paper_count"] == 12
    assert data[0]["canonical_surface"] == "Right Entity 1"
    assert data[1]["canonical_id"] == "R2"
    assert data[1]["paper_count"] == 5
    assert data[1]["canonical_surface"] == "Right Entity 2"

    response = await client.get("/api/concepts/neighbors/L?year=2023")
    data = response.json()
    assert len(data) == 2
    assert data[0]["canonical_id"] == "R1"
    assert data[0]["paper_count"] == 10


@pytest.mark.asyncio
async def test_concepts_cooccurrence_edges(
    client: AsyncClient,
    db_session: AsyncSession,
):
    venue_filter = "unit_edges_venue_1b2c"
    db_session.add_all(
        [
            NerCooccurrenceEdge(
                left_node="task|A",
                right_node="method|B",
                left_label="task",
                right_label="method",
                paper_count=20,
                venue=venue_filter,
                year=2023,
            ),
            NerCooccurrenceEdge(
                left_node="task|A",
                right_node="dataset|C",
                left_label="task",
                right_label="dataset",
                paper_count=10,
                venue=venue_filter,
                year=2023,
            ),
            NerCooccurrenceEdge(
                left_node="dataset|C",
                right_node="metric|D",
                left_label="dataset",
                right_label="metric",
                paper_count=5,
                venue=venue_filter,
                year=2022,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(f"/api/concepts/edges?venue={venue_filter}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["paper_count"] == 20
    assert data[1]["paper_count"] == 10
    assert data[2]["paper_count"] == 5

    response = await client.get(f"/api/concepts/edges?canonical_id=C&venue={venue_filter}")
    data = response.json()
    assert len(data) == 2

    response = await client.get(
        f"/api/concepts/edges?min_paper_count=15&venue={venue_filter}"
    )
    data = response.json()
    assert len(data) == 1
    assert data[0]["left_node"] == "task|A"
    assert data[0]["right_node"] == "method|B"


@pytest.mark.asyncio
async def test_concepts_edges_canonical_id_escapes_like_wildcards(
    client: AsyncClient,
    db_session: AsyncSession,
):
    db_session.add_all(
        [
            NerCooccurrenceEdge(
                left_node="task|A_B",
                right_node="method|X",
                left_label="task",
                right_label="method",
                paper_count=8,
                venue="neurips",
                year=2023,
            ),
            NerCooccurrenceEdge(
                left_node="task|A1B",
                right_node="method|Y",
                left_label="task",
                right_label="method",
                paper_count=7,
                venue="neurips",
                year=2023,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/concepts/edges?canonical_id=A_B")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["left_node"] == "task|A_B"
