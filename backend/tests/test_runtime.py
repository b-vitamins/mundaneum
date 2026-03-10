from types import SimpleNamespace

import pytest

from app.runtime import build_app_runtime
from app.runtime_models import ManagedJob, RuntimeDefinition
from app.services.domain_events import DomainEventBus
from app.services.system_health import HealthContributor


class RecordingJob(ManagedJob):
    def __init__(self, name: str, events: list[str]):
        self.name = name
        self._events = events
        self._running = False

    async def start(self) -> None:
        self._events.append(f"start:{self.name}")
        self._running = True

    async def stop(self) -> None:
        self._events.append(f"stop:{self.name}")
        self._running = False

    def status(self) -> dict:
        return {"status": "running" if self._running else "idle"}


def make_services() -> SimpleNamespace:
    async def dispose() -> None:
        return None

    async def close() -> None:
        return None

    return SimpleNamespace(
        database=SimpleNamespace(
            engine=SimpleNamespace(dispose=dispose),
            session_factory=None,
        ),
        search=SimpleNamespace(indexer=SimpleNamespace(is_available=lambda: True)),
        s2_runtime=SimpleNamespace(close=close),
    )


@pytest.mark.asyncio
async def test_runtime_builds_jobs_from_definition():
    events: list[str] = []
    services = make_services()

    runtime = build_app_runtime(
        services,
        DomainEventBus(),
        definition=RuntimeDefinition(
            jobs=[
                lambda resources: RecordingJob("alpha", events),
                lambda resources: RecordingJob("beta", events),
            ],
            health_contributors=[
                lambda resources: HealthContributor(name="database", probe=lambda: True),
                lambda resources: HealthContributor(name="search", probe=lambda: True),
            ],
        ),
    )

    await runtime.start()
    assert events == ["start:alpha", "start:beta"]
    assert runtime.snapshot() == {
        "alpha": {"status": "running"},
        "beta": {"status": "running"},
    }

    await runtime.stop()
    assert events == ["start:alpha", "start:beta", "stop:beta", "stop:alpha"]
