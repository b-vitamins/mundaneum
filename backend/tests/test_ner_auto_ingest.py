import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modeling.library_models import Entry, EntryType
from app.modeling.ner_models import NerRelease
from app.runtime_components import run_ner_auto_ingest_once


def _create_release_dir(base_dir: Path, *, product_id: str, run_id: str) -> Path:
    release_dir = base_dir / run_id
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "manifest.json").write_text(
        json.dumps({"product_id": product_id, "run_id": run_id}),
        encoding="utf-8",
    )
    return release_dir


def _create_release_dir_with_entries_seen(
    base_dir: Path,
    *,
    product_id: str,
    run_id: str,
    entries_seen: int,
) -> Path:
    release_dir = base_dir / run_id
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "manifest.json").write_text(
        json.dumps(
            {
                "product_id": product_id,
                "run_id": run_id,
                "entries_seen": entries_seen,
            }
        ),
        encoding="utf-8",
    )
    return release_dir


@pytest.mark.asyncio
async def test_auto_ingest_runs_for_new_release(
    tmp_path: Path,
    isolated_session_factory: async_sessionmaker[AsyncSession],
):
    signals_root = tmp_path / "signals-product"
    release_dir = _create_release_dir(signals_root, product_id="folio-signals-v1", run_id="run-1")

    async with isolated_session_factory() as session:
        session.add(
            Entry(
                citation_key="entry_auto_1",
                entry_type=EntryType.ARTICLE,
                title="Auto Ingest Entry",
                source_file="test.bib",
            )
        )
        await session.commit()

    calls: list[Path] = []

    async def ingest_stub(db: AsyncSession, target_release_dir: Path) -> dict:
        calls.append(target_release_dir)
        db.add(
            NerRelease(
                release_id="folio-signals-v1:run-1",
                product_id="folio-signals-v1",
                run_id="run-1",
                manifest={},
            )
        )
        await db.commit()
        return {
            "release_id": "folio-signals-v1:run-1",
            "entities": 0,
            "facts": 0,
            "unresolved": 0,
            "trends": 0,
            "emergence": 0,
            "flow": 0,
            "bundles": 0,
            "edges": 0,
        }

    outcome = await run_ner_auto_ingest_once(
        session_factory=isolated_session_factory,
        signals_path=signals_root,
        wait_for_entries=True,
        wait_timeout_seconds=5,
        poll_interval_seconds=0.1,
        ingest_release=ingest_stub,
    )

    assert outcome["status"] == "complete"
    assert outcome["release_id"] == "folio-signals-v1:run-1"
    assert calls == [release_dir]

    async with isolated_session_factory() as session:
        release_count = await session.scalar(
            select(func.count())
            .select_from(NerRelease)
            .where(NerRelease.release_id == "folio-signals-v1:run-1")
        )
    assert release_count == 1


@pytest.mark.asyncio
async def test_auto_ingest_skips_when_release_is_already_ingested(
    tmp_path: Path,
    isolated_session_factory: async_sessionmaker[AsyncSession],
):
    signals_root = tmp_path / "signals-product"
    _create_release_dir(signals_root, product_id="folio-signals-v1", run_id="run-2")

    async with isolated_session_factory() as session:
        session.add(
            Entry(
                citation_key="entry_auto_2",
                entry_type=EntryType.ARTICLE,
                title="Auto Ingest Existing",
                source_file="test.bib",
            )
        )
        session.add(
            NerRelease(
                release_id="folio-signals-v1:run-2",
                product_id="folio-signals-v1",
                run_id="run-2",
                manifest={},
            )
        )
        await session.commit()

    async def ingest_stub(_db: AsyncSession, _target_release_dir: Path) -> dict:
        raise AssertionError("ingest should not run for an already ingested release")

    outcome = await run_ner_auto_ingest_once(
        session_factory=isolated_session_factory,
        signals_path=signals_root,
        wait_for_entries=True,
        wait_timeout_seconds=5,
        poll_interval_seconds=0.1,
        ingest_release=ingest_stub,
    )

    assert outcome["status"] == "skipped"
    assert "already ingested" in outcome["message"]
    assert outcome["release_id"] == "folio-signals-v1:run-2"


@pytest.mark.asyncio
async def test_auto_ingest_skips_when_entries_not_ready(
    tmp_path: Path,
    isolated_session_factory: async_sessionmaker[AsyncSession],
):
    signals_root = tmp_path / "signals-product"
    _create_release_dir_with_entries_seen(
        signals_root,
        product_id="folio-signals-v1",
        run_id="run-3",
        entries_seen=10**9,
    )

    async def ingest_stub(_db: AsyncSession, _target_release_dir: Path) -> dict:
        raise AssertionError("ingest should not run when threshold is unmet")

    outcome = await run_ner_auto_ingest_once(
        session_factory=isolated_session_factory,
        signals_path=signals_root,
        wait_for_entries=True,
        wait_timeout_seconds=0,
        poll_interval_seconds=0.1,
        ingest_release=ingest_stub,
    )

    assert outcome["status"] == "skipped"
    assert "bibliography entries not ready" in outcome["message"]


@pytest.mark.asyncio
async def test_auto_ingest_waits_for_manifest_entry_threshold(
    tmp_path: Path,
    isolated_session_factory: async_sessionmaker[AsyncSession],
):
    signals_root = tmp_path / "signals-product"
    async with isolated_session_factory() as session:
        existing_entries = int(await session.scalar(select(func.count(Entry.id))) or 0)

    target_entries = existing_entries + 5
    _create_release_dir_with_entries_seen(
        signals_root,
        product_id="folio-signals-v1",
        run_id="run-threshold",
        entries_seen=target_entries,
    )

    async with isolated_session_factory() as session:
        session.add(
            Entry(
                citation_key="entry_only_one",
                entry_type=EntryType.ARTICLE,
                title="Only one entry",
                source_file="test.bib",
            )
        )
        await session.commit()

    async def ingest_stub(_db: AsyncSession, _target_release_dir: Path) -> dict:
        raise AssertionError("ingest should not run when threshold is unmet")

    outcome = await run_ner_auto_ingest_once(
        session_factory=isolated_session_factory,
        signals_path=signals_root,
        wait_for_entries=True,
        wait_timeout_seconds=0,
        poll_interval_seconds=0.1,
        ingest_release=ingest_stub,
    )

    assert outcome["status"] == "skipped"
    assert f"need {target_entries}" in outcome["message"]
