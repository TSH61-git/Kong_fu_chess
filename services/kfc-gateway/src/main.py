# kfc-gateway entrypoint (Server_Design.md §4: "Absorbs server/network/*").
#
# Infra-first scope note: this container runs the existing, fully working
# server/main.py monolith (login + matchmaking + game hosting in one
# asyncio process, SQLite-backed) alongside the shared health/metrics
# server, rather than a real network-only extraction. A true split — this
# process handling only auth/matchmaking-relay/redirect issuance, with
# kfc-matchmaker and kfc-game-server owning their own state over Redis —
# is Server_Design.md Phase 1 and is intentionally out of scope here; see
# CLAUDE.md and the docker-compose comments for what's real vs. scaffold.
from __future__ import annotations

import asyncio
import logging

from server import config
from server.main import main as run_monolith
from server.observability.health_server import serve_health

_logger = logging.getLogger("kfchess.kfc_gateway")


async def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    _logger.info(
        "kfc-gateway starting: game port %s:%d, health/metrics port %d",
        config.HOST, config.PORT, config.METRICS_PORT,
    )
    await asyncio.gather(
        run_monolith(),
        serve_health(config.HOST if config.HOST != "localhost" else "0.0.0.0", config.METRICS_PORT),
    )


if __name__ == "__main__":
    asyncio.run(run())
