# Shared /healthz + /metrics HTTP endpoint, mounted on METRICS_PORT (9090)
# by every containerized service per Server_Design.md §4/§8 ("exposes 9090
# for health/metrics"). Deliberately has zero dependency on any one
# service's business logic so kfc-gateway, kfc-matchmaker, kfc-game-server
# and kfc-event-consumer can all share it as-is.
from __future__ import annotations

import logging
from typing import Awaitable, Callable, Optional

from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest

_logger = logging.getLogger("kfchess.health")

ReadinessCheck = Callable[[], Awaitable[bool]]


def build_health_app(readiness_check: Optional[ReadinessCheck] = None) -> web.Application:
    app = web.Application()

    async def healthz(_request: web.Request) -> web.Response:
        return web.Response(text="ok")

    async def readyz(_request: web.Request) -> web.Response:
        if readiness_check is None:
            return web.Response(text="ok")
        try:
            ok = await readiness_check()
        except Exception:
            _logger.exception("readiness check raised")
            ok = False
        return web.Response(text="ok" if ok else "not ready", status=200 if ok else 503)

    async def metrics(_request: web.Request) -> web.Response:
        # aiohttp's `content_type=` rejects a charset param, unlike the raw
        # header CONTENT_TYPE_LATEST ships (e.g. "text/plain; version=0.0.4;
        # charset=utf-8") — split it so aiohttp appends charset itself.
        content_type = CONTENT_TYPE_LATEST.split(";")[0].strip()
        return web.Response(body=generate_latest(REGISTRY), content_type=content_type, charset="utf-8")

    app.router.add_get("/healthz", healthz)
    app.router.add_get("/readyz", readyz)
    app.router.add_get("/metrics", metrics)
    return app


async def serve_health(host: str, port: int, readiness_check: Optional[ReadinessCheck] = None) -> None:
    app = build_health_app(readiness_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    _logger.info("health/metrics server listening on %s:%d", host, port)
