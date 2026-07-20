# Composition root — builds every sub-package's objects, wires them together,
# and starts the WebSocket server. Nothing else in server/ contains wiring logic.
from __future__ import annotations

import asyncio
import logging

from server import config
from server.auth.service import AuthService
from server.core.bus import Bus
from server.core.clock import RealClock
from server.db.connection import create_connection
from server.db.matches_repository import MatchesRepository
from server.db.schema import init_schema
from server.db.users_repository import UsersRepository
from server.game.registry import MatchRegistry
from server.matchmaking.matchmaker import Matchmaker
from server.matchmaking.queue import MatchmakingQueue
from server.network.context import ServerContext
from server.network.server import serve_forever


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    bus = Bus()
    clock = RealClock()

    conn = create_connection(config.DB_PATH)
    init_schema(conn)
    users_repo = UsersRepository(conn)
    matches_repo = MatchesRepository(conn)
    auth_service = AuthService(users_repo)

    registry = MatchRegistry()
    queue = MatchmakingQueue(elo_range=config.QUEUE_ELO_RANGE)
    context = ServerContext(auth_service=auth_service, clock=clock, queue=queue)
    matchmaker = Matchmaker(
        queue=queue, registry=registry, bus=bus, clock=clock,
        auth_service=auth_service, matches_repo=matches_repo,
        poll_interval_seconds=config.QUEUE_POLL_INTERVAL_SECONDS,
        timeout_seconds=config.QUEUE_TIMEOUT_SECONDS,
    )

    matchmaker_task = asyncio.create_task(matchmaker.run_forever())
    try:
        await serve_forever(config.HOST, config.PORT, context)
    finally:
        matchmaker_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
