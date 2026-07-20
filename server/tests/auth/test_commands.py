import asyncio

from server.auth import commands
from server.core.bus import Bus
from server.core.clock import FakeClock
from server.core.protocol import ErrorCode, Envelope
from server.game.events import RoomMatchReady
from server.game.match import MatchSession
from server.network.session import ClientSession, Role
from server.tests.support import build_test_repos


class _FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, message: str) -> None:
        self.sent.append(message)


def _run_with_match(body) -> None:
    async def wrapper():
        auth_service, matches_repo = build_test_repos()
        match = MatchSession(bus=Bus(), clock=FakeClock(), auth_service=auth_service, matches_repo=matches_repo)
        try:
            await body(match)
        finally:
            match._tick_task.cancel()

    asyncio.run(wrapper())


class TestHandleRegister:
    def test_registering_acks_seats_and_attaches_identity_to_the_session(self):
        async def body(match):
            session = ClientSession("s1", _FakeWebSocket())
            envelope = Envelope(type="register", id="1", data={"username": "alice", "password": "hunter2"})

            reply = await commands.handle_register(session, envelope, match)

            assert '"ok": true' in reply
            assert session.user_id is not None
            assert session.username == "alice"
            assert session.role is Role.WHITE
            assert match.white is session
            assert any('"event": "seated"' in msg for msg in session.websocket.sent)

        _run_with_match(body)

    def test_duplicate_username_is_rejected_and_session_stays_unseated(self):
        async def body(match):
            await match.auth_service.register("alice", "hunter2")
            session = ClientSession("s1", _FakeWebSocket())
            envelope = Envelope(type="register", id="1", data={"username": "alice", "password": "different"})

            reply = await commands.handle_register(session, envelope, match)

            assert ErrorCode.USERNAME_TAKEN.value in reply
            assert session.user_id is None
            assert session.role is None

        _run_with_match(body)

    def test_missing_password_is_malformed(self):
        async def body(match):
            session = ClientSession("s1", _FakeWebSocket())
            envelope = Envelope(type="register", id="1", data={"username": "alice"})

            reply = await commands.handle_register(session, envelope, match)

            assert ErrorCode.MALFORMED_COMMAND.value in reply
            assert session.role is None

        _run_with_match(body)

    def test_a_third_registration_is_rejected_as_match_full(self):
        async def body(match):
            await commands.handle_register(
                ClientSession("s1", _FakeWebSocket()), Envelope(type="register", id="1",
                                                                 data={"username": "alice", "password": "pw"}), match,
            )
            await commands.handle_register(
                ClientSession("s2", _FakeWebSocket()), Envelope(type="register", id="1",
                                                                 data={"username": "bob", "password": "pw"}), match,
            )
            third = ClientSession("s3", _FakeWebSocket())
            reply = await commands.handle_register(
                third, Envelope(type="register", id="1", data={"username": "carol", "password": "pw"}), match,
            )

            assert ErrorCode.MATCH_FULL.value in reply
            assert third.role is None
            assert third.user_id is None  # rolled back — not left in a half-authenticated state

        _run_with_match(body)


class TestHandleLogin:
    def test_login_acks_seats_and_attaches_identity_to_the_session(self):
        async def body(match):
            await match.auth_service.register("alice", "hunter2")
            session = ClientSession("s1", _FakeWebSocket())
            envelope = Envelope(type="login", id="1", data={"username": "alice", "password": "hunter2"})

            reply = await commands.handle_login(session, envelope, match)

            assert '"ok": true' in reply
            assert session.username == "alice"
            assert session.role is Role.WHITE
            assert match.white is session

        _run_with_match(body)

    def test_wrong_password_is_rejected_and_session_stays_unseated(self):
        async def body(match):
            await match.auth_service.register("alice", "hunter2")
            session = ClientSession("s1", _FakeWebSocket())
            envelope = Envelope(type="login", id="1", data={"username": "alice", "password": "wrong"})

            reply = await commands.handle_login(session, envelope, match)

            assert ErrorCode.INVALID_CREDENTIALS.value in reply
            assert session.user_id is None
            assert session.role is None

        _run_with_match(body)

    def test_second_login_publishes_match_ready(self):
        async def body(match):
            bus_events = []

            async def handler(event):
                bus_events.append(event)

            match.bus.subscribe(f"room:{match.room_id}", handler)

            await match.auth_service.register("alice", "hunter2")
            await match.auth_service.register("bob", "hunter2")

            await commands.handle_login(
                ClientSession("s1", _FakeWebSocket()),
                Envelope(type="login", id="1", data={"username": "alice", "password": "hunter2"}), match,
            )
            # not ready with only one seat filled
            assert not any(isinstance(event, RoomMatchReady) for event in bus_events)

            await commands.handle_login(
                ClientSession("s2", _FakeWebSocket()),
                Envelope(type="login", id="1", data={"username": "bob", "password": "hunter2"}), match,
            )
            await asyncio.sleep(0.01)
            assert any(isinstance(event, RoomMatchReady) for event in bus_events)

        _run_with_match(body)
