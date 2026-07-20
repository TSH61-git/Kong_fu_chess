# End-to-end smoke tests over a real WebSocket connection — everything else
# in server/tests/ exercises the layers in isolation with fakes.
from __future__ import annotations

import asyncio
import json

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from server.core.bus import Bus
from server.core.clock import RealClock
from server.game.match import MatchSession
from server.network.server import handle_connection
from server.tests.support import build_test_repos

# A large tick interval keeps the periodic RoomStateTick broadcast from
# interleaving with the specific messages these tests assert on.
_NO_TICKS_DURING_TEST_MS = 60_000


def _new_match(tick_ms: int = _NO_TICKS_DURING_TEST_MS) -> MatchSession:
    auth_service, matches_repo = build_test_repos()
    return MatchSession(
        bus=Bus(), clock=RealClock(), auth_service=auth_service, matches_repo=matches_repo, tick_ms=tick_ms,
    )


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
        match = _new_match()
        server = await _start_test_server(match)
        try:
            port = server.sockets[0].getsockname()[1]
            uri = f"ws://localhost:{port}"

            async with connect(uri) as white_ws, connect(uri) as black_ws:
                # A connection is unseated and unauthenticated until it
                # registers/logs in — the "seated" notice only fires then.
                await white_ws.send(json.dumps(
                    {"type": "register", "id": "r1", "data": {"username": "white_player", "password": "pw"}},
                ))
                await black_ws.send(json.dumps(
                    {"type": "register", "id": "r1", "data": {"username": "black_player", "password": "pw"}},
                ))

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
        match = _new_match()
        server = await _start_test_server(match)
        try:
            port = server.sockets[0].getsockname()[1]
            uri = f"ws://localhost:{port}"

            async with connect(uri) as white_ws, connect(uri) as black_ws:
                # Moves require an authenticated, seated session as of Phase
                # 2 — and black must also be seated, or it won't be in the
                # room's broadcast roster to receive the move at all.
                await white_ws.send(json.dumps(
                    {"type": "register", "id": "r1", "data": {"username": "white_player", "password": "pw"}},
                ))
                await _recv_until(white_ws, lambda m: m["type"] == "ack" and m.get("in_reply_to") == "r1")
                await black_ws.send(json.dumps(
                    {"type": "register", "id": "r1", "data": {"username": "black_player", "password": "pw"}},
                ))
                await _recv_until(black_ws, lambda m: m["type"] == "ack" and m.get("in_reply_to") == "r1")

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
            match._tick_task.cancel()

    asyncio.run(body())


def test_a_third_authenticated_session_is_refused_a_seat():
    # Connections are no longer refused at the transport level — a match's
    # capacity is only enforced once a session tries to actually be seated,
    # which now happens on a successful register/login (see auth/commands.py).
    async def body():
        match = _new_match()
        server = await _start_test_server(match)
        try:
            port = server.sockets[0].getsockname()[1]
            uri = f"ws://localhost:{port}"

            async with connect(uri) as white_ws, connect(uri) as black_ws, connect(uri) as third_ws:
                # Sequential and awaited: seat order must be deterministic
                # for this test to mean anything.
                replies = {}
                for ws, username in ((white_ws, "p1"), (black_ws, "p2"), (third_ws, "p3")):
                    await ws.send(json.dumps(
                        {"type": "register", "id": "r1", "data": {"username": username, "password": "pw"}},
                    ))
                    replies[username] = await _recv_until(ws, lambda m: m.get("in_reply_to") == "r1")

                assert replies["p1"]["type"] == "ack"
                assert replies["p2"]["type"] == "ack"
                assert replies["p3"]["type"] == "error"
                assert replies["p3"]["code"] == "MATCH_FULL"
        finally:
            server.close()
            await server.wait_closed()
            match._tick_task.cancel()

    asyncio.run(body())


def test_move_claiming_the_wrong_color_is_rejected():
    async def body():
        match = _new_match()
        server = await _start_test_server(match)
        try:
            port = server.sockets[0].getsockname()[1]
            uri = f"ws://localhost:{port}"

            async with connect(uri) as white_ws, connect(uri):
                await white_ws.send(json.dumps(
                    {"type": "register", "id": "r1", "data": {"username": "white_player", "password": "pw"}},
                ))
                await _recv_until(white_ws, lambda m: m["type"] == "ack" and m.get("in_reply_to") == "r1")

                await white_ws.send(json.dumps({"type": "move", "id": "1", "data": {"cmd": "BPe7e6"}}))
                reply = await _recv_until(white_ws, lambda m: m["type"] == "error")
                assert reply["code"] == "NOT_YOUR_COLOR"
        finally:
            server.close()
            await server.wait_closed()
            match._tick_task.cancel()

    asyncio.run(body())
