"""
Explicit process-owned service container for Mundaneum.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import meilisearch
from minio import Minio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import settings
from app.services.bibliography_repository import BibliographyRepositoryService
from app.services.storage import StorageService
from app.services.sync import SearchIndexService

if TYPE_CHECKING:
    from app.services.s2_runtime import S2Runtime


@dataclass(slots=True)
class DatabaseServices:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]


@dataclass(slots=True)
class SearchServices:
    client: meilisearch.Client
    indexer: SearchIndexService


@dataclass(slots=True)
class StorageServices:
    client: Minio
    service: StorageService


@dataclass(slots=True)
class BibliographyServices:
    repository: BibliographyRepositoryService


@dataclass(slots=True)
class ServiceContainer:
    database: DatabaseServices
    search: SearchServices
    storage: StorageServices
    bibliography: BibliographyServices
    s2_runtime: "S2Runtime"


def _build_meili_client() -> meilisearch.Client:
    return meilisearch.Client(
        settings.meili_url,
        settings.meili_api_key,
        timeout=settings.meili_timeout,
    )


def _build_minio_client() -> Minio:
    secure = settings.minio_url.startswith("https://")
    host = settings.minio_url.replace("https://", "").replace("http://", "")
    return Minio(
        host,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=secure,
    )


def build_service_container() -> ServiceContainer:
    from app.database import build_database_services
    from app.services.s2_runtime import build_s2_runtime

    database = build_database_services()
    search_client = _build_meili_client()
    storage_client = _build_minio_client()
    return ServiceContainer(
        database=database,
        search=SearchServices(
            client=search_client,
            indexer=SearchIndexService(search_client),
        ),
        storage=StorageServices(
            client=storage_client,
            service=StorageService(storage_client),
        ),
        bibliography=BibliographyServices(
            repository=BibliographyRepositoryService(
                repo_url=settings.bibliography_repo_url,
                checkout_path=Path(settings.bibliography_checkout_path),
                ref=settings.bibliography_repo_ref,
                timeout_seconds=settings.bibliography_sync_timeout_seconds,
            )
        ),
        s2_runtime=build_s2_runtime(session_factory=database.session_factory),
    )
