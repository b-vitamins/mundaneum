"""
Application composition root context.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from app.runtime import AppRuntime, build_app_runtime
from app.services.service_container import (
    ServiceContainer,
    build_service_container,
    set_service_container,
)


@dataclass(slots=True)
class AppContext:
    """Top-level process context owned by the FastAPI application."""

    services: ServiceContainer
    runtime: AppRuntime


def build_app_context() -> AppContext:
    """Build all process-owned services and runtime wiring."""
    services = build_service_container()
    set_service_container(services)
    runtime = build_app_runtime(services)
    return AppContext(services=services, runtime=runtime)


def get_app_context(request: Request) -> AppContext:
    """Resolve the current app context from request state."""
    return request.app.state.context
