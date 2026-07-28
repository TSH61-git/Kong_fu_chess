# kfc-game-server entrypoint (Server_Design.md §4: "Absorbs server/game/*
# + chess_engine/ (unchanged)"; stateful, in-memory rooms, ADR-005).
#
# Infra-first scope note: real room hosting still runs only inside the
# monolith behind kfc-gateway (server/game/, chess_engine/) — extracting
# it so clients connect here directly post-redirect (ADR-009) is
# Server_Design.md Phase 1. This process is a real, running container that
# proves the compose wiring: it connects to Redis (ADR-010 checkpoint
# store) and listens on both ports Server_Design.md §4 assigns this
# service — 9090 for health/metrics, and 7000 as the public game port
# (currently a placeholder TCP listener, not the real wire protocol).
from __future__ import annotations

import asyncio
import logging

from server import config
from server.observability.connectivity import wait_for_redis
from server.observability.health_server import serve_health

_logger = logging.getLogger("kfchess.kfc_game_server")

GAME_PORT = 7000


async def _handle_placeholder_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    peer = writer.get_extra_info("peername")
    _logger.info("connection on placeholder game port from %s (ADR-009 redirect target not yet implemented)", peer)
    writer.close()
    await writer.wait_closed()


async def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    _logger.info(
        "kfc-game-server starting (scaffold — see module docstring); Redis=%s, game_port=%d",
        config.REDIS_URL, GAME_PORT,
    )
    await wait_for_redis(config.REDIS_URL)

    game_server = await asyncio.start_server(_handle_placeholder_connection, "0.0.0.0", GAME_PORT)

    async def ready() -> bool:
        return True

    await serve_health("0.0.0.0", config.METRICS_PORT, readiness_check=ready)
    _logger.info("kfc-game-server ready: health :%d, game port :%d", config.METRICS_PORT, GAME_PORT)
    async with game_server:
        await game_server.serve_forever()


if __name__ == "__main__":
    asyncio.run(run())
