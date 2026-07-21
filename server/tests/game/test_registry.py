import asyncio

from server.core.bus import Bus
from server.core.clock import FakeClock
from server.game.match import MatchSession
from server.game.registry import MatchRegistry
from server.network.session import ClientSession
from server.tests.support import build_test_repos


class _FakeWebSocket:
    async def send(self, _message: str) -> None:
        pass


def _run(body) -> None:
    asyncio.run(body())


def _new_match() -> MatchSession:
    auth_service, matches_repo = build_test_repos()
    return MatchSession(bus=Bus(), clock=FakeClock(), auth_service=auth_service, matches_repo=matches_repo)


class TestFindAwaitingReconnect:
    def test_finds_the_match_a_disconnected_user_is_awaiting_reconnect_in(self):
        async def body():
            match = _new_match()
            try:
                registry = MatchRegistry()
                registry.add(match)

                white_user = await match.auth_service.register("white_player", "pw")
                white = ClientSession("s1", _FakeWebSocket())
                white.user_id = white_user.id
                match.try_seat(white)
                black_user = await match.auth_service.register("black_player", "pw")
                black = ClientSession("s2", _FakeWebSocket())
                black.user_id = black_user.id
                match.try_seat(black)

                match.handle_disconnect(white)

                assert registry.find_awaiting_reconnect(white.user_id) is match
                assert registry.find_awaiting_reconnect(black.user_id) is None
                assert registry.find_awaiting_reconnect(999999) is None
            finally:
                if match._disconnect_task is not None:
                    match._disconnect_task.cancel()
                match._tick_task.cancel()

        _run(body)

    def test_returns_none_once_the_match_has_ended(self):
        async def body():
            match = _new_match()
            registry = MatchRegistry()
            registry.add(match)

            white_user = await match.auth_service.register("white_player", "pw")
            white = ClientSession("s1", _FakeWebSocket())
            white.user_id = white_user.id
            match.try_seat(white)

            match.end(reason="test cleanup")
            await match.teardown_task

            assert registry.find_awaiting_reconnect(white.user_id) is None

        _run(body)
