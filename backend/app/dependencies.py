"""
FastAPI dependency helpers for explicit app-owned services.
"""

from __future__ import annotations

from fastapi import Depends, Request

from app.app_context import AppContext, get_app_context
from app.runtime import AppRuntime
from app.services.storage import StorageService
from app.services.sync import SearchIndexService


def get_runtime(context: AppContext = Depends(get_app_context)) -> AppRuntime:
    return context.runtime


def get_search_index(context: AppContext = Depends(get_app_context)) -> SearchIndexService:
    return context.services.search.indexer


def get_storage(context: AppContext = Depends(get_app_context)) -> StorageService:
    return context.services.storage.service


def get_s2_runtime(request: Request):
    return request.app.state.context.services.s2_runtime
