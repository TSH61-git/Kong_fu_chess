# kfc-matchmaker entrypoint (Server_Design.md §4: "Absorbs
# server/matchmaking/*, server/rooms/*"; state lives in Redis, ADR-003).
#
# Infra-first scope note: the real Elo-queue / room-assignment / crash
# recovery logic (ADR-003, ADR-010) still lives only in the monolith
# behind kfc-gateway (server/matchmaking/, server/rooms/) — extracting it
# into an independently-scaling service is Server_Design.md Phase 1. This
# process is a real, running container that proves the compose wiring: it
# connects to Redis (the queue/presence/checkpoint store this service will
# own) and serves /healthz + /metrics on METRICS_PORT.
from __future__ import annotations

import asyncio
import logging

from server import config
from server.observability.connectivity import wait_for_redis
from server.observability.health_server import serve_health

_logger = logging.getLogger("kfchess.kfc_matchmaker")


async def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    _logger.info("kfc-matchmaker starting (scaffold — see module docstring); Redis=%s", config.REDIS_URL)
    await wait_for_redis(config.REDIS_URL)

    async def ready() -> bool:
        return True

    await serve_health("0.0.0.0", config.METRICS_PORT, readiness_check=ready)
    _logger.info("kfc-matchmaker ready on :%d", config.METRICS_PORT)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(run())
