# The only async code in this package: a thin driver polling
# MatchmakingQueue's pure methods roughly once a second and acting on the
# results — pairing, seating, and expiry notices.
from __future__ import annotations

import asyncio

from server import config
from server.auth.service import AuthService
from server.core.bus import Bus
from server.core.clock import Clock
from server.core.protocol import encode_notice
from server.db.matches_repository import MatchesRepository
from server.game.match import MatchSession
from server.game.registry import MatchRegistry
from server.matchmaking.queue import MatchmakingQueue, QueueEntry


class Matchmaker:
    def __init__(
        self,
        queue: MatchmakingQueue,
        registry: MatchRegistry,
        bus: Bus,
        clock: Clock,
        auth_service: AuthService,
        matches_repo: MatchesRepository,
        poll_interval_seconds: float = config.QUEUE_POLL_INTERVAL_SECONDS,
        timeout_seconds: float = config.QUEUE_TIMEOUT_SECONDS,
        tick_ms: int = config.TICK_MS,
    ) -> None:
        self._queue = queue
        self._registry = registry
        self._bus = bus
        self._clock = clock
        self._auth_service = auth_service
        self._matches_repo = matches_repo
        self._poll_interval_seconds = poll_interval_seconds
        self._timeout_seconds = timeout_seconds
        self._tick_ms = tick_ms

    async def run_forever(self) -> None:
        while True:
            await asyncio.sleep(self._poll_interval_seconds)
            await self.poll_once()

    async def poll_once(self) -> None:
        now = self._clock.now()

        for entry_a, entry_b in self._queue.find_pairings(now):
            await self._seat_pair(entry_a, entry_b)

        for entry in self._queue.expire(now, self._timeout_seconds):
            await entry.session.send(encode_notice("queue_timeout", {}))

    async def _seat_pair(self, entry_a: QueueEntry, entry_b: QueueEntry) -> None:
        match = MatchSession(
            bus=self._bus, clock=self._clock, auth_service=self._auth_service,
            matches_repo=self._matches_repo, tick_ms=self._tick_ms, on_ended=self._registry.remove,
        )
        self._registry.add(match)

        for entry in (entry_a, entry_b):
            match.try_seat(entry.session)
            # Same "seated" notice shape auth/commands.py used to send at
            # login-time seating, before Phase 3 moved seating here.
            await entry.session.send(encode_notice("seated", {"role": entry.session.role.name.lower()}))
