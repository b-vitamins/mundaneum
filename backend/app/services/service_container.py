"""
Explicit process-owned service container for Mundaneum.
"""

from __future__ import annotations

from dataclasses import dataclass

import meilisearch
from minio import Minio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import settings


@dataclass(slots=True)
class DatabaseServices:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]


@dataclass(slots=True)
class SearchServices:
    client: meilisearch.Client


@dataclass(slots=True)
class StorageServices:
    client: Minio


@dataclass(slots=True)
class ServiceContainer:
    database: DatabaseServices
    search: SearchServices
    storage: StorageServices
    s2_runtime: "S2Runtime"


_container: ServiceContainer | None = None


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

    return ServiceContainer(
        database=build_database_services(),
        search=SearchServices(client=_build_meili_client()),
        storage=StorageServices(client=_build_minio_client()),
        s2_runtime=build_s2_runtime(),
    )


def set_service_container(container: ServiceContainer) -> None:
    global _container
    _container = container


def get_service_container() -> ServiceContainer:
    global _container
    if _container is None:
        _container = build_service_container()
    return _container


def reset_service_container() -> None:
    global _container
    _container = None
