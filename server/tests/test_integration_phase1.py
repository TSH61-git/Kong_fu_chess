# End-to-end smoke tests over a real WebSocket connection — everything else
# in server/tests/ exercises the layers in isolation with fakes.
from __future__ import annotations

import asyncio
import json

import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from server.core.bus import Bus
from server.core.clock import RealClock
from server.game.match import MatchSession
from server.network.server import handle_connection

# A large tick interval keeps the periodic RoomStateTick broadcast from
# interleaving with the specific messages these tests assert on.
_NO_TICKS_DURING_TEST_MS = 60_000


async def _start_test_server(match: MatchSession):
    async def handler(websocket):
        await handle_connection(websocket, match)

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


def test_two_clients_are_seated_and_notified_when_the_match_is_ready():
    async def body():
        match = MatchSession(bus=Bus(), clock=RealClock(), tick_ms=_NO_TICKS_DURING_TEST_MS)
        server = await _start_test_server(match)
        try:
            port = server.sockets[0].getsockname()[1]
            uri = f"ws://localhost:{port}"

            async with connect(uri) as white_ws, connect(uri) as black_ws:
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
            match._tick_task.cancel()

    asyncio.run(body())


def test_two_clients_can_connect_and_trade_a_move():
    async def body():
        match = MatchSession(bus=Bus(), clock=RealClock(), tick_ms=_NO_TICKS_DURING_TEST_MS)
        server = await _start_test_server(match)
        try:
            port = server.sockets[0].getsockname()[1]
            uri = f"ws://localhost:{port}"

            async with connect(uri) as white_ws, connect(uri) as black_ws:
                await white_ws.send(json.dumps({"type": "move", "id": "1", "data": {"cmd": "WPe2e3"}}))

                white_ack = await _recv_until(white_ws, lambda m: m["type"] == "ack")
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
            match._tick_task.cancel()

    asyncio.run(body())


def test_a_third_connection_is_refused():
    async def body():
        match = MatchSession(bus=Bus(), clock=RealClock(), tick_ms=_NO_TICKS_DURING_TEST_MS)
        server = await _start_test_server(match)
        try:
            port = server.sockets[0].getsockname()[1]
            uri = f"ws://localhost:{port}"

            async with connect(uri), connect(uri), connect(uri) as third:
                with pytest.raises(ConnectionClosed):
                    await third.recv()
        finally:
            server.close()
            await server.wait_closed()
            match._tick_task.cancel()

    asyncio.run(body())


def test_move_claiming_the_wrong_color_is_rejected():
    async def body():
        match = MatchSession(bus=Bus(), clock=RealClock(), tick_ms=_NO_TICKS_DURING_TEST_MS)
        server = await _start_test_server(match)
        try:
            port = server.sockets[0].getsockname()[1]
            uri = f"ws://localhost:{port}"

            async with connect(uri) as white_ws, connect(uri):
                await white_ws.send(json.dumps({"type": "move", "id": "1", "data": {"cmd": "BPe7e6"}}))
                reply = await _recv_until(white_ws, lambda m: m["type"] == "error")
                assert reply["code"] == "NOT_YOUR_COLOR"
        finally:
            server.close()
            await server.wait_closed()
            match._tick_task.cancel()

    asyncio.run(body())
