# Shared test helpers — not a test module itself (no test_ functions).
# Builds a fresh in-memory-SQLite-backed AuthService/MatchesRepository pair,
# the same shape server/main.py wires from a real on-disk connection.
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Optional, Union

from server.auth.service import AuthService
from server.core.clock import Clock, FakeClock
from server.db.connection import create_connection
from server.db.matches_repository import MatchesRepository
from server.db.schema import init_schema
from server.db.users_repository import UsersRepository
from server.matchmaking.queue import MatchmakingQueue
from server.network.context import ServerContext


def build_test_repos() -> tuple[AuthService, MatchesRepository]:
    conn = create_connection(":memory:")
    init_schema(conn)
    return AuthService(UsersRepository(conn)), MatchesRepository(conn)


def build_test_context(clock: Optional[Clock] = None) -> ServerContext:
    auth_service, _ = build_test_repos()
    return ServerContext(auth_service=auth_service, clock=clock or FakeClock(), queue=MatchmakingQueue())


async def wait_until(
    predicate: Callable[[], Union[bool, Awaitable[bool]]], timeout: float = 2.0,
) -> None:
    # Polls a condition on every event-loop tick instead of sleeping a fixed
    # duration — resolves as soon as the awaited background task/consumer
    # actually runs, rather than hoping a hardcoded delay was long enough.
    deadline = time.monotonic() + timeout
    while True:
        result = predicate()
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            return
        if time.monotonic() > deadline:
            raise AssertionError("wait_until: timed out waiting for condition")
        await asyncio.sleep(0)
