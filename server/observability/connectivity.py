# Small connectivity probes shared by the stub services (kfc-matchmaker,
# kfc-game-server, kfc-event-consumer). They exist to prove the
# docker-compose wiring (Redis reachable, Postgres/Citus reachable) is
# real, not to stand in for the Redis-backed queue/presence/checkpoint
# logic those services will own once Server_Design.md Phase 1 lands.
from __future__ import annotations

import asyncio
import logging

import psycopg2
import redis.asyncio as redis_asyncio

_logger = logging.getLogger("kfchess.connectivity")


async def wait_for_redis(redis_url: str, attempts: int = 30, delay_seconds: float = 2.0) -> None:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        client = redis_asyncio.from_url(redis_url)
        try:
            await client.ping()
            _logger.info("Redis reachable at %s (attempt %d)", redis_url, attempt)
            return
        except Exception as exc:  # noqa: BLE001 - broad on purpose while retrying
            last_error = exc
            _logger.warning("Redis not yet reachable (attempt %d/%d): %s", attempt, attempts, exc)
            await asyncio.sleep(delay_seconds)
        finally:
            await client.aclose()
    raise RuntimeError(f"Redis never became reachable at {redis_url}") from last_error


def _check_postgres_sync(database_url: str) -> None:
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    finally:
        conn.close()


async def wait_for_postgres(database_url: str, attempts: int = 30, delay_seconds: float = 2.0) -> None:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            await asyncio.to_thread(_check_postgres_sync, database_url)
            _logger.info("Postgres/Citus reachable (attempt %d)", attempt)
            return
        except Exception as exc:  # noqa: BLE001 - broad on purpose while retrying
            last_error = exc
            _logger.warning("Postgres not yet reachable (attempt %d/%d): %s", attempt, attempts, exc)
            await asyncio.sleep(delay_seconds)
    raise RuntimeError(f"Postgres never became reachable at {database_url}") from last_error
