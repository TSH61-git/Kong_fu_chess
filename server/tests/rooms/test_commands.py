import asyncio

from chess_engine.engine.events import PieceCaptured
from chess_engine.model.piece import Color, Piece, PieceType

from server.core.protocol import ErrorCode, Envelope
from server.network.session import ClientSession, Role
from server.rooms import commands
from server.tests.support import build_test_context


class _FakeWebSocket:
    async def send(self, _message: str) -> None:
        pass


def _run(body) -> None:
    asyncio.run(body())


async def _authenticated_session(context, session_id: str, username: str) -> ClientSession:
    user = await context.auth_service.register(username, "pw")
    session = ClientSession(session_id, _FakeWebSocket())
    session.user_id = user.id
    session.username = user.username
    return session


class TestHandleRoomCreate:
    def test_creates_a_room_and_seats_the_creator_as_white(self):
        async def body():
            context = build_test_context()
            session = await _authenticated_session(context, "s1", "alice")
            envelope = Envelope(type="room_create", id="1", data={})

            reply = await commands.handle_room_create(session, envelope, context)

            assert '"ok": true' in reply
            assert '"role": "white"' in reply
            assert session.role is Role.WHITE
            match = context.registry.get(session.current_match.room_id)
            assert match is session.current_match
            assert len(match.room_id) == 6
            match._tick_task.cancel()

        _run(body)

    def test_rejects_unauthenticated_session(self):
        async def body():
            context = build_test_context()
            session = ClientSession("s1", _FakeWebSocket())
            envelope = Envelope(type="room_create", id="1", data={})
            reply = await commands.handle_room_create(session, envelope, context)
            assert ErrorCode.NOT_AUTHENTICATED.value in reply

        _run(body)

    def test_rejects_a_session_already_in_a_match(self):
        async def body():
            context = build_test_context()
            session = await _authenticated_session(context, "s1", "alice")
            await commands.handle_room_create(session, Envelope(type="room_create", id="1", data={}), context)
            reply = await commands.handle_room_create(session, Envelope(type="room_create", id="2", data={}), context)
            assert ErrorCode.ALREADY_IN_MATCH.value in reply
            session.current_match._tick_task.cancel()

        _run(body)

    def test_solo_room_is_frozen_until_black_joins(self):
        async def body():
            context = build_test_context()
            session = await _authenticated_session(context, "s1", "alice")
            await commands.handle_room_create(session, Envelope(type="room_create", id="1", data={}), context)
            match = session.current_match
            assert match.is_frozen is True

            second = await _authenticated_session(context, "s2", "bob")
            await commands.handle_room_join(
                second, Envelope(type="room_join", id="2", data={"room_id": match.room_id}), context,
            )
            assert match.is_frozen is False
            match._tick_task.cancel()

        _run(body)

    def test_custom_alias_is_used_verbatim_when_free(self):
        async def body():
            context = build_test_context()
            session = await _authenticated_session(context, "s1", "alice")
            envelope = Envelope(type="room_create", id="1", data={"room_id": "teamroom"})

            reply = await commands.handle_room_create(session, envelope, context)

            assert '"ok": true' in reply
            assert '"room_id": "TEAMROOM"' in reply
            assert session.current_match.room_id == "TEAMROOM"
            session.current_match._tick_task.cancel()

        _run(body)

    def test_custom_alias_rejects_bad_length(self):
        async def body():
            context = build_test_context()
            session = await _authenticated_session(context, "s1", "alice")
            envelope = Envelope(type="room_create", id="1", data={"room_id": "AB"})
            reply = await commands.handle_room_create(session, envelope, context)
            assert ErrorCode.MALFORMED_COMMAND.value in reply
            assert session.current_match is None

        _run(body)

    def test_custom_alias_rejects_non_alphanumeric(self):
        async def body():
            context = build_test_context()
            session = await _authenticated_session(context, "s1", "alice")
            envelope = Envelope(type="room_create", id="1", data={"room_id": "AB!DEF"})
            reply = await commands.handle_room_create(session, envelope, context)
            assert ErrorCode.MALFORMED_COMMAND.value in reply

        _run(body)

    def test_custom_alias_rejects_when_already_taken(self):
        async def body():
            context = build_test_context()
            first = await _authenticated_session(context, "s1", "alice")
            await commands.handle_room_create(
                first, Envelope(type="room_create", id="1", data={"room_id": "TAKEN01"}), context,
            )

            second = await _authenticated_session(context, "s2", "bob")
            reply = await commands.handle_room_create(
                second, Envelope(type="room_create", id="2", data={"room_id": "taken01"}), context,
            )

            assert ErrorCode.ROOM_ALREADY_EXISTS.value in reply
            assert second.current_match is None
            first.current_match._tick_task.cancel()

        _run(body)


class TestHandleRoomJoin:
    async def _create_room(self, context, username: str) -> tuple[ClientSession, str]:
        creator = await _authenticated_session(context, "creator", username)
        reply = await commands.handle_room_create(creator, Envelope(type="room_create", id="1", data={}), context)
        room_id = creator.current_match.room_id
        return creator, room_id

    def test_second_joiner_is_seated_black(self):
        async def body():
            context = build_test_context()
            creator, room_id = await self._create_room(context, "alice")
            joiner = await _authenticated_session(context, "s2", "bob")

            reply = await commands.handle_room_join(
                joiner, Envelope(type="room_join", id="2", data={"room_id": room_id}), context,
            )

            assert '"ok": true' in reply
            assert '"role": "black"' in reply
            assert joiner.role is Role.BLACK
            creator.current_match._tick_task.cancel()

        _run(body)

    def test_third_plus_joiners_become_viewers(self):
        async def body():
            context = build_test_context()
            creator, room_id = await self._create_room(context, "alice")
            second = await _authenticated_session(context, "s2", "bob")
            await commands.handle_room_join(
                second, Envelope(type="room_join", id="2", data={"room_id": room_id}), context,
            )
            third = await _authenticated_session(context, "s3", "carol")

            reply = await commands.handle_room_join(
                third, Envelope(type="room_join", id="3", data={"room_id": room_id}), context,
            )

            assert '"ok": true' in reply
            assert '"role": "viewer"' in reply
            assert third.role is Role.VIEWER
            assert third in creator.current_match.viewers
            creator.current_match._tick_task.cancel()

        _run(body)

    def test_join_is_case_and_whitespace_insensitive(self):
        async def body():
            context = build_test_context()
            creator, room_id = await self._create_room(context, "alice")
            joiner = await _authenticated_session(context, "s2", "bob")

            reply = await commands.handle_room_join(
                joiner, Envelope(type="room_join", id="2", data={"room_id": f"  {room_id.lower()}  "}), context,
            )

            assert '"ok": true' in reply
            creator.current_match._tick_task.cancel()

        _run(body)

    def test_unknown_code_is_rejected(self):
        async def body():
            context = build_test_context()
            session = await _authenticated_session(context, "s1", "alice")
            reply = await commands.handle_room_join(
                session, Envelope(type="room_join", id="1", data={"room_id": "ZZZZZZ"}), context,
            )
            assert ErrorCode.ROOM_NOT_FOUND.value in reply

        _run(body)

    def test_rejects_unauthenticated_session(self):
        async def body():
            context = build_test_context()
            session = ClientSession("s1", _FakeWebSocket())
            reply = await commands.handle_room_join(
                session, Envelope(type="room_join", id="1", data={"room_id": "ABCDEF"}), context,
            )
            assert ErrorCode.NOT_AUTHENTICATED.value in reply

        _run(body)

    def test_rejects_a_session_already_in_a_match(self):
        async def body():
            context = build_test_context()
            creator, room_id = await self._create_room(context, "alice")
            reply = await commands.handle_room_join(
                creator, Envelope(type="room_join", id="2", data={"room_id": room_id}), context,
            )
            assert ErrorCode.ALREADY_IN_MATCH.value in reply
            creator.current_match._tick_task.cancel()

        _run(body)


class TestMatchStatePayload:
    def test_create_ack_includes_white_username_and_zero_scores(self):
        async def body():
            context = build_test_context()
            session = await _authenticated_session(context, "s1", "alice")
            reply = await commands.handle_room_create(session, Envelope(type="room_create", id="1", data={}), context)
            assert '"white_username": "alice"' in reply
            assert '"black_username": null' in reply
            assert '"white_score": 0' in reply
            assert '"black_score": 0' in reply
            session.current_match._tick_task.cancel()

        _run(body)

    def test_second_joiner_ack_includes_both_usernames(self):
        async def body():
            context = build_test_context()
            creator = await _authenticated_session(context, "s1", "alice")
            await commands.handle_room_create(creator, Envelope(type="room_create", id="1", data={}), context)
            room_id = creator.current_match.room_id

            joiner = await _authenticated_session(context, "s2", "bob")
            reply = await commands.handle_room_join(
                joiner, Envelope(type="room_join", id="2", data={"room_id": room_id}), context,
            )

            assert '"white_username": "alice"' in reply
            assert '"black_username": "bob"' in reply
            creator.current_match._tick_task.cancel()

        _run(body)

    def test_viewer_joining_mid_game_gets_current_names_and_scores(self):
        # Regression: a spectator joining after play has started must see
        # the real player names/score in its own ack, since it never
        # receives the original match_ready broadcast.
        async def body():
            context = build_test_context()
            creator = await _authenticated_session(context, "s1", "alice")
            await commands.handle_room_create(creator, Envelope(type="room_create", id="1", data={}), context)
            match = creator.current_match
            room_id = match.room_id

            second = await _authenticated_session(context, "s2", "bob")
            await commands.handle_room_join(
                second, Envelope(type="room_join", id="2", data={"room_id": room_id}), context,
            )

            # Simulate White capturing Black's queen mid-game.
            match.stack.engine.events.publish(
                PieceCaptured(piece=Piece(PieceType.QUEEN, Color.BLACK), captured_by=Color.WHITE),
            )

            viewer = await _authenticated_session(context, "s3", "carol")
            reply = await commands.handle_room_join(
                viewer, Envelope(type="room_join", id="3", data={"room_id": room_id}), context,
            )

            assert '"role": "viewer"' in reply
            assert '"white_username": "alice"' in reply
            assert '"black_username": "bob"' in reply
            assert '"white_score": 9' in reply
            assert '"black_score": 0' in reply
            match._tick_task.cancel()

        _run(body)
