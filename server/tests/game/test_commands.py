import asyncio

from server.core.bus import Bus
from server.core.clock import FakeClock
from server.core.protocol import ErrorCode, Envelope
from server.game import commands
from server.game.match import MatchSession
from server.network.session import ClientSession, Role


class _FakeWebSocket:
    async def send(self, _message: str) -> None:
        pass


def _seated_session(match: MatchSession, role: Role) -> ClientSession:
    session = ClientSession("s1", _FakeWebSocket(), role)
    if role is Role.WHITE:
        match.white = session
    else:
        match.black = session
    return session


def _run_with_match(body) -> None:
    async def wrapper():
        match = MatchSession(bus=Bus(), clock=FakeClock())
        try:
            await body(match)
        finally:
            match._tick_task.cancel()

    asyncio.run(wrapper())


class TestHandleMove:
    def test_accepts_a_legal_move_for_the_authorized_color(self):
        async def body(match):
            session = _seated_session(match, Role.WHITE)
            envelope = Envelope(type="move", id="1", data={"cmd": "WPe2e3"})
            reply = commands.handle_move(session, envelope, match)
            assert '"ok": true' in reply

        _run_with_match(body)

    def test_rejects_command_color_that_does_not_match_the_seat(self):
        async def body(match):
            session = _seated_session(match, Role.WHITE)
            envelope = Envelope(type="move", id="1", data={"cmd": "BPe7e6"})
            reply = commands.handle_move(session, envelope, match)
            assert ErrorCode.NOT_YOUR_COLOR.value in reply

        _run_with_match(body)

    def test_rejects_a_square_the_session_does_not_actually_own(self):
        # The command's own color letter is internally consistent ("W"), but
        # e7 holds a black piece on the live board — the cross-check against
        # board state must catch this even though the string-only check
        # above it would not.
        async def body(match):
            session = _seated_session(match, Role.WHITE)
            envelope = Envelope(type="move", id="1", data={"cmd": "WPe7e6"})
            reply = commands.handle_move(session, envelope, match)
            assert ErrorCode.EMPTY_SOURCE.value in reply

        _run_with_match(body)

    def test_rejects_piece_letter_mismatch(self):
        async def body(match):
            session = _seated_session(match, Role.WHITE)
            envelope = Envelope(type="move", id="1", data={"cmd": "WQe2e3"})  # e2 holds a pawn
            reply = commands.handle_move(session, envelope, match)
            assert ErrorCode.PIECE_MISMATCH.value in reply

        _run_with_match(body)

    def test_malformed_command_rejected_before_touching_the_board(self):
        async def body(match):
            session = _seated_session(match, Role.WHITE)
            envelope = Envelope(type="move", id="1", data={"cmd": "bad"})
            reply = commands.handle_move(session, envelope, match)
            assert ErrorCode.MALFORMED_COMMAND.value in reply

        _run_with_match(body)

    def test_illegal_engine_move_surfaces_the_engine_reason(self):
        async def body(match):
            session = _seated_session(match, Role.WHITE)
            # Three squares forward is not a legal opening pawn move.
            envelope = Envelope(type="move", id="1", data={"cmd": "WPe2e5"})
            reply = commands.handle_move(session, envelope, match)
            assert ErrorCode.ILLEGAL_PIECE_MOVE.value in reply

        _run_with_match(body)


class TestHandleJump:
    def test_accepts_a_jump_for_the_authorized_color(self):
        async def body(match):
            session = _seated_session(match, Role.WHITE)
            envelope = Envelope(type="jump", id="1", data={"cmd": "WPe2e2"})
            reply = commands.handle_jump(session, envelope, match)
            assert '"ok": true' in reply

        _run_with_match(body)

    def test_rejects_wrong_color_claim(self):
        async def body(match):
            session = _seated_session(match, Role.BLACK)
            envelope = Envelope(type="jump", id="1", data={"cmd": "WPe2e2"})
            reply = commands.handle_jump(session, envelope, match)
            assert ErrorCode.NOT_YOUR_COLOR.value in reply

        _run_with_match(body)


class TestHandlePing:
    def test_always_acks(self):
        async def body(match):
            session = _seated_session(match, Role.WHITE)
            envelope = Envelope(type="ping", id="9", data={})
            reply = commands.handle_ping(session, envelope, match)
            assert '"ok": true' in reply

        _run_with_match(body)
