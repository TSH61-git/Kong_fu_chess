# Minimal synchronous publish/subscribe bus — dispatch is immediate and
# in-process, which is all a single-threaded, per-frame engine needs.
from __future__ import annotations

from collections import defaultdict
from typing import Callable, TypeVar

E = TypeVar("E")


class EventManager:
    def __init__(self) -> None:
        self._subscribers: dict[type, list[Callable[[object], None]]] = defaultdict(list)

    def subscribe(self, event_type: type[E], handler: Callable[[E], None]) -> None:
        self._subscribers[event_type].append(handler)

    def publish(self, event: object) -> None:
        for handler in self._subscribers[type(event)]:
            handler(event)
