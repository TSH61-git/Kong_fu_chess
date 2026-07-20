# Async publish/subscribe bus. Each subscription owns a bounded queue and a
# dedicated consumer task, so one slow or failing subscriber can never block
# publish() or any other subscriber — only its own queue backs up.
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

Handler = Callable[[object], Awaitable[None]]
Unsubscribe = Callable[[], None]

_logger = logging.getLogger("kfchess.bus")


class _Subscription:
    def __init__(self, topic: str, handler: Handler, maxsize: int) -> None:
        self.topic = topic
        self.queue: asyncio.Queue[object] = asyncio.Queue(maxsize=maxsize)
        self.task = asyncio.create_task(self._consume(handler))

    async def _consume(self, handler: Handler) -> None:
        while True:
            event = await self.queue.get()
            try:
                await handler(event)
            except Exception:
                _logger.exception("Bus subscriber raised while handling %r on topic %r", event, self.topic)

    def stop(self) -> None:
        self.task.cancel()


class Bus:
    def __init__(self) -> None:
        self._subscriptions: dict[str, list[_Subscription]] = {}

    def subscribe(self, topic: str, handler: Handler, maxsize: int = 1000) -> Unsubscribe:
        subscription = _Subscription(topic, handler, maxsize)
        self._subscriptions.setdefault(topic, []).append(subscription)

        def unsubscribe() -> None:
            subscription.stop()
            subscriptions = self._subscriptions.get(topic)
            if subscriptions and subscription in subscriptions:
                subscriptions.remove(subscription)

        return unsubscribe

    def publish(self, topic: str, event: object) -> None:
        for subscription in self._subscriptions.get(topic, ()):
            try:
                subscription.queue.put_nowait(event)
            except asyncio.QueueFull:
                _logger.warning("Dropping event %r on topic %r: subscriber queue full", event, topic)
