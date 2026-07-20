import asyncio

from chess_engine.engine.events import PieceCaptured
from chess_engine.model.piece import Color, Piece, PieceType
from chess_engine.model.position import Position

from server.core.bus import Bus
from server.core.clock import FakeClock
from server.game.events import RoomMatchReady, RoomStateTick
from server.game.match import MatchSession, MatchStatus
from server.network.session import ClientSession, Role
from server.tests.support import build_test_repos, wait_until


class _FakeWebSocket:
    async def send(self, _message: str) -> None:
        pass


def _run(body) -> None:
    asyncio.run(body())


def _new_match(bus=None, clock=None, tick_ms=None) -> MatchSession:
    auth_service, matches_repo = build_test_repos()
    kwargs = {"bus": bus or Bus(), "clock": clock or FakeClock(), "auth_service": auth_service, "matches_repo": matches_repo}
    if tick_ms is not None:
        kwargs["tick_ms"] = tick_ms
    return MatchSession(**kwargs)


def _unseated_session(session_id: str = "s1") -> ClientSession:
    return ClientSession(session_id, _FakeWebSocket())


class TestTrySeat:
    def test_first_connection_becomes_white(self):
        async def body():
            match = _new_match()
            try:
                session = _unseated_session("s1")
                assert match.try_seat(session) is True
                assert session.role is Role.WHITE
                assert match.white is session
            finally:
                match._tick_task.cancel()

        _run(body)

    def test_second_connection_becomes_black(self):
        async def body():
            match = _new_match()
            try:
                match.try_seat(_unseated_session("s1"))
                second = _unseated_session("s2")
                assert match.try_seat(second) is True
                assert second.role is Role.BLACK
                assert match.black is second
            finally:
                match._tick_task.cancel()

        _run(body)

    def test_third_connection_is_refused(self):
        async def body():
            match = _new_match()
            try:
                match.try_seat(_unseated_session("s1"))
                match.try_seat(_unseated_session("s2"))
                third = _unseated_session("s3")
                assert match.try_seat(third) is False
                assert third.role is None
            finally:
                match._tick_task.cancel()

        _run(body)

    def test_seating_the_second_player_publishes_match_ready(self):
        async def body():
            bus = Bus()
            received = []

            async def handler(event):
                received.append(event)

            match = _new_match(bus=bus)
            try:
                bus.subscribe(f"room:{match.room_id}", handler)
                match.try_seat(_unseated_session("s1"))
                assert received == []  # not ready with only one seat filled
                match.try_seat(_unseated_session("s2"))
                await wait_until(lambda: any(isinstance(event, RoomMatchReady) for event in received))
                assert any(isinstance(event, RoomMatchReady) for event in received)
            finally:
                match._tick_task.cancel()

        _run(body)


class TestRelease:
    def test_release_frees_the_seat(self):
        async def body():
            match = _new_match()
            try:
                session = _unseated_session("s1")
                match.try_seat(session)
                match.release(session)
                assert match.white is None
            finally:
                match._tick_task.cancel()

        _run(body)

    def test_release_of_an_unseated_session_is_a_noop(self):
        async def body():
            match = _new_match()
            try:
                stranger = ClientSession("stranger", _FakeWebSocket(), Role.WHITE)
                match.release(stranger)
            finally:
                match._tick_task.cancel()

        _run(body)


class TestEnd:
    def test_end_is_idempotent(self):
        async def body():
            match = _new_match()
            match.end(reason="king_captured")
            match.end(reason="king_captured")
            await match.teardown_task
            await match.record_result_task
            assert match.status is MatchStatus.ENDED

        _run(body)

    def test_king_capture_ends_the_match(self):
        async def body():
            match = _new_match()
            match.stack.engine.notify_king_captured()
            await match.teardown_task
            await match.record_result_task
            assert match.status is MatchStatus.ENDED

        _run(body)

    def test_end_tears_down_the_tick_task(self):
        async def body():
            match = _new_match(tick_ms=5)
            match.end(reason="king_captured")
            await match.teardown_task
            await wait_until(lambda: match._tick_task.done())
            assert match._tick_task.done()

        _run(body)


class TestRecordResult:
    async def _seat_authenticated_players(self, match: MatchSession) -> tuple[ClientSession, ClientSession]:
        # Mirrors what auth/commands.py does on a real register/login: set
        # user_id first, then seat — try_seat itself never touches identity.
        white_user = await match.auth_service.register("white_player", "pw")
        black_user = await match.auth_service.register("black_player", "pw")
        white = _unseated_session("s1")
        white.user_id = white_user.id
        match.try_seat(white)
        black = _unseated_session("s2")
        black.user_id = black_user.id
        match.try_seat(black)
        return white, black

    def test_king_capture_records_a_result_and_updates_elo(self):
        async def body():
            match = _new_match()
            try:
                white, black = await self._seat_authenticated_players(match)
                match._winner_color = None
                # Simulate white's king being captured by black.
                match.stack.engine.events.publish(
                    PieceCaptured(piece=Piece(PieceType.KING, Color.WHITE), captured_by=Color.BLACK),
                )
                match.stack.engine.notify_king_captured()
                await match.record_result_task

                white_user = await match.auth_service.users_repo.get_by_id(white.user_id)
                black_user = await match.auth_service.users_repo.get_by_id(black.user_id)
                assert white_user.elo < 1200
                assert black_user.elo > 1200
            finally:
                match._tick_task.cancel()

        _run(body)

    def test_result_is_skipped_when_a_player_never_authenticated(self):
        async def body():
            match = _new_match()
            try:
                match.try_seat(_unseated_session("s1"))  # no user_id set
                match.try_seat(_unseated_session("s2"))
                match.stack.engine.notify_king_captured()
                await match.record_result_task
                # Nothing to assert on the DB beyond "this didn't raise" —
                # _record_result must no-op, not crash, for a guest match.
                assert match.status is MatchStatus.ENDED
            finally:
                match._tick_task.cancel()

        _run(body)

    def test_result_is_skipped_when_a_player_has_disconnected(self):
        async def body():
            match = _new_match()
            try:
                white, black = await self._seat_authenticated_players(match)
                match.release(white)
                match.stack.engine.notify_king_captured()
                await match.record_result_task
                black_user = await match.auth_service.users_repo.get_by_id(black.user_id)
                assert black_user.elo == 1200  # untouched: recording was skipped
            finally:
                match._tick_task.cancel()

        _run(body)


class TestTickLoop:
    def test_tick_advances_engine_time_and_publishes_state(self):
        async def body():
            bus = Bus()
            received = []

            async def handler(event):
                received.append(event)

            match = _new_match(bus=bus, tick_ms=5)
            bus.subscribe(f"room:{match.room_id}", handler)
            await wait_until(lambda: len(received) > 0)
            match.end(reason="test cleanup")
            await match.teardown_task
            assert len(received) > 0

        _run(body)

    def test_tick_carries_active_motions_and_cooldowns(self):
        async def body():
            bus = Bus()
            received = []

            async def handler(event):
                received.append(event)

            match = _new_match(bus=bus, tick_ms=5)
            bus.subscribe(f"room:{match.room_id}", handler)
            match.stack.engine.request_move(Position(6, 4), Position(5, 4))
            await wait_until(
                lambda: any(
                    isinstance(e, RoomStateTick) and e.active_motions for e in received
                ),
            )
            match.end(reason="test cleanup")
            await match.teardown_task

            ticks = [e for e in received if isinstance(e, RoomStateTick)]
            assert ticks
            assert any(tick.active_motions for tick in ticks)

        _run(body)
