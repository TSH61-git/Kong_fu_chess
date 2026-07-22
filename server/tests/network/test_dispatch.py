import asyncio

from server.core.bus import Bus
from server.core.protocol import ErrorCode, Envelope
from server.game.match import MatchSession
from server.network.dispatch import dispatch
from server.network.session import ClientSession, Role
from server.tests.support import build_test_context, build_test_repos


class _FakeWebSocket:
    async def send(self, _message: str) -> None:
        pass


def _run(body) -> None:
    asyncio.run(body())


def test_dispatch_routes_move_to_handle_move():
    async def body():
        context = build_test_context()
        auth_service, matches_repo = build_test_repos()
        match = MatchSession(bus=Bus(), clock=context.clock, auth_service=auth_service, matches_repo=matches_repo)
        try:
            session = ClientSession("s1", _FakeWebSocket())
            session.user_id = 1
            session.role = Role.WHITE
            session.current_match = match
            match.white = session
            envelope = Envelope(type="move", id="1", data={"cmd": "WPe2e3"})
            assert '"ok": true' in await dispatch(session, envelope, context)
        finally:
            match._tick_task.cancel()

    _run(body)


def test_dispatch_routes_ping_to_handle_ping():
    async def body():
        context = build_test_context()
        session = ClientSession("s1", _FakeWebSocket())
        envelope = Envelope(type="ping", id="1", data={})
        assert '"ok": true' in await dispatch(session, envelope, context)

    _run(body)


def test_dispatch_routes_register_to_handle_register():
    async def body():
        context = build_test_context()
        session = ClientSession("s1", _FakeWebSocket())
        envelope = Envelope(type="register", id="1", data={"username": "alice", "password": "hunter2"})
        assert '"ok": true' in await dispatch(session, envelope, context)
        assert session.username == "alice"
        assert session.role is None  # register no longer seats — that's the matchmaker's job now

    _run(body)


def test_dispatch_routes_login_to_handle_login():
    async def body():
        context = build_test_context()
        await context.auth_service.register("alice", "hunter2")
        session = ClientSession("s1", _FakeWebSocket())
        envelope = Envelope(type="login", id="1", data={"username": "alice", "password": "hunter2"})
        assert '"ok": true' in await dispatch(session, envelope, context)
        assert session.username == "alice"
        assert session.role is None

    _run(body)


def test_dispatch_routes_queue_join_to_handle_queue_join():
    async def body():
        context = build_test_context()
        user = await context.auth_service.register("alice", "hunter2")
        session = ClientSession("s1", _FakeWebSocket())
        session.user_id = user.id
        envelope = Envelope(type="queue_join", id="1", data={})
        assert '"ok": true' in await dispatch(session, envelope, context)
        assert context.queue.contains(session)

    _run(body)


def test_dispatch_routes_queue_cancel_to_handle_queue_cancel():
    async def body():
        context = build_test_context()
        user = await context.auth_service.register("alice", "hunter2")
        session = ClientSession("s1", _FakeWebSocket())
        session.user_id = user.id
        context.queue.enqueue(session, user.elo, context.clock.now())
        envelope = Envelope(type="queue_cancel", id="1", data={})
        assert '"ok": true' in await dispatch(session, envelope, context)
        assert not context.queue.contains(session)

    _run(body)


def test_dispatch_routes_room_create_to_handle_room_create():
    async def body():
        context = build_test_context()
        user = await context.auth_service.register("alice", "hunter2")
        session = ClientSession("s1", _FakeWebSocket())
        session.user_id = user.id
        envelope = Envelope(type="room_create", id="1", data={})
        reply = await dispatch(session, envelope, context)
        assert '"ok": true' in reply
        assert '"role": "white"' in reply
        session.current_match._tick_task.cancel()

    _run(body)


def test_dispatch_routes_room_join_to_handle_room_join():
    async def body():
        context = build_test_context()
        creator_user = await context.auth_service.register("alice", "hunter2")
        creator = ClientSession("s1", _FakeWebSocket())
        creator.user_id = creator_user.id
        await dispatch(creator, Envelope(type="room_create", id="1", data={}), context)
        room_id = creator.current_match.room_id

        joiner_user = await context.auth_service.register("bob", "hunter2")
        joiner = ClientSession("s2", _FakeWebSocket())
        joiner.user_id = joiner_user.id
        reply = await dispatch(joiner, Envelope(type="room_join", id="2", data={"room_id": room_id}), context)

        assert '"ok": true' in reply
        assert '"role": "black"' in reply
        creator.current_match._tick_task.cancel()

    _run(body)


def test_dispatch_rejects_unknown_command_type():
    async def body():
        context = build_test_context()
        session = ClientSession("s1", _FakeWebSocket())
        envelope = Envelope(type="teleport", id="1", data={})
        assert ErrorCode.UNKNOWN_COMMAND_TYPE.value in await dispatch(session, envelope, context)

    _run(body)
