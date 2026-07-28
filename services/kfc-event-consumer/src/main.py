# kfc-event-consumer entrypoint (Server_Design.md §4: "Absorbs
# server/db/*, server/rating/*"; ADR-008 async event sourcing).
#
# Infra-first scope note: kfc-gateway's monolith still writes match
# results synchronously via server/db/matches_repository.py — there is no
# Redis Streams publisher yet for this service to batch-consume from
# (that publisher, plus this consumer's batched-write/Elo logic, is
# Server_Design.md Phase 1, ADR-008). This process is a real, running
# container that proves the compose wiring: it connects to Redis (the
# future event bus, ADR-008) and to Citus-sharded Postgres (the durable
# store it will batch-write into, ADR-001), and serves /healthz +
# /metrics on METRICS_PORT.
from __future__ import annotations

import asyncio
import logging

from server import config
from server.observability.connectivity import wait_for_postgres, wait_for_redis
from server.observability.health_server import serve_health

_logger = logging.getLogger("kfchess.kfc_event_consumer")


async def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    _logger.info(
        "kfc-event-consumer starting (scaffold — see module docstring); Redis=%s, Postgres=%s",
        config.REDIS_URL, config.DATABASE_URL,
    )
    await asyncio.gather(
        wait_for_redis(config.REDIS_URL),
        wait_for_postgres(config.DATABASE_URL),
    )

    async def ready() -> bool:
        return True

    await serve_health("0.0.0.0", config.METRICS_PORT, readiness_check=ready)
    _logger.info("kfc-event-consumer ready on :%d", config.METRICS_PORT)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(run())
