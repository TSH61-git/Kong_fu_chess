import asyncio

from server.core.bus import Bus
from server.core.clock import FakeClock
from server.core.protocol import ErrorCode, Envelope
from server.game.match import MatchSession
from server.network.dispatch import dispatch
from server.network.session import ClientSession, Role


class _FakeWebSocket:
    async def send(self, _message: str) -> None:
        pass


def _run_with_match(body) -> None:
    async def wrapper():
        match = MatchSession(bus=Bus(), clock=FakeClock())
        try:
            await body(match)
        finally:
            match._tick_task.cancel()

    asyncio.run(wrapper())


def test_dispatch_routes_move_to_handle_move():
    async def body(match):
        session = ClientSession("s1", _FakeWebSocket(), Role.WHITE)
        match.white = session
        envelope = Envelope(type="move", id="1", data={"cmd": "WPe2e3"})
        assert '"ok": true' in dispatch(session, envelope, match)

    _run_with_match(body)


def test_dispatch_routes_ping_to_handle_ping():
    async def body(match):
        session = ClientSession("s1", _FakeWebSocket(), Role.WHITE)
        envelope = Envelope(type="ping", id="1", data={})
        assert '"ok": true' in dispatch(session, envelope, match)

    _run_with_match(body)


def test_dispatch_rejects_unknown_command_type():
    async def body(match):
        session = ClientSession("s1", _FakeWebSocket(), Role.WHITE)
        envelope = Envelope(type="teleport", id="1", data={})
        assert ErrorCode.UNKNOWN_COMMAND_TYPE.value in dispatch(session, envelope, match)

    _run_with_match(body)
