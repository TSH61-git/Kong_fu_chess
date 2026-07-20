# Composition root — builds every sub-package's objects, wires them together,
# and starts the WebSocket server. Nothing else in server/ contains wiring logic.
from __future__ import annotations

import asyncio
import logging

from server import config
from server.core.bus import Bus
from server.core.clock import RealClock
from server.game.match import MatchSession
from server.network.server import serve_forever


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    bus = Bus()
    clock = RealClock()
    match = MatchSession(bus=bus, clock=clock)
    await serve_forever(config.HOST, config.PORT, match)


if __name__ == "__main__":
    asyncio.run(main())
