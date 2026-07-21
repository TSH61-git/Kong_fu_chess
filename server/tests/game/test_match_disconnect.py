import asyncio

from server.core.bus import Bus
from server.core.clock import FakeClock
from server.game.events import RoomOpponentDisconnected, RoomOpponentReconnected, RoomStateTick
from server.game.match import MatchSession
from server.network.session import ClientSession, Role
from server.tests.support import build_test_repos, wait_until


class _FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, message: str) -> None:
        self.sent.append(message)


def _run(body) -> None:
    asyncio.run(body())


def _new_match(bus=None, disconnect_grace_seconds: float = 5.0) -> MatchSession:
    auth_service, matches_repo = build_test_repos()
    return MatchSession(
        bus=bus or Bus(), clock=FakeClock(), auth_service=auth_service, matches_repo=matches_repo,
        disconnect_grace_seconds=disconnect_grace_seconds,
    )


async def _seat_authenticated_players(match: MatchSession) -> tuple[ClientSession, ClientSession]:
    white_user = await match.auth_service.register("white_player", "pw")
    black_user = await match.auth_service.register("black_player", "pw")
    white = ClientSession("s1", _FakeWebSocket())
    white.user_id = white_user.id
    white.username = white_user.username
    match.try_seat(white)
    black = ClientSession("s2", _FakeWebSocket())
    black.user_id = black_user.id
    black.username = black_user.username
    match.try_seat(black)
    return white, black


class TestHandleDisconnect:
    def test_single_disconnect_freezes_match_and_notifies(self):
        async def body():
            bus = Bus()
            received = []

            async def handler(event):
                received.append(event)

            match = _new_match(bus=bus)
            try:
                white, black = await _seat_authenticated_players(match)
                bus.subscribe(f"room:{match.room_id}", handler)

                match.handle_disconnect(white)

                assert match.white is None
                assert match.is_frozen is True
                await wait_until(lambda: any(isinstance(e, RoomOpponentDisconnected) for e in received))
                event = next(e for e in received if isinstance(e, RoomOpponentDisconnected))
                assert event.role == "white"
                assert event.countdown_seconds == 5.0
            finally:
                if match._disconnect_task is not None:
                    match._disconnect_task.cancel()
                match._tick_task.cancel()

        _run(body)


class TestReconnect:
    def test_reconnect_within_grace_reseats_and_sends_state_tick(self):
        async def body():
            bus = Bus()
            received = []

            async def handler(event):
                received.append(event)

            match = _new_match(bus=bus)
            try:
                white, black = await _seat_authenticated_players(match)
                bus.subscribe(f"room:{match.room_id}", handler)
                match.handle_disconnect(white)
                await wait_until(lambda: any(isinstance(e, RoomOpponentDisconnected) for e in received))

                new_session = ClientSession("s3", _FakeWebSocket())
                new_session.username = "white_player"
                role = match.reconnect(white.user_id, new_session)

                assert role is Role.WHITE
                assert match.white is new_session
                assert match.is_frozen is False
                assert match._disconnect_task is None
                await wait_until(lambda: any(isinstance(e, RoomOpponentReconnected) for e in received))
                await wait_until(lambda: any(isinstance(e, RoomStateTick) for e in received))
            finally:
                if match._disconnect_task is not None:
                    match._disconnect_task.cancel()
                match._tick_task.cancel()

        _run(body)

    def test_reconnect_with_wrong_user_id_is_refused(self):
        async def body():
            match = _new_match()
            try:
                white, black = await _seat_authenticated_players(match)
                match.handle_disconnect(white)

                stranger = ClientSession("s3", _FakeWebSocket())
                role = match.reconnect(999999, stranger)

                assert role is None
                assert match.white is None
            finally:
                if match._disconnect_task is not None:
                    match._disconnect_task.cancel()
                match._tick_task.cancel()

        _run(body)


class TestDisconnectTimeout:
    def test_timeout_without_reconnect_forfeits_and_updates_elo(self):
        async def body():
            match = _new_match(disconnect_grace_seconds=0.02)
            white, black = await _seat_authenticated_players(match)

            match.handle_disconnect(white)
            await wait_until(lambda: match.record_result_task is not None)
            await match.record_result_task

            white_user = await match.auth_service.users_repo.get_by_id(white.user_id)
            black_user = await match.auth_service.users_repo.get_by_id(black.user_id)
            assert white_user.elo < 1200
            assert black_user.elo > 1200

        _run(body)


class TestBothDisconnected:
    def test_both_disconnecting_ends_match_as_no_contest(self):
        async def body():
            match = _new_match(disconnect_grace_seconds=5.0)
            white, black = await _seat_authenticated_players(match)

            match.handle_disconnect(white)
            first_timer = match._disconnect_task
            assert first_timer is not None

            match.handle_disconnect(black)

            await wait_until(lambda: match.record_result_task is not None)
            await match.record_result_task
            assert first_timer.cancelled()

            white_user = await match.auth_service.users_repo.get_by_id(white.user_id)
            black_user = await match.auth_service.users_repo.get_by_id(black.user_id)
            # Same starting elo + no-contest draw scoring -> no net change.
            assert white_user.elo == 1200
            assert black_user.elo == 1200

        _run(body)
