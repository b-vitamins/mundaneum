import json
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modeling.concept_models import NerBundle, NerCooccurrenceEdge
from app.modeling.library_models import Entry, EntryType
from app.modeling.ner_models import EntryNerEntity, NerEntity, NerRelease
from app.modeling.trend_models import NerCrossVenueFlow, NerEmergence, NerTrend
from app.services import ner_ingest as ner_ingest_service
from app.services.ner_ingest import resolve_signals_release_dir


@pytest.fixture
def mock_release_dir(tmp_path: Path) -> Path:
    """Create a minimal but schema-accurate signals-product release directory."""
    release_dir = tmp_path / "signals"
    release_dir.mkdir()

    (release_dir / "manifest.json").write_text(
        json.dumps(
            {
                "product_id": "folio-signals-v1",
                "run_id": "test_run",
                "entries_seen": 1,
                "mentions_seen": 1,
            }
        ),
        encoding="utf-8",
    )

    (release_dir / "entity_atlas.jsonl").write_text(
        json.dumps(
            {
                "canonical_id": "ent1",
                "canonical_surface": "Entity 1",
                "label": "task",
                "mention_total": 100,
                "paper_hits": 50,
                "first_year": 2020,
                "last_year": 2023,
                "years_active": 3,
                "venues": ["neurips"],
                "venue_count": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    (release_dir / "paper_entity_facts.jsonl").write_text(
        json.dumps(
            {
                "citation_key": "key_A",
                "canonical_id": "ent1",
                "label": "task",
                "max_confidence": 0.99,
                "mention_count": 5,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    (release_dir / "trend_table.jsonl").write_text(
        json.dumps(
            {
                "canonical_id": "ent1",
                "canonical_surface": "Entity 1",
                "label": "task",
                "venue": "neurips",
                "year": 2023,
                "momentum": 1.0,
                "prevalence": 0.05,
                "change_direction": "rising",
                "rolling_mean_3": 0.04,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    (release_dir / "emergence_watchlist.jsonl").write_text(
        json.dumps(
            {
                "canonical_id": "ent1",
                "canonical_surface": "Entity 1",
                "label": "task",
                "venue": "neurips",
                "year": 2023,
                "emergence_score": 0.8,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    (release_dir / "cross_venue_flow.jsonl").write_text(
        json.dumps(
            {
                "canonical_id": "ent1",
                "canonical_surface": "Entity 1",
                "label": "task",
                "source_venue": "neurips",
                "source_year": 2022,
                "target_venue": "icml",
                "target_year": 2023,
                "transfer_score": 0.9,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    (release_dir / "bundle_table.jsonl").write_text(
        json.dumps(
            {
                "bundle_id": "bundle_1",
                "size": 10,
                "venue_count": 2,
                "venue_coverage": ["icml"],
                "members": ["task|ent1"],
                "top_entities": [
                    {
                        "node_key": "task|ent1",
                        "canonical_surface": "Entity 1",
                        "label": "task",
                        "paper_hits": 5,
                    }
                ],
                "yearly_paper_counts": {"2023": 5},
                "previous_year_papers": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    (release_dir / "cooccurrence_edges.jsonl").write_text(
        json.dumps(
            {
                "left_node": "task|ent1",
                "left_label": "task",
                "right_node": "method|ent2",
                "right_label": "method",
                "paper_count": 10,
                "venue": "neurips",
                "year": 2023,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    return release_dir


def test_resolve_signals_release_dir_prefers_richer_release(tmp_path: Path):
    root = tmp_path / "signals-product"
    root.mkdir()

    smaller = root / "small"
    smaller.mkdir()
    (smaller / "manifest.json").write_text(
        json.dumps(
            {
                "product_id": "folio-signals-v1",
                "run_id": "small",
                "entries_seen": 25,
                "mentions_seen": 153,
                "row_counts": {"trend_table.jsonl": 130},
            }
        ),
        encoding="utf-8",
    )

    richer = root / "rich"
    richer.mkdir()
    (richer / "manifest.json").write_text(
        json.dumps(
            {
                "product_id": "folio-signals-v1",
                "run_id": "rich",
                "entries_seen": 58169,
                "mentions_seen": 224618,
                "row_counts": {"trend_table.jsonl": 148222},
            }
        ),
        encoding="utf-8",
    )

    assert resolve_signals_release_dir(root) == richer


@pytest.mark.asyncio
async def test_ner_ingest_all_phases(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_release_dir: Path,
):
    """Ingest populates all NER-related tables from one release directory."""
    db_session.add(
        Entry(
            citation_key="key_A",
            entry_type=EntryType.ARTICLE,
            title="Paper A",
            source_file="test.bib",
        )
    )
    await db_session.commit()

    response = await client.post(
        "/api/ner/ingest",
        params={"directory": str(mock_release_dir)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["release_id"] == "folio-signals-v1:test_run"
    assert data["entities"] == 1
    assert data["facts"] == 1
    assert data["unresolved"] == 0
    assert data["trends"] == 1
    assert data["emergence"] == 1
    assert data["flow"] == 1
    assert data["bundles"] == 1
    assert data["edges"] == 1

    assert (await db_session.scalar(select(func.count()).select_from(NerRelease))) == 1
    assert (await db_session.scalar(select(func.count()).select_from(NerEntity))) == 1
    assert (
        await db_session.scalar(select(func.count()).select_from(EntryNerEntity))
    ) == 1
    assert (await db_session.scalar(select(func.count()).select_from(NerTrend))) == 1
    assert (await db_session.scalar(select(func.count()).select_from(NerEmergence))) == 1
    assert (
        await db_session.scalar(select(func.count()).select_from(NerCrossVenueFlow))
    ) == 1
    assert (await db_session.scalar(select(func.count()).select_from(NerBundle))) == 1
    assert (
        await db_session.scalar(select(func.count()).select_from(NerCooccurrenceEdge))
    ) == 1

    bundle = (
        await db_session.execute(select(NerBundle).where(NerBundle.bundle_id == "bundle_1"))
    ).scalar_one()
    assert bundle.bundle_index == 1
    assert bundle.top_entities[0]["canonical_id"] == "ent1"

    trend = (await db_session.execute(select(NerTrend))).scalar_one()
    emergence = (await db_session.execute(select(NerEmergence))).scalar_one()
    flow = (await db_session.execute(select(NerCrossVenueFlow))).scalar_one()
    assert trend.node_key == "task|ent1"
    assert emergence.node_key == "task|ent1"
    assert flow.node_key == "task|ent1"


@pytest.mark.asyncio
async def test_ner_ingest_rejects_concurrent_runs(
    client: AsyncClient,
    mock_release_dir: Path,
):
    lock = ner_ingest_service._NER_INGEST_MUTEX
    await lock.acquire()
    try:
        response = await client.post(
            "/api/ner/ingest",
            params={"directory": str(mock_release_dir)},
        )
    finally:
        lock.release()

    assert response.status_code == 409
    assert response.json()["detail"] == "NER ingest is already running"


@pytest.mark.asyncio
async def test_ner_ingest_merges_duplicate_fact_pairs(
    client: AsyncClient,
    db_session: AsyncSession,
    tmp_path: Path,
):
    release_dir = tmp_path / "signals_dupe"
    release_dir.mkdir()

    (release_dir / "manifest.json").write_text(
        json.dumps(
            {
                "product_id": "folio-signals-v1",
                "run_id": "dupe_run",
                "entries_seen": 1,
                "mentions_seen": 2,
            }
        ),
        encoding="utf-8",
    )

    (release_dir / "entity_atlas.jsonl").write_text(
        json.dumps(
            {
                "canonical_id": "ent1",
                "canonical_surface": "Entity 1",
                "label": "task",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    # Same entry/entity pair appears multiple times in the same source file.
    (release_dir / "paper_entity_facts.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "citation_key": "key_dupe",
                        "canonical_id": "ent1",
                        "label": "task",
                        "max_confidence": 0.4,
                        "mention_count": 1,
                    }
                ),
                json.dumps(
                    {
                        "citation_key": "key_dupe",
                        "canonical_id": "ent1",
                        "label": "task",
                        "max_confidence": 0.9,
                        "mention_count": 3,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    # Optional phase files are absent; ingest should still succeed.
    db_session.add(
        Entry(
            citation_key="key_dupe",
            entry_type=EntryType.ARTICLE,
            title="Duplicate Facts",
            source_file="test.bib",
        )
    )
    await db_session.commit()

    response = await client.post(
        "/api/ner/ingest",
        params={"directory": str(release_dir)},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["facts"] == 1
    assert payload["unresolved"] == 0

    row = (await db_session.execute(select(EntryNerEntity))).scalar_one()
    assert row.mention_count == 4
    assert row.confidence == 0.9


@pytest.mark.asyncio
async def test_ner_ingest_resolves_dblp_fact_keys_with_source_context(
    client: AsyncClient,
    db_session: AsyncSession,
    tmp_path: Path,
):
    release_dir = tmp_path / "signals_dblp"
    release_dir.mkdir()

    (release_dir / "manifest.json").write_text(
        json.dumps(
            {
                "product_id": "folio-signals-v1",
                "run_id": "dblp_run",
                "entries_seen": 1,
                "mentions_seen": 1,
            }
        ),
        encoding="utf-8",
    )
    (release_dir / "entity_atlas.jsonl").write_text(
        json.dumps(
            {
                "canonical_id": "ent1",
                "canonical_surface": "Entity 1",
                "label": "task",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (release_dir / "paper_entity_facts.jsonl").write_text(
        json.dumps(
                {
                    "citation_key": "DBLP:conf:iclr:GuoL25",
                    "source_file": "/tmp/conferences/iclr/unit_test_unique_2025.bib",
                    "year": 2025,
                    "canonical_id": "ent1",
                    "label": "task",
                "max_confidence": 0.8,
                "mention_count": 2,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    db_session.add(
        Entry(
            citation_key="guo2025adaptive",
            entry_type=EntryType.INPROCEEDINGS,
            title="Adaptive Learning",
            year=2025,
            source_file="conferences/iclr/unit_test_unique_2025.bib",
        )
    )
    await db_session.commit()

    response = await client.post(
        "/api/ner/ingest",
        params={"directory": str(release_dir)},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["facts"] == 1
    assert payload["unresolved"] == 0

    row = (await db_session.execute(select(EntryNerEntity))).scalar_one()
    assert row.mention_count == 2
    assert row.confidence == 0.8


@pytest.mark.asyncio
async def test_ner_ingest_keeps_dblp_resolution_conservative_when_ambiguous(
    client: AsyncClient,
    db_session: AsyncSession,
    tmp_path: Path,
):
    release_dir = tmp_path / "signals_dblp_ambiguous"
    release_dir.mkdir()

    (release_dir / "manifest.json").write_text(
        json.dumps(
            {
                "product_id": "folio-signals-v1",
                "run_id": "dblp_ambiguous_run",
                "entries_seen": 1,
                "mentions_seen": 1,
            }
        ),
        encoding="utf-8",
    )
    (release_dir / "entity_atlas.jsonl").write_text(
        json.dumps(
            {
                "canonical_id": "ent1",
                "canonical_surface": "Entity 1",
                "label": "task",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (release_dir / "paper_entity_facts.jsonl").write_text(
        json.dumps(
                {
                    "citation_key": "DBLP:conf:iclr:GuoL25",
                    "source_file": "/tmp/conferences/iclr/unit_test_ambiguous_2025.bib",
                    "year": 2025,
                    "canonical_id": "ent1",
                    "label": "task",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    db_session.add_all(
        [
            Entry(
                citation_key="guo2025adaptive",
                entry_type=EntryType.INPROCEEDINGS,
                title="Adaptive Learning",
                year=2025,
                source_file="conferences/iclr/unit_test_ambiguous_2025.bib",
            ),
            Entry(
                citation_key="guo2025robust",
                entry_type=EntryType.INPROCEEDINGS,
                title="Robust Learning",
                year=2025,
                source_file="conferences/iclr/unit_test_ambiguous_2025.bib",
            ),
        ]
    )
    await db_session.commit()

    response = await client.post(
        "/api/ner/ingest",
        params={"directory": str(release_dir)},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["facts"] == 0
    assert payload["unresolved"] == 1


@pytest.mark.asyncio
async def test_ner_ingest_normalizes_trend_change_direction_up_down(
    client: AsyncClient,
    db_session: AsyncSession,
    tmp_path: Path,
):
    release_dir = tmp_path / "signals_direction"
    release_dir.mkdir()

    (release_dir / "manifest.json").write_text(
        json.dumps(
            {
                "product_id": "folio-signals-v1",
                "run_id": "direction_run",
                "entries_seen": 0,
                "mentions_seen": 0,
            }
        ),
        encoding="utf-8",
    )
    (release_dir / "entity_atlas.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "canonical_id": "ent_up",
                        "canonical_surface": "Entity Up",
                        "label": "task",
                    }
                ),
                json.dumps(
                    {
                        "canonical_id": "ent_down",
                        "canonical_surface": "Entity Down",
                        "label": "task",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (release_dir / "paper_entity_facts.jsonl").write_text("", encoding="utf-8")
    (release_dir / "trend_table.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "canonical_id": "ent_up",
                        "canonical_surface": "Entity Up",
                        "label": "task",
                        "venue": "iclr",
                        "year": 2025,
                        "change_direction": "up",
                    }
                ),
                json.dumps(
                    {
                        "canonical_id": "ent_down",
                        "canonical_surface": "Entity Down",
                        "label": "task",
                        "venue": "iclr",
                        "year": 2025,
                        "change_direction": "down",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    response = await client.post(
        "/api/ner/ingest",
        params={"directory": str(release_dir)},
    )
    assert response.status_code == 200

    directions = (
        await db_session.execute(
            select(NerTrend.canonical_id, NerTrend.change_direction).order_by(
                NerTrend.canonical_id.asc()
            )
        )
    ).all()
    assert directions == [
        ("ent_down", "falling"),
        ("ent_up", "rising"),
    ]


@pytest.mark.asyncio
async def test_ner_ingest_deduplicates_entity_atlas_rows(
    client: AsyncClient,
    db_session: AsyncSession,
    tmp_path: Path,
):
    release_dir = tmp_path / "signals_entity_dupes"
    release_dir.mkdir()

    (release_dir / "manifest.json").write_text(
        json.dumps(
            {
                "product_id": "folio-signals-v1",
                "run_id": "entity_dupes",
                "entries_seen": 0,
                "mentions_seen": 0,
            }
        ),
        encoding="utf-8",
    )
    (release_dir / "entity_atlas.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "canonical_id": "ent1",
                        "canonical_surface": "Entity One",
                        "label": "task",
                        "paper_hits": 1,
                        "venues": ["iclr"],
                    }
                ),
                json.dumps(
                    {
                        "canonical_id": "ent1",
                        "canonical_surface": "Entity One Updated",
                        "label": "task",
                        "paper_hits": 3,
                        "venues": ["icml"],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (release_dir / "paper_entity_facts.jsonl").write_text("", encoding="utf-8")

    response = await client.post(
        "/api/ner/ingest",
        params={"directory": str(release_dir)},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["entities"] == 1

    entity = (
        await db_session.execute(select(NerEntity).where(NerEntity.canonical_id == "ent1"))
    ).scalar_one()
    assert entity.paper_hits == 3
    assert sorted(entity.venues or []) == ["iclr", "icml"]


@pytest.mark.asyncio
async def test_ner_ingest_handles_large_entity_atlas_batch(
    client: AsyncClient,
    db_session: AsyncSession,
    tmp_path: Path,
):
    release_dir = tmp_path / "signals_large_atlas"
    release_dir.mkdir()

    entity_count = 3500
    (release_dir / "manifest.json").write_text(
        json.dumps(
            {
                "product_id": "folio-signals-v1",
                "run_id": "large_atlas",
                "entries_seen": 0,
                "mentions_seen": entity_count,
            }
        ),
        encoding="utf-8",
    )
    atlas_rows = [
        json.dumps(
            {
                "canonical_id": f"ent_{index}",
                "canonical_surface": f"Entity {index}",
                "label": "task",
                "paper_hits": 1,
            }
        )
        for index in range(entity_count)
    ]
    (release_dir / "entity_atlas.jsonl").write_text(
        "\n".join(atlas_rows) + "\n",
        encoding="utf-8",
    )
    (release_dir / "paper_entity_facts.jsonl").write_text("", encoding="utf-8")

    response = await client.post(
        "/api/ner/ingest",
        params={"directory": str(release_dir)},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["entities"] == entity_count

    db_entities = await db_session.scalar(select(func.count()).select_from(NerEntity))
    assert db_entities == entity_count
