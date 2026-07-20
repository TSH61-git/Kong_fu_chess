import asyncio

from server.auth import commands
from server.core.protocol import ErrorCode, Envelope
from server.network.session import ClientSession, Role
from server.tests.support import build_test_context


class _FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, message: str) -> None:
        self.sent.append(message)


def _run(body) -> None:
    asyncio.run(body())


class TestHandleRegister:
    def test_registering_acks_and_attaches_identity_without_seating(self):
        async def body():
            context = build_test_context()
            session = ClientSession("s1", _FakeWebSocket())
            envelope = Envelope(type="register", id="1", data={"username": "alice", "password": "hunter2"})

            reply = await commands.handle_register(session, envelope, context)

            assert '"ok": true' in reply
            assert session.user_id is not None
            assert session.username == "alice"
            assert session.role is None
            assert session.current_match is None

        _run(body)

    def test_duplicate_username_is_rejected_and_session_stays_unauthenticated(self):
        async def body():
            context = build_test_context()
            await context.auth_service.register("alice", "hunter2")
            session = ClientSession("s1", _FakeWebSocket())
            envelope = Envelope(type="register", id="1", data={"username": "alice", "password": "different"})

            reply = await commands.handle_register(session, envelope, context)

            assert ErrorCode.USERNAME_TAKEN.value in reply
            assert session.user_id is None

        _run(body)

    def test_missing_password_is_malformed(self):
        async def body():
            context = build_test_context()
            session = ClientSession("s1", _FakeWebSocket())
            envelope = Envelope(type="register", id="1", data={"username": "alice"})

            reply = await commands.handle_register(session, envelope, context)

            assert ErrorCode.MALFORMED_COMMAND.value in reply
            assert session.user_id is None

        _run(body)


class TestHandleLogin:
    def test_login_acks_and_attaches_identity_without_seating(self):
        async def body():
            context = build_test_context()
            await context.auth_service.register("alice", "hunter2")
            session = ClientSession("s1", _FakeWebSocket())
            envelope = Envelope(type="login", id="1", data={"username": "alice", "password": "hunter2"})

            reply = await commands.handle_login(session, envelope, context)

            assert '"ok": true' in reply
            assert session.username == "alice"
            assert session.role is None
            assert session.current_match is None

        _run(body)

    def test_wrong_password_is_rejected_and_session_stays_unauthenticated(self):
        async def body():
            context = build_test_context()
            await context.auth_service.register("alice", "hunter2")
            session = ClientSession("s1", _FakeWebSocket())
            envelope = Envelope(type="login", id="1", data={"username": "alice", "password": "wrong"})

            reply = await commands.handle_login(session, envelope, context)

            assert ErrorCode.INVALID_CREDENTIALS.value in reply
            assert session.user_id is None
            assert session.role is None

        _run(body)
