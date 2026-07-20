# End-to-end smoke tests for Phase 2 (auth + Elo) over a real WebSocket
# connection, mirroring test_integration_phase1.py's style.
from __future__ import annotations

import asyncio
import json

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from chess_engine.engine.events import PieceCaptured
from chess_engine.model.piece import Color, Piece, PieceType
from server.core.bus import Bus
from server.core.clock import RealClock
from server.game.match import MatchSession
from server.network.server import handle_connection
from server.tests.support import build_test_repos

_NO_TICKS_DURING_TEST_MS = 60_000


def _new_match(tick_ms: int = _NO_TICKS_DURING_TEST_MS) -> tuple[MatchSession, object]:
    auth_service, matches_repo = build_test_repos()
    match = MatchSession(
        bus=Bus(), clock=RealClock(), auth_service=auth_service, matches_repo=matches_repo, tick_ms=tick_ms,
    )
    return match, auth_service


async def _start_test_server(match: MatchSession):
    async def handler(websocket):
        await handle_connection(websocket, match)

    return await serve(handler, "localhost", 0)


async def _recv_until(websocket, predicate, max_messages: int = 10) -> dict:
    for _ in range(max_messages):
        message = json.loads(await websocket.recv())
        if predicate(message):
            return message
    raise AssertionError(f"no message matching predicate arrived within {max_messages} messages")


def test_move_before_login_is_rejected():
    async def body():
        match, _ = _new_match()
        server = await _start_test_server(match)
        try:
            port = server.sockets[0].getsockname()[1]
            uri = f"ws://localhost:{port}"

            async with connect(uri) as white_ws, connect(uri):
                await white_ws.send(json.dumps({"type": "move", "id": "1", "data": {"cmd": "WPe2e3"}}))
                reply = await _recv_until(white_ws, lambda m: m["type"] == "error")
                assert reply["code"] == "NOT_AUTHENTICATED"
        finally:
            server.close()
            await server.wait_closed()
            match._tick_task.cancel()

    asyncio.run(body())


def test_register_then_login_round_trip():
    async def body():
        match, _ = _new_match()
        server = await _start_test_server(match)
        try:
            port = server.sockets[0].getsockname()[1]
            uri = f"ws://localhost:{port}"

            async with connect(uri) as white_ws, connect(uri):
                await white_ws.send(json.dumps(
                    {"type": "register", "id": "r1", "data": {"username": "alice", "password": "hunter2"}},
                ))
                register_ack = await _recv_until(white_ws, lambda m: m.get("in_reply_to") == "r1")
                assert register_ack["ok"] is True
                assert register_ack["data"]["username"] == "alice"
                assert register_ack["data"]["elo"] == 1200

                # A duplicate registration on the same account is rejected...
                await white_ws.send(json.dumps(
                    {"type": "register", "id": "r2", "data": {"username": "alice", "password": "hunter2"}},
                ))
                dup_reply = await _recv_until(white_ws, lambda m: m.get("in_reply_to") == "r2")
                assert dup_reply["type"] == "error"
                assert dup_reply["code"] == "USERNAME_TAKEN"

                # ...but logging in with the right credentials succeeds.
                await white_ws.send(json.dumps(
                    {"type": "login", "id": "l1", "data": {"username": "alice", "password": "hunter2"}},
                ))
                login_ack = await _recv_until(white_ws, lambda m: m.get("in_reply_to") == "l1")
                assert login_ack["ok"] is True

                # And the wrong password is rejected.
                await white_ws.send(json.dumps(
                    {"type": "login", "id": "l2", "data": {"username": "alice", "password": "wrong"}},
                ))
                bad_login_reply = await _recv_until(white_ws, lambda m: m.get("in_reply_to") == "l2")
                assert bad_login_reply["type"] == "error"
                assert bad_login_reply["code"] == "INVALID_CREDENTIALS"
        finally:
            server.close()
            await server.wait_closed()
            match._tick_task.cancel()

    asyncio.run(body())


def test_a_king_capture_persists_a_result_and_updates_elo():
    # The real-time motion physics of an actual king capture belong to
    # Phase 1's engine tests (and server/tests/game/test_match.py's
    # TestRecordResult, which exercises this exact path against the engine
    # directly). What Phase 2 adds is: authenticate both seats over the
    # wire, then confirm the existing GameOver hook reaches the database.
    # So: real websocket register + a real move (proving NOT_AUTHENTICATED
    # lifts after login), then trigger game-over the same way the engine
    # itself would report a king capture, and confirm the broadcast and the
    # persisted Elo change.
    async def body():
        match, auth_service = _new_match()
        server = await _start_test_server(match)
        try:
            port = server.sockets[0].getsockname()[1]
            uri = f"ws://localhost:{port}"

            async with connect(uri) as white_ws, connect(uri) as black_ws:
                await white_ws.send(json.dumps(
                    {"type": "register", "id": "r1", "data": {"username": "white_player", "password": "pw"}},
                ))
                await _recv_until(white_ws, lambda m: m.get("in_reply_to") == "r1")
                await black_ws.send(json.dumps(
                    {"type": "register", "id": "r1", "data": {"username": "black_player", "password": "pw"}},
                ))
                await _recv_until(black_ws, lambda m: m.get("in_reply_to") == "r1")

                await white_ws.send(json.dumps({"type": "move", "id": "1", "data": {"cmd": "WPe2e3"}}))
                move_ack = await _recv_until(white_ws, lambda m: m.get("in_reply_to") == "1")
                assert move_ack["ok"] is True

                match.stack.engine.events.publish(
                    PieceCaptured(piece=Piece(PieceType.KING, Color.WHITE), captured_by=Color.BLACK),
                )
                match.stack.engine.notify_king_captured()

                await _recv_until(white_ws, lambda m: m.get("event") == "game_over", max_messages=20)
                await asyncio.sleep(0.05)  # let the async _record_result task finish

                white_user = await auth_service.users_repo.get_by_username("white_player")
                black_user = await auth_service.users_repo.get_by_username("black_player")
                assert white_user.elo < 1200
                assert black_user.elo > 1200
        finally:
            server.close()
            await server.wait_closed()
            match._tick_task.cancel()

    asyncio.run(body())
