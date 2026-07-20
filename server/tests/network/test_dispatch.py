import asyncio

from server.core.bus import Bus
from server.core.clock import FakeClock
from server.core.protocol import ErrorCode, Envelope
from server.game.match import MatchSession
from server.network.dispatch import dispatch
from server.network.session import ClientSession, Role
from server.tests.support import build_test_repos


class _FakeWebSocket:
    async def send(self, _message: str) -> None:
        pass


def _run_with_match(body) -> None:
    async def wrapper():
        auth_service, matches_repo = build_test_repos()
        match = MatchSession(bus=Bus(), clock=FakeClock(), auth_service=auth_service, matches_repo=matches_repo)
        try:
            await body(match)
        finally:
            match._tick_task.cancel()

    asyncio.run(wrapper())


def test_dispatch_routes_move_to_handle_move():
    async def body(match):
        session = ClientSession("s1", _FakeWebSocket())
        session.user_id = 1
        session.role = Role.WHITE
        match.white = session
        envelope = Envelope(type="move", id="1", data={"cmd": "WPe2e3"})
        assert '"ok": true' in await dispatch(session, envelope, match)

    _run_with_match(body)


def test_dispatch_routes_ping_to_handle_ping():
    async def body(match):
        session = ClientSession("s1", _FakeWebSocket())
        envelope = Envelope(type="ping", id="1", data={})
        assert '"ok": true' in await dispatch(session, envelope, match)

    _run_with_match(body)


def test_dispatch_routes_register_to_handle_register():
    async def body(match):
        session = ClientSession("s1", _FakeWebSocket())
        envelope = Envelope(type="register", id="1", data={"username": "alice", "password": "hunter2"})
        assert '"ok": true' in await dispatch(session, envelope, match)
        assert session.username == "alice"
        assert session.role is Role.WHITE  # seated as a side effect of a successful register
        assert match.white is session

    _run_with_match(body)


def test_dispatch_routes_login_to_handle_login():
    async def body(match):
        await match.auth_service.register("alice", "hunter2")
        session = ClientSession("s1", _FakeWebSocket())
        envelope = Envelope(type="login", id="1", data={"username": "alice", "password": "hunter2"})
        assert '"ok": true' in await dispatch(session, envelope, match)
        assert session.username == "alice"
        assert session.role is Role.WHITE

    _run_with_match(body)


def test_dispatch_rejects_unknown_command_type():
    async def body(match):
        session = ClientSession("s1", _FakeWebSocket())
        envelope = Envelope(type="teleport", id="1", data={})
        assert ErrorCode.UNKNOWN_COMMAND_TYPE.value in await dispatch(session, envelope, match)

    _run_with_match(body)
