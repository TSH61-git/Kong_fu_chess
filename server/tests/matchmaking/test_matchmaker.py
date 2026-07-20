import asyncio

from server.core.bus import Bus
from server.core.clock import FakeClock
from server.game.registry import MatchRegistry
from server.matchmaking.matchmaker import Matchmaker
from server.matchmaking.queue import MatchmakingQueue
from server.network.session import ClientSession, Role
from server.tests.support import build_test_repos, wait_until


class _FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, message: str) -> None:
        self.sent.append(message)


def _run(body) -> None:
    asyncio.run(body())


async def _authenticated_session(auth_service, session_id: str, username: str) -> ClientSession:
    user = await auth_service.register(username, "pw")
    session = ClientSession(session_id, _FakeWebSocket())
    session.user_id = user.id
    session.username = user.username
    return session


def _build():
    auth_service, matches_repo = build_test_repos()
    queue = MatchmakingQueue()
    registry = MatchRegistry()
    clock = FakeClock()
    matchmaker = Matchmaker(
        queue=queue, registry=registry, bus=Bus(), clock=clock,
        auth_service=auth_service, matches_repo=matches_repo, tick_ms=60_000,
    )
    return matchmaker, queue, registry, clock, auth_service


class TestPollOnce:
    def test_pairs_and_seats_two_same_elo_sessions(self):
        async def body():
            matchmaker, queue, registry, clock, auth_service = _build()
            white = await _authenticated_session(auth_service, "s1", "white_player")
            black = await _authenticated_session(auth_service, "s2", "black_player")
            queue.enqueue(white, elo=1200, now=clock.now())
            queue.enqueue(black, elo=1200, now=clock.now())

            await matchmaker.poll_once()

            assert white.current_match is not None
            assert white.current_match is black.current_match
            assert white.role is Role.WHITE
            assert black.role is Role.BLACK
            assert len(registry) == 1
            assert any('"event": "seated"' in msg for msg in white.websocket.sent)
            assert any('"event": "seated"' in msg for msg in black.websocket.sent)

            white.current_match._tick_task.cancel()

        _run(body)

    def test_leaves_out_of_range_pair_queued(self):
        async def body():
            matchmaker, queue, registry, clock, auth_service = _build()
            low = await _authenticated_session(auth_service, "s1", "low_elo")
            high = await _authenticated_session(auth_service, "s2", "high_elo")
            queue.enqueue(low, elo=1000, now=clock.now())
            queue.enqueue(high, elo=1400, now=clock.now())

            await matchmaker.poll_once()

            assert low.current_match is None
            assert high.current_match is None
            assert queue.contains(low)
            assert queue.contains(high)
            assert len(registry) == 0

        _run(body)

    def test_expires_a_lone_queued_session_and_notifies_it(self):
        async def body():
            matchmaker, queue, registry, clock, auth_service = _build()
            lone = await _authenticated_session(auth_service, "s1", "lone_player")
            queue.enqueue(lone, elo=1200, now=clock.now())

            clock.advance(61)
            await matchmaker.poll_once()

            assert not queue.contains(lone)
            assert lone.current_match is None
            assert any('"event": "queue_timeout"' in msg for msg in lone.websocket.sent)

        _run(body)

    def test_ended_match_is_removed_from_the_registry(self):
        async def body():
            matchmaker, queue, registry, clock, auth_service = _build()
            white = await _authenticated_session(auth_service, "s1", "white_player")
            black = await _authenticated_session(auth_service, "s2", "black_player")
            queue.enqueue(white, elo=1200, now=clock.now())
            queue.enqueue(black, elo=1200, now=clock.now())
            await matchmaker.poll_once()

            match = white.current_match
            match.end(reason="test cleanup")
            await wait_until(lambda: len(registry) == 0)

            assert len(registry) == 0
            assert white.current_match is None
            assert white.role is None
            assert black.current_match is None
            assert black.role is None

        _run(body)
