# End-to-end smoke tests over a real WebSocket connection — everything else
# in server/tests/ exercises the layers in isolation with fakes.
from __future__ import annotations

import asyncio
import json
from typing import Optional

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from server.core.bus import Bus
from server.core.clock import Clock, FakeClock, RealClock
from server.game.registry import MatchRegistry
from server.matchmaking.matchmaker import Matchmaker
from server.matchmaking.queue import MatchmakingQueue
from server.network.context import ServerContext
from server.network.server import handle_connection
from server.tests.support import build_test_repos

# A large tick interval keeps the periodic RoomStateTick broadcast from
# interleaving with the specific messages these tests assert on.
_NO_TICKS_DURING_TEST_MS = 60_000


def _new_context_and_matchmaker(clock: Optional[Clock] = None) -> tuple[ServerContext, Matchmaker]:
    auth_service, matches_repo = build_test_repos()
    clock = clock or RealClock()
    queue = MatchmakingQueue()
    registry = MatchRegistry()
    bus = Bus()
    context = ServerContext(auth_service=auth_service, clock=clock, queue=queue, registry=registry)
    matchmaker = Matchmaker(
        queue=queue, registry=registry, bus=bus, clock=clock,
        auth_service=auth_service, matches_repo=matches_repo, tick_ms=_NO_TICKS_DURING_TEST_MS,
    )
    return context, matchmaker


async def _start_test_server(context: ServerContext):
    async def handler(websocket):
        await handle_connection(websocket, context)

    return await serve(handler, "localhost", 0)


async def _recv_until(websocket, predicate, max_messages: int = 10) -> dict:
    # Every connection now also receives a "seated" notice and a "match_ready"
    # broadcast, whose exact arrival order relative to each other/other
    # broadcasts isn't guaranteed — tests key off message content, not position.
    for _ in range(max_messages):
        message = json.loads(await websocket.recv())
        if predicate(message):
            return message
    raise AssertionError(f"no message matching predicate arrived within {max_messages} messages")


async def _register_and_queue(ws, username: str) -> None:
    await ws.send(json.dumps(
        {"type": "register", "id": "r1", "data": {"username": username, "password": "pw"}},
    ))
    await _recv_until(ws, lambda m: m["type"] == "ack" and m.get("in_reply_to") == "r1")
    await ws.send(json.dumps({"type": "queue_join", "id": "q1", "data": {}}))
    await _recv_until(ws, lambda m: m.get("in_reply_to") == "q1")


def test_two_clients_are_seated_and_notified_when_the_match_is_ready():
    async def body():
        context, matchmaker = _new_context_and_matchmaker()
        server = await _start_test_server(context)
        try:
            port = server.sockets[0].getsockname()[1]
            uri = f"ws://localhost:{port}"

            async with connect(uri) as white_ws, connect(uri) as black_ws:
                await _register_and_queue(white_ws, "white_player")
                await _register_and_queue(black_ws, "black_player")
                await matchmaker.poll_once()

                white_seated = await _recv_until(white_ws, lambda m: m["type"] == "notice" and m["event"] == "seated")
                black_seated = await _recv_until(black_ws, lambda m: m["type"] == "notice" and m["event"] == "seated")
                assert white_seated["data"]["role"] == "white"
                assert black_seated["data"]["role"] == "black"

                white_ready = await _recv_until(white_ws, lambda m: m.get("event") == "match_ready")
                black_ready = await _recv_until(black_ws, lambda m: m.get("event") == "match_ready")
                assert white_ready["type"] == "broadcast"
                assert black_ready["type"] == "broadcast"
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(body())


def test_two_clients_can_connect_and_trade_a_move():
    async def body():
        context, matchmaker = _new_context_and_matchmaker()
        server = await _start_test_server(context)
        try:
            port = server.sockets[0].getsockname()[1]
            uri = f"ws://localhost:{port}"

            async with connect(uri) as white_ws, connect(uri) as black_ws:
                await _register_and_queue(white_ws, "white_player")
                await _register_and_queue(black_ws, "black_player")
                await matchmaker.poll_once()
                await _recv_until(white_ws, lambda m: m.get("event") == "match_ready")
                await _recv_until(black_ws, lambda m: m.get("event") == "match_ready")

                await white_ws.send(json.dumps({"type": "move", "id": "1", "data": {"cmd": "WPe2e3"}}))

                white_ack = await _recv_until(white_ws, lambda m: m["type"] == "ack" and m.get("in_reply_to") == "1")
                white_broadcast = await _recv_until(
                    white_ws, lambda m: m.get("event") == "move_accepted",
                )
                black_broadcast = await _recv_until(
                    black_ws, lambda m: m.get("event") == "move_accepted",
                )

                assert white_ack["ok"] is True
                assert white_broadcast["type"] == "broadcast"
                assert black_broadcast["type"] == "broadcast"
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(body())


def test_move_claiming_the_wrong_color_is_rejected():
    async def body():
        context, matchmaker = _new_context_and_matchmaker()
        server = await _start_test_server(context)
        try:
            port = server.sockets[0].getsockname()[1]
            uri = f"ws://localhost:{port}"

            async with connect(uri) as white_ws, connect(uri) as black_ws:
                await _register_and_queue(white_ws, "white_player")
                await _register_and_queue(black_ws, "black_player")
                await matchmaker.poll_once()
                await _recv_until(white_ws, lambda m: m.get("event") == "match_ready")

                await white_ws.send(json.dumps({"type": "move", "id": "1", "data": {"cmd": "BPe7e6"}}))
                reply = await _recv_until(white_ws, lambda m: m["type"] == "error")
                assert reply["code"] == "NOT_YOUR_COLOR"
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(body())


def test_a_lone_queued_session_receives_a_queue_timeout_notice():
    async def body():
        clock = FakeClock()
        context, matchmaker = _new_context_and_matchmaker(clock=clock)
        server = await _start_test_server(context)
        try:
            port = server.sockets[0].getsockname()[1]
            uri = f"ws://localhost:{port}"

            async with connect(uri) as ws:
                await _register_and_queue(ws, "lone_player")

                clock.advance(61)
                await matchmaker.poll_once()

                timeout_notice = await _recv_until(
                    ws, lambda m: m["type"] == "notice" and m["event"] == "queue_timeout",
                )
                assert timeout_notice["data"] == {}
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(body())
