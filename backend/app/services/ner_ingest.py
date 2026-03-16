"""
NER release ingest service.

Loads folio-lab `signals-product` artifacts into relational tables.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError
from app.logging import get_logger
from app.modeling.concept_models import NerBundle, NerCooccurrenceEdge
from app.modeling.library_models import Entry
from app.modeling.ner_models import EntryNerEntity, NerEntity, NerRelease
from app.modeling.trend_models import NerCrossVenueFlow, NerEmergence, NerTrend

logger = get_logger(__name__)

BATCH_SIZE = 5000
PG_MAX_BIND_PARAMS = 32767
_NER_INGEST_MUTEX = asyncio.Lock()
_DBLP_FACT_KEY_RE = re.compile(r"^DBLP:conf:(?P<venue>[a-z0-9]+):(?P<suffix>[^:]+)$")
_SOURCE_FILE_RE = re.compile(
    r"(conferences|journals|workshops|books|misc)/.+",
    flags=re.IGNORECASE,
)


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            payload = line.strip()
            if not payload:
                continue
            try:
                row = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path.name}:{line_number}") from exc
            if isinstance(row, dict):
                yield row


def _max_rows_per_insert(*, bind_params_per_row: int, reserve: int = 16) -> int:
    """
    Bound multi-row VALUES statements to avoid asyncpg bind-parameter overflow.

    asyncpg enforces max query arguments of 32767; leave a small reserve for safety.
    """
    return max(1, (PG_MAX_BIND_PARAMS - reserve) // max(1, bind_params_per_row))


def resolve_signals_release_dir(directory: str | Path) -> Path:
    """Resolve a signals-product directory to a concrete release directory."""
    target_dir = Path(directory)
    if not target_dir.exists():
        raise FileNotFoundError(f"Directory does not exist: {target_dir}")
    if not target_dir.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {target_dir}")

    manifest_path = target_dir / "manifest.json"
    if manifest_path.exists():
        return target_dir

    releases = [
        path
        for path in target_dir.iterdir()
        if path.is_dir() and (path / "manifest.json").exists()
    ]
    if not releases:
        raise ValueError(f"No valid NER releases found in {target_dir}")
    return max(releases, key=_release_priority_key)


def _release_priority_key(path: Path) -> tuple[int, int, int, str, float]:
    """
    Rank candidate releases for auto-selection.

    Prefer richer releases first (entries/trend rows), then recency.
    """
    try:
        manifest = load_release_manifest(path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        return (0, 0, 0, "", path.stat().st_mtime)

    row_counts = manifest.get("row_counts")
    trend_rows = 0
    if isinstance(row_counts, dict):
        trend_rows = _as_int(row_counts.get("trend_table.jsonl"), default=0)

    return (
        _as_int(manifest.get("entries_seen"), default=0),
        trend_rows,
        _as_int(manifest.get("mentions_seen"), default=0),
        _as_str(manifest.get("created_at"), default=""),
        path.stat().st_mtime,
    )


def load_release_manifest(release_dir: Path) -> dict[str, Any]:
    manifest_path = release_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Required file not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError(f"Invalid manifest content in {manifest_path}")
    return manifest


def release_id_from_manifest(manifest: dict[str, Any], release_dir: Path) -> str:
    product_id = _as_str(manifest.get("product_id"), default="unknown")
    run_id = _as_str(manifest.get("run_id"), default=release_dir.name)
    return _as_str(
        manifest.get("release_id"),
        default=f"{product_id}:{run_id}",
    )


def _as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else default
    return str(value)


def _as_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _canonical_id_from_node(node_key: str | None) -> str | None:
    if not isinstance(node_key, str) or "|" not in node_key:
        return None
    return node_key.split("|", 1)[1] or None


def _label_from_node(node_key: str | None) -> str | None:
    if not isinstance(node_key, str) or "|" not in node_key:
        return None
    return node_key.split("|", 1)[0] or None


def _build_node_key(label: str | None, canonical_id: str | None) -> str:
    normalized_label = _as_str(label, default="")
    normalized_id = _as_str(canonical_id, default="")
    if normalized_label and normalized_id:
        return f"{normalized_label}|{normalized_id}"
    return normalized_id


def _normalize_top_entities(top_entities: Any) -> list[dict[str, Any]]:
    if not isinstance(top_entities, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in top_entities:
        if not isinstance(item, dict):
            continue
        node_key = _as_str(item.get("node_key"), default="")
        canonical_id = _as_str(item.get("canonical_id"), default="") or _as_str(
            _canonical_id_from_node(node_key),
            default="",
        )
        label = _as_str(item.get("label"), default="") or _as_str(
            _label_from_node(node_key),
            default="unknown",
        )
        normalized.append(
            {
                "canonical_id": canonical_id or None,
                "canonical_surface": _as_str(
                    item.get("canonical_surface"),
                    default=canonical_id,
                ),
                "label": label,
                "node_key": node_key or _build_node_key(label, canonical_id) or None,
                "paper_hits": _as_int(item.get("paper_hits"), default=0),
            }
        )
    return normalized


def _iter_fact_rows(row: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """
    Support both current and legacy fact shapes.

    Current:
      {"citation_key", "canonical_id", "label", "max_confidence", "mention_count"}
    Legacy:
      {"citation_key", "entities": [{"canonical_id", "label", "confidence", "mention_count"}]}
    """
    entities = row.get("entities")
    if isinstance(entities, list):
        citation_key = row.get("citation_key")
        source_file = row.get("source_file")
        year = row.get("year")
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            yield {
                "citation_key": citation_key,
                "source_file": source_file,
                "year": year,
                "canonical_id": entity.get("canonical_id"),
                "label": entity.get("label", row.get("label", "")),
                "max_confidence": entity.get(
                    "max_confidence",
                    entity.get("confidence", 0.0),
                ),
                "mention_count": entity.get("mention_count", 1),
            }
        return

    yield row


def _normalize_source_file(value: Any) -> str | None:
    raw = _as_str(value, default="")
    if not raw:
        return None
    path = raw.replace("\\", "/")
    marker = "/bibliography/"
    lowered = path.lower()
    marker_index = lowered.find(marker)
    if marker_index != -1:
        return path[marker_index + len(marker) :].lstrip("/")

    match = _SOURCE_FILE_RE.search(path)
    if match:
        return match.group(0)
    return path.lstrip("/")


def _normalize_change_direction(value: Any) -> str:
    direction = _as_str(value, default="stable").lower()
    if direction in {"up", "rising", "rise"}:
        return "rising"
    if direction in {"down", "falling", "fall"}:
        return "falling"
    return "stable"


def _resolve_dblp_entry_id(
    citation_key: str,
    source_file: Any,
    year_value: Any,
    *,
    source_year_to_entries: dict[tuple[str, int], list[tuple[str, Any]]],
    cache: dict[tuple[str, str | None, int], Any | None],
) -> Any | None:
    normalized_source = _normalize_source_file(source_file)
    fact_year = _as_int(year_value, default=0)
    cache_key = (citation_key, normalized_source, fact_year)
    if cache_key in cache:
        return cache[cache_key]

    match = _DBLP_FACT_KEY_RE.match(citation_key)
    if not match:
        cache[cache_key] = None
        return None

    suffix = match.group("suffix")
    year_match = re.search(r"(\d{2})$", suffix)
    if not year_match:
        cache[cache_key] = None
        return None
    yy = int(year_match.group(1))
    inferred_year = 2000 + yy if yy < 70 else 1900 + yy
    target_year = fact_year or inferred_year
    if not normalized_source or target_year <= 0:
        cache[cache_key] = None
        return None

    surname_match = re.match(r"([A-Z][a-z]+)", suffix)
    if not surname_match:
        cache[cache_key] = None
        return None
    surname = surname_match.group(1).lower()

    candidates = source_year_to_entries.get((normalized_source, target_year), [])
    matches = [
        entry_id
        for candidate_key, entry_id in candidates
        if candidate_key.lower().startswith(f"{surname}{target_year}")
    ]
    if len(matches) == 1:
        cache[cache_key] = matches[0]
        return matches[0]

    cache[cache_key] = None
    return None


async def ingest_ner_release(
    db: AsyncSession,
    release_dir: Path,
) -> dict[str, Any]:
    if _NER_INGEST_MUTEX.locked():
        raise ConflictError("NER ingest is already running")

    async with _NER_INGEST_MUTEX:
        return await _ingest_ner_release_unlocked(db, release_dir)


async def _ingest_ner_release_unlocked(
    db: AsyncSession,
    release_dir: Path,
) -> dict[str, Any]:
    """
    Ingest one NER signals-product release into the database.

    Required files:
      - manifest.json
      - entity_atlas.jsonl
      - paper_entity_facts.jsonl
    """
    manifest_path = release_dir / "manifest.json"
    atlas_path = release_dir / "entity_atlas.jsonl"
    facts_path = release_dir / "paper_entity_facts.jsonl"

    for path in (manifest_path, atlas_path, facts_path):
        if not path.exists():
            raise FileNotFoundError(f"Required file not found: {path}")

    manifest = load_release_manifest(release_dir)
    product_id = _as_str(manifest.get("product_id"), default="unknown")
    run_id = _as_str(manifest.get("run_id"), default=release_dir.name)
    release_id = release_id_from_manifest(manifest, release_dir)

    logger.info("Ingesting NER release '%s' from %s", release_id, release_dir)

    # Clear and rebuild all NER-derived tables atomically.
    await db.execute(delete(EntryNerEntity))
    await db.execute(delete(NerEntity))
    await db.execute(delete(NerRelease))
    await db.execute(delete(NerCrossVenueFlow))
    await db.execute(delete(NerEmergence))
    await db.execute(delete(NerTrend))
    await db.execute(delete(NerCooccurrenceEdge))
    await db.execute(delete(NerBundle))
    await db.flush()

    db.add(
        NerRelease(
            release_id=release_id,
            product_id=product_id,
            run_id=run_id,
            entries_seen=int(manifest.get("entries_seen", 0)),
            mentions_seen=int(manifest.get("mentions_seen", 0)),
            manifest=manifest,
        )
    )

    entity_count = await _ingest_entity_atlas(db, atlas_path)
    facts_count, unresolved = await _ingest_paper_entity_facts(db, facts_path)

    trend_count = await _ingest_trend_table(db, release_dir / "trend_table.jsonl")
    emergence_count = await _ingest_emergence(
        db,
        release_dir / "emergence_watchlist.jsonl",
    )
    flow_count = await _ingest_cross_venue_flow(
        db,
        release_dir / "cross_venue_flow.jsonl",
    )

    bundle_count = await _ingest_bundles(db, release_dir / "bundle_table.jsonl")
    edge_count = await _ingest_cooccurrence_edges(
        db,
        release_dir / "cooccurrence_edges.jsonl",
    )

    await db.commit()
    return {
        "entities": entity_count,
        "facts": facts_count,
        "unresolved": unresolved,
        "trends": trend_count,
        "emergence": emergence_count,
        "flow": flow_count,
        "bundles": bundle_count,
        "edges": edge_count,
        "release_id": release_id,
    }


async def _ingest_entity_atlas(db: AsyncSession, atlas_path: Path) -> int:
    if not atlas_path.exists():
        return 0

    total = 0
    current_batch: list[dict[str, Any]] = []
    for row in _iter_jsonl(atlas_path):
        canonical_id = _as_str(row.get("canonical_id"), default="")
        if not canonical_id:
            continue
        label = _as_str(row.get("label"), default="unknown")
        current_batch.append(
            {
                "canonical_id": canonical_id,
                "canonical_surface": _as_str(
                    row.get("canonical_surface"),
                    default=canonical_id,
                ),
                "label": label,
                "first_year": _as_int(row.get("first_year"), default=0) or None,
                "last_year": _as_int(row.get("last_year"), default=0) or None,
                "paper_hits": _as_int(row.get("paper_hits"), default=0),
                "mention_total": _as_int(row.get("mention_total"), default=0),
                "venue_count": _as_int(row.get("venue_count"), default=0),
                "venues": row.get("venues", []),
                "years_active": _as_int(row.get("years_active"), default=0),
            }
        )

        if len(current_batch) >= BATCH_SIZE:
            total += await _upsert_entity_batch(db, current_batch)
            current_batch = []

    if current_batch:
        total += await _upsert_entity_batch(db, current_batch)
    return total


def _merge_year(existing: Any, incoming: Any, *, mode: str) -> int | None:
    existing_year = _as_int(existing, default=0) or None
    incoming_year = _as_int(incoming, default=0) or None
    if existing_year is None:
        return incoming_year
    if incoming_year is None:
        return existing_year
    if mode == "min":
        return min(existing_year, incoming_year)
    return max(existing_year, incoming_year)


def _merge_venues(existing: Any, incoming: Any) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for source in (existing, incoming):
        if not isinstance(source, list):
            continue
        for venue in source:
            venue_name = _as_str(venue, default="")
            if not venue_name or venue_name in seen:
                continue
            seen.add(venue_name)
            merged.append(venue_name)
    return merged


async def _upsert_entity_batch(db: AsyncSession, rows: list[dict[str, Any]]) -> int:
    merged_rows: dict[str, dict[str, Any]] = {}
    for row in rows:
        canonical_id = _as_str(row.get("canonical_id"), default="")
        if not canonical_id:
            continue

        existing = merged_rows.get(canonical_id)
        if existing is None:
            merged_rows[canonical_id] = dict(row)
            continue

        existing["canonical_surface"] = _as_str(
            row.get("canonical_surface"),
            default=_as_str(existing.get("canonical_surface"), default=canonical_id),
        )
        existing["label"] = _as_str(
            row.get("label"),
            default=_as_str(existing.get("label"), default="unknown"),
        )
        existing["first_year"] = _merge_year(
            existing.get("first_year"),
            row.get("first_year"),
            mode="min",
        )
        existing["last_year"] = _merge_year(
            existing.get("last_year"),
            row.get("last_year"),
            mode="max",
        )
        existing["paper_hits"] = max(
            _as_int(existing.get("paper_hits"), default=0),
            _as_int(row.get("paper_hits"), default=0),
        )
        existing["mention_total"] = max(
            _as_int(existing.get("mention_total"), default=0),
            _as_int(row.get("mention_total"), default=0),
        )
        existing["venue_count"] = max(
            _as_int(existing.get("venue_count"), default=0),
            _as_int(row.get("venue_count"), default=0),
        )
        existing["venues"] = _merge_venues(existing.get("venues"), row.get("venues"))
        existing["years_active"] = max(
            _as_int(existing.get("years_active"), default=0),
            _as_int(row.get("years_active"), default=0),
        )

    if not merged_rows:
        return 0

    values = list(merged_rows.values())
    chunk_size = _max_rows_per_insert(
        bind_params_per_row=len(NerEntity.__table__.columns)
    )
    for start in range(0, len(values), chunk_size):
        chunk = values[start : start + chunk_size]
        stmt = pg_insert(NerEntity).values(chunk)
        await db.execute(
            stmt.on_conflict_do_update(
                index_elements=[NerEntity.canonical_id],
                set_={
                    "canonical_surface": stmt.excluded.canonical_surface,
                    "label": stmt.excluded.label,
                    "first_year": stmt.excluded.first_year,
                    "last_year": stmt.excluded.last_year,
                    "paper_hits": stmt.excluded.paper_hits,
                    "mention_total": stmt.excluded.mention_total,
                    "venue_count": stmt.excluded.venue_count,
                    "venues": stmt.excluded.venues,
                    "years_active": stmt.excluded.years_active,
                },
            )
        )
    return len(merged_rows)


async def _ingest_paper_entity_facts(
    db: AsyncSession,
    facts_path: Path,
) -> tuple[int, int]:
    if not facts_path.exists():
        return 0, 0

    entry_rows = await db.execute(
        select(Entry.citation_key, Entry.id, Entry.source_file, Entry.year)
    )
    key_to_entry_id: dict[str, Any] = {}
    source_year_to_entries: dict[tuple[str, int], list[tuple[str, Any]]] = defaultdict(
        list
    )
    for citation_key, entry_id, source_file, year in entry_rows.all():
        key_to_entry_id[citation_key] = entry_id
        normalized_source = _normalize_source_file(source_file)
        if normalized_source and isinstance(year, int):
            source_year_to_entries[(normalized_source, year)].append(
                (citation_key, entry_id)
            )

    entity_rows = await db.execute(select(NerEntity.canonical_id, NerEntity.id))
    canonical_to_entity_id = {row[0]: row[1] for row in entity_rows.all()}
    dblp_resolution_cache: dict[tuple[str, str | None, int], Any | None] = {}

    unresolved = 0
    unique_pairs: set[tuple[str, str]] = set()
    current_batch: list[dict[str, Any]] = []

    for raw_row in _iter_jsonl(facts_path):
        for row in _iter_fact_rows(raw_row):
            citation_key = row.get("citation_key")
            canonical_id = row.get("canonical_id")
            entry_id = key_to_entry_id.get(citation_key)
            if entry_id is None and isinstance(citation_key, str):
                entry_id = _resolve_dblp_entry_id(
                    citation_key,
                    row.get("source_file"),
                    row.get("year"),
                    source_year_to_entries=source_year_to_entries,
                    cache=dblp_resolution_cache,
                )
            ner_entity_id = canonical_to_entity_id.get(canonical_id)
            if entry_id is None or ner_entity_id is None:
                unresolved += 1
                continue

            confidence = _as_float(
                row.get("max_confidence", row.get("confidence_sum")),
                default=0.0,
            )
            mention_count = max(1, _as_int(row.get("mention_count"), default=1))
            label = _as_str(row.get("label"), default="unknown")
            current_batch.append(
                {
                    "entry_id": entry_id,
                    "ner_entity_id": ner_entity_id,
                    "label": label,
                    "confidence": confidence,
                    "mention_count": mention_count,
                }
            )
            unique_pairs.add((str(entry_id), str(ner_entity_id)))

            if len(current_batch) >= BATCH_SIZE:
                await _upsert_facts_batch(db, current_batch)
                current_batch = []

    if current_batch:
        await _upsert_facts_batch(db, current_batch)

    return len(unique_pairs), unresolved


async def _upsert_facts_batch(db: AsyncSession, rows: list[dict[str, Any]]) -> None:
    # Postgres cannot handle duplicate conflict keys within the same INSERT ... ON CONFLICT
    # statement. Collapse duplicates first.
    merged_rows: dict[tuple[Any, Any], dict[str, Any]] = {}
    for row in rows:
        key = (row["entry_id"], row["ner_entity_id"])
        existing = merged_rows.get(key)
        if existing is None:
            merged_rows[key] = {
                "entry_id": row["entry_id"],
                "ner_entity_id": row["ner_entity_id"],
                "label": row["label"],
                "confidence": row["confidence"],
                "mention_count": row["mention_count"],
            }
            continue

        existing["mention_count"] += int(row.get("mention_count", 0))
        existing["confidence"] = max(
            float(existing.get("confidence", 0.0)),
            float(row.get("confidence", 0.0)),
        )
        if not existing.get("label") and row.get("label"):
            existing["label"] = row["label"]

    values = list(merged_rows.values())
    chunk_size = _max_rows_per_insert(
        bind_params_per_row=len(EntryNerEntity.__table__.columns)
    )
    for start in range(0, len(values), chunk_size):
        chunk = values[start : start + chunk_size]
        stmt = pg_insert(EntryNerEntity).values(chunk)
        await db.execute(
            stmt.on_conflict_do_update(
                index_elements=[EntryNerEntity.entry_id, EntryNerEntity.ner_entity_id],
                set_={
                    "label": stmt.excluded.label,
                    "confidence": func.greatest(
                        EntryNerEntity.confidence,
                        stmt.excluded.confidence,
                    ),
                    "mention_count": EntryNerEntity.mention_count
                    + stmt.excluded.mention_count,
                },
            )
        )


async def _ingest_trend_table(db: AsyncSession, trend_path: Path) -> int:
    if not trend_path.exists():
        return 0

    total = 0
    current_batch: list[dict[str, Any]] = []
    for row in _iter_jsonl(trend_path):
        canonical_id = _as_str(row.get("canonical_id"), default="")
        if not canonical_id:
            continue
        label = _as_str(row.get("label"), default="unknown")
        node_key = _as_str(row.get("node_key"), default="") or _build_node_key(
            label,
            canonical_id,
        )
        change_direction = _normalize_change_direction(row.get("change_direction"))
        current_batch.append(
            {
                "canonical_id": canonical_id,
                "canonical_surface": _as_str(
                    row.get("canonical_surface"),
                    default=canonical_id,
                ),
                "label": label,
                "venue": _as_str(row.get("venue"), default=""),
                "year": _as_int(row.get("year"), default=0),
                "paper_hits": _as_int(row.get("paper_hits"), default=0),
                "prevalence": _as_float(row.get("prevalence"), default=0.0),
                "momentum": _as_float(row.get("momentum"), default=0.0),
                "rolling_mean_3": _as_float(row.get("rolling_mean_3"), default=0.0),
                "weighted_prevalence": _as_float(
                    row.get("weighted_prevalence"),
                    default=0.0,
                ),
                "prevalence_z_by_year_label": _as_float(
                    row.get("prevalence_z_by_year_label"),
                    default=0.0,
                ),
                "change_point": bool(row.get("change_point", False)),
                "change_direction": change_direction,
                "novelty": _as_int(row.get("novelty"), default=0),
                "novelty_score": _as_float(row.get("novelty_score"), default=0.0),
                "persistence_streak": _as_int(row.get("persistence_streak"), default=0),
                "mention_count": _as_int(row.get("mention_count"), default=0),
                "mention_density": _as_float(row.get("mention_density"), default=0.0),
                "confidence_sum": _as_float(row.get("confidence_sum"), default=0.0),
                "cross_venue_transfer": _as_float(
                    row.get("cross_venue_transfer"),
                    default=0.0,
                ),
                "papers_in_venue_year": _as_int(row.get("papers_in_venue_year"), default=0),
                "node_key": node_key,
            }
        )

        if len(current_batch) >= BATCH_SIZE:
            await db.execute(insert(NerTrend), current_batch)
            total += len(current_batch)
            current_batch = []

    if current_batch:
        await db.execute(insert(NerTrend), current_batch)
        total += len(current_batch)
    return total


async def _ingest_emergence(db: AsyncSession, emergence_path: Path) -> int:
    if not emergence_path.exists():
        return 0

    total = 0
    current_batch: list[dict[str, Any]] = []
    for row in _iter_jsonl(emergence_path):
        canonical_id = _as_str(row.get("canonical_id"), default="")
        if not canonical_id:
            continue
        label = _as_str(row.get("label"), default="unknown")
        node_key = _as_str(row.get("node_key"), default="") or _build_node_key(
            label,
            canonical_id,
        )
        current_batch.append(
            {
                "canonical_id": canonical_id,
                "canonical_surface": _as_str(
                    row.get("canonical_surface"),
                    default=canonical_id,
                ),
                "label": label,
                "venue": _as_str(row.get("venue"), default=""),
                "year": _as_int(row.get("year"), default=0),
                "emergence_score": _as_float(row.get("emergence_score"), default=0.0),
                "momentum": _as_float(row.get("momentum"), default=0.0),
                "prevalence": _as_float(row.get("prevalence"), default=0.0),
                "prevalence_z_by_year_label": _as_float(
                    row.get("prevalence_z_by_year_label"),
                    default=0.0,
                ),
                "paper_hits": _as_int(row.get("paper_hits"), default=0),
                "cross_venue_transfer": _as_float(
                    row.get("cross_venue_transfer"),
                    default=0.0,
                ),
                "novelty": _as_int(row.get("novelty"), default=0),
                "node_key": node_key,
            }
        )
        if len(current_batch) >= BATCH_SIZE:
            await db.execute(insert(NerEmergence), current_batch)
            total += len(current_batch)
            current_batch = []

    if current_batch:
        await db.execute(insert(NerEmergence), current_batch)
        total += len(current_batch)
    return total


async def _ingest_cross_venue_flow(db: AsyncSession, flow_path: Path) -> int:
    if not flow_path.exists():
        return 0

    total = 0
    current_batch: list[dict[str, Any]] = []
    for row in _iter_jsonl(flow_path):
        canonical_id = _as_str(row.get("canonical_id"), default="")
        if not canonical_id:
            continue
        label = _as_str(row.get("label"), default="unknown")
        node_key = _as_str(row.get("node_key"), default="") or _build_node_key(
            label,
            canonical_id,
        )
        current_batch.append(
            {
                "canonical_id": canonical_id,
                "canonical_surface": _as_str(
                    row.get("canonical_surface"),
                    default=canonical_id,
                ),
                "label": label,
                "source_venue": _as_str(row.get("source_venue"), default=""),
                "source_year": _as_int(row.get("source_year"), default=0),
                "target_venue": _as_str(row.get("target_venue"), default=""),
                "target_year": _as_int(row.get("target_year"), default=0),
                "lag_years": _as_int(row.get("lag_years"), default=0),
                "transfer_score": _as_float(row.get("transfer_score"), default=0.0),
                "target_prevalence": _as_float(
                    row.get("target_prevalence"),
                    default=0.0,
                ),
                "node_key": node_key,
            }
        )
        if len(current_batch) >= BATCH_SIZE:
            await db.execute(insert(NerCrossVenueFlow), current_batch)
            total += len(current_batch)
            current_batch = []

    if current_batch:
        await db.execute(insert(NerCrossVenueFlow), current_batch)
        total += len(current_batch)
    return total


async def _ingest_bundles(db: AsyncSession, bundle_path: Path) -> int:
    if not bundle_path.exists():
        return 0

    total = 0
    current_batch: list[dict[str, Any]] = []
    for row in _iter_jsonl(bundle_path):
        yearly_counts = row.get("yearly_paper_counts", {})
        if isinstance(yearly_counts, dict):
            normalized_yearly = {
                str(year): _as_int(count, default=0)
                for year, count in yearly_counts.items()
                if isinstance(year, (str, int))
            }
        else:
            normalized_yearly = {}

        current_batch.append(
            {
                "bundle_index": _as_int(
                    row.get("bundle_index"),
                    default=total + len(current_batch) + 1,
                ),
                "bundle_id": (
                    str(row["bundle_id"]) if row.get("bundle_id") is not None else None
                ),
                "lifecycle": _as_str(row.get("lifecycle"), default="stable"),
                "birth_year": _as_int(row.get("birth_year"), default=0) or None,
                "latest_year": _as_int(row.get("latest_year"), default=0) or None,
                "size": _as_int(row.get("size"), default=0),
                "latest_year_papers": _as_int(row.get("latest_year_papers"), default=0),
                "venue_count": _as_int(row.get("venue_count"), default=0),
                "growth_rate": _as_float(row.get("growth_rate"), default=0.0),
                "cohesion": _as_float(row.get("cohesion"), default=0.0),
                "internal_edge_weight": _as_int(row.get("internal_edge_weight"), default=0),
                "external_edge_weight": _as_int(row.get("external_edge_weight"), default=0),
                "venue_coverage": row.get("venue_coverage", []),
                "members": row.get("members", []),
                "top_entities": _normalize_top_entities(row.get("top_entities")),
                "yearly_paper_counts": normalized_yearly,
                "previous_year_papers": _as_int(row.get("previous_year_papers"), default=0),
            }
        )
        if len(current_batch) >= BATCH_SIZE:
            await db.execute(insert(NerBundle), current_batch)
            total += len(current_batch)
            current_batch = []

    if current_batch:
        await db.execute(insert(NerBundle), current_batch)
        total += len(current_batch)
    return total


async def _ingest_cooccurrence_edges(db: AsyncSession, edge_path: Path) -> int:
    if not edge_path.exists():
        return 0

    total = 0
    current_batch: list[dict[str, Any]] = []
    for row in _iter_jsonl(edge_path):
        left_node = _as_str(row.get("left_node"), default="")
        right_node = _as_str(row.get("right_node"), default="")
        left_label = _as_str(row.get("left_label"), default="")
        right_label = _as_str(row.get("right_label"), default="")

        if not left_node:
            left_node = _build_node_key(
                left_label,
                _as_str(row.get("left_canonical_id"), default=""),
            )
        if not right_node:
            right_node = _build_node_key(
                right_label,
                _as_str(row.get("right_canonical_id"), default=""),
            )
        if not left_node or not right_node:
            continue

        left_label = left_label or _as_str(_label_from_node(left_node), default="unknown")
        right_label = right_label or _as_str(
            _label_from_node(right_node),
            default="unknown",
        )

        current_batch.append(
            {
                "left_node": left_node,
                "right_node": right_node,
                "left_label": left_label,
                "right_label": right_label,
                "paper_count": _as_int(row.get("paper_count"), default=0),
                "venue": _as_str(row.get("venue"), default=""),
                "year": _as_int(row.get("year"), default=0),
            }
        )
        if len(current_batch) >= BATCH_SIZE:
            await db.execute(insert(NerCooccurrenceEdge), current_batch)
            total += len(current_batch)
            current_batch = []

    if current_batch:
        await db.execute(insert(NerCooccurrenceEdge), current_batch)
        total += len(current_batch)
    return total
