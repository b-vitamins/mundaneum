import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modeling.trend_models import NerCrossVenueFlow, NerEmergence, NerTrend


@pytest.mark.asyncio
async def test_trends_stats(client: AsyncClient, db_session: AsyncSession):
    before = (await client.get("/api/trends/stats")).json()
    db_session.add_all(
        [
            NerTrend(
                canonical_id="us_c1_4d9f",
                canonical_surface="A",
                label="us_method",
                venue="us_nv",
                year=2022,
                node_key="us_method|us_c1_4d9f",
            ),
            NerTrend(
                canonical_id="us_c1_4d9f",
                canonical_surface="A",
                label="us_method",
                venue="us_iv",
                year=2023,
                node_key="us_method|us_c1_4d9f",
            ),
            NerTrend(
                canonical_id="us_c2_4d9f",
                canonical_surface="B",
                label="us_task",
                venue="us_nv",
                year=2023,
                node_key="us_task|us_c2_4d9f",
            ),
            NerEmergence(
                canonical_id="us_c2_4d9f",
                canonical_surface="B",
                label="us_task",
                venue="us_nv",
                year=2023,
                node_key="us_task|us_c2_4d9f",
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/trends/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_entities"] == before["total_entities"] + 2
    assert data["total_trend_rows"] == before["total_trend_rows"] + 3
    assert data["emerging_count"] == before["emerging_count"] + 1
    assert "us_iv" in set(data["venues"])
    assert "us_nv" in set(data["venues"])
    assert "us_method" in set(data["labels"])
    assert "us_task" in set(data["labels"])
    assert data["year_range"][0] <= 2022 <= data["year_range"][1]
    assert data["year_range"][0] <= 2023 <= data["year_range"][1]


@pytest.mark.asyncio
async def test_trends_movers(client: AsyncClient, db_session: AsyncSession):
    label_method = "um_meth"
    label_task = "um_task"
    venue_method = "um_nv"
    venue_task = "um_iv"
    target_year = 2099
    db_session.add_all(
        [
            NerTrend(
                canonical_id="um_c1",
                canonical_surface="Entity 1",
                label=label_method,
                venue=venue_method,
                year=target_year,
                momentum=0.5,
                prevalence=0.01,
                change_direction="rising",
                node_key=f"{label_method}|um_c1",
            ),
            NerTrend(
                canonical_id="um_c2",
                canonical_surface="Entity 2",
                label=label_task,
                venue=venue_task,
                year=target_year,
                momentum=-0.2,
                prevalence=0.02,
                change_direction="falling",
                node_key=f"{label_task}|um_c2",
            ),
            NerTrend(
                canonical_id="um_c1",
                canonical_surface="Entity 1",
                label=label_method,
                venue=venue_method,
                year=target_year - 1,
                momentum=0.1,
                node_key=f"{label_method}|um_c1",
            ),  # Older year
        ]
    )
    await db_session.commit()

    response = await client.get(
        f"/api/trends/movers?year={target_year}&venue={venue_method}&direction=rising"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["canonical_id"] == "um_c1"

    response = await client.get(
        f"/api/trends/movers?year={target_year}&venue={venue_task}&direction=falling"
    )
    data = response.json()
    assert len(data) == 1
    assert data[0]["canonical_id"] == "um_c2"

    response = await client.get(f"/api/trends/movers?year={target_year}&limit=10")
    data = response.json()
    canonical_ids = [row["canonical_id"] for row in data]
    assert "um_c1" in canonical_ids
    assert "um_c2" in canonical_ids


@pytest.mark.asyncio
async def test_trends_sparkline(client: AsyncClient, db_session: AsyncSession):
    db_session.add_all(
        [
            NerTrend(
                canonical_id="cs1",
                canonical_surface="S",
                label="method",
                venue="neurips",
                year=2022,
                prevalence=0.1,
                node_key="method|cs1",
            ),
            NerTrend(
                canonical_id="cs1",
                canonical_surface="S",
                label="method",
                venue="neurips",
                year=2023,
                prevalence=0.2,
                node_key="method|cs1",
            ),
            NerTrend(
                canonical_id="cs1",
                canonical_surface="S",
                label="method",
                venue="icml",
                year=2023,
                prevalence=0.15,
                node_key="method|cs1",
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/trends/sparkline/cs1")
    assert response.status_code == 200
    data = response.json()
    assert data["canonical_id"] == "cs1"
    assert len(data["points"]) == 3

    # Order should be year asc, venue asc
    assert data["points"][0]["year"] == 2022
    assert data["points"][1]["year"] == 2023
    assert data["points"][1]["venue"] == "icml"
    assert data["points"][2]["year"] == 2023
    assert data["points"][2]["venue"] == "neurips"

    # 404 test
    response = await client.get("/api/trends/sparkline/doesnotexist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_trends_emergence(client: AsyncClient, db_session: AsyncSession):
    emergence_venue = "ue_v6f01"
    db_session.add_all(
        [
            NerEmergence(
                canonical_id="e1",
                canonical_surface="E1",
                label="task",
                venue=emergence_venue,
                year=2023,
                emergence_score=0.9,
                node_key="task|e1",
            ),
            NerEmergence(
                canonical_id="e2",
                canonical_surface="E2",
                label="method",
                venue=emergence_venue,
                year=2023,
                emergence_score=0.95,
                node_key="method|e2",
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(f"/api/trends/emergence?venue={emergence_venue}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Sort by emergence_score desc
    assert data[0]["canonical_id"] == "e2"
    assert data[1]["canonical_id"] == "e1"

    # Filter by label
    response = await client.get(
        f"/api/trends/emergence?label=task&venue={emergence_venue}"
    )
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_trends_cross_venue_flow(client: AsyncClient, db_session: AsyncSession):
    flow_label = "uf_l9c20"
    db_session.add_all(
        [
            NerCrossVenueFlow(
                canonical_id="f1",
                canonical_surface="F1",
                label=flow_label,
                source_venue="neurips",
                source_year=2021,
                target_venue="icml",
                target_year=2022,
                transfer_score=0.8,
                node_key=f"{flow_label}|f1",
            ),
            NerCrossVenueFlow(
                canonical_id="f2",
                canonical_surface="F2",
                label=flow_label,
                source_venue="iclr",
                source_year=2022,
                target_venue="neurips",
                target_year=2023,
                transfer_score=0.9,
                node_key=f"{flow_label}|f2",
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(f"/api/trends/flow?label={flow_label}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Sort by transfer score desc
    assert data[0]["canonical_id"] == "f2"
    assert data[1]["canonical_id"] == "f1"

    # Filter by target_venue
    response = await client.get(f"/api/trends/flow?target_venue=icml&label={flow_label}")
    data = response.json()
    assert len(data) == 1
    assert data[0]["source_venue"] == "neurips"
