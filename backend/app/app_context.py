"""
Application composition root context.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from app.runtime import AppRuntime, build_app_runtime
from app.services.service_container import ServiceContainer, build_service_container
from app.services.domain_events import DomainEventBus, build_domain_event_bus


@dataclass(slots=True)
class AppContext:
    """Top-level process context owned by the FastAPI application."""

    services: ServiceContainer
    runtime: AppRuntime
    events: DomainEventBus


def build_app_context() -> AppContext:
    """Build all process-owned services and runtime wiring."""
    services = build_service_container()
    events = build_domain_event_bus(
        session_factory=services.database.session_factory,
        search_index=services.search.indexer,
    )
    runtime = build_app_runtime(services, events)
    return AppContext(services=services, runtime=runtime, events=events)


def get_app_context(request: Request) -> AppContext:
    """Resolve the current app context from request state."""
    return request.app.state.context
