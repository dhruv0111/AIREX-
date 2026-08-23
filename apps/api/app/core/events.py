"""Domain event foundation (spec §42).

Phase 0 establishes the event interface and an in-process bus; Redis-backed
publishing and the transactional outbox are introduced with the async worker
surface. Events are used to decouple side effects from request handling.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

logger = logging.getLogger("airex.events")


@dataclass
class DomainEvent:
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class EventPublisher(Protocol):
    def publish(self, event: DomainEvent) -> None: ...


class InMemoryEventBus:
    """In-process publisher with optional subscriber list (tests/dev)."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[DomainEvent], None]]] = {}
        self.published: list[DomainEvent] = []

    def subscribe(self, event_type: str, handler: Callable[[DomainEvent], None]) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    def publish(self, event: DomainEvent) -> None:
        self.published.append(event)
        for handler in self._subscribers.get(event.event_type, []):
            try:
                handler(event)
            except Exception:  # pragma: no cover - subscriber isolation
                logger.exception("Event handler failed for %s", event.event_type)


_bus = InMemoryEventBus()


def get_event_bus() -> InMemoryEventBus:
    return _bus
