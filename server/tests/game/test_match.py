import asyncio

from chess_engine.model.position import Position

from server.core.bus import Bus
from server.core.clock import FakeClock
from server.game.events import RoomMatchReady, RoomStateTick
from server.game.match import MatchSession, MatchStatus
from server.network.session import ClientSession, Role


class _FakeWebSocket:
    async def send(self, _message: str) -> None:
        pass


def _run(body) -> None:
    asyncio.run(body())


class TestTrySeat:
    def test_first_connection_becomes_white(self):
        async def body():
            match = MatchSession(bus=Bus(), clock=FakeClock())
            try:
                session = match.try_seat("s1", _FakeWebSocket())
                assert session.role is Role.WHITE
                assert match.white is session
            finally:
                match._tick_task.cancel()

        _run(body)

    def test_second_connection_becomes_black(self):
        async def body():
            match = MatchSession(bus=Bus(), clock=FakeClock())
            try:
                match.try_seat("s1", _FakeWebSocket())
                second = match.try_seat("s2", _FakeWebSocket())
                assert second.role is Role.BLACK
                assert match.black is second
            finally:
                match._tick_task.cancel()

        _run(body)

    def test_third_connection_is_refused(self):
        async def body():
            match = MatchSession(bus=Bus(), clock=FakeClock())
            try:
                match.try_seat("s1", _FakeWebSocket())
                match.try_seat("s2", _FakeWebSocket())
                assert match.try_seat("s3", _FakeWebSocket()) is None
            finally:
                match._tick_task.cancel()

        _run(body)

    def test_seating_the_second_player_publishes_match_ready(self):
        async def body():
            bus = Bus()
            received = []

            async def handler(event):
                received.append(event)

            match = MatchSession(bus=bus, clock=FakeClock())
            try:
                bus.subscribe(f"room:{match.room_id}", handler)
                match.try_seat("s1", _FakeWebSocket())
                assert received == []  # not ready with only one seat filled
                match.try_seat("s2", _FakeWebSocket())
                await asyncio.sleep(0.01)
                assert any(isinstance(event, RoomMatchReady) for event in received)
            finally:
                match._tick_task.cancel()

        _run(body)


class TestRelease:
    def test_release_frees_the_seat(self):
        async def body():
            match = MatchSession(bus=Bus(), clock=FakeClock())
            try:
                session = match.try_seat("s1", _FakeWebSocket())
                match.release(session)
                assert match.white is None
            finally:
                match._tick_task.cancel()

        _run(body)

    def test_release_of_an_unseated_session_is_a_noop(self):
        async def body():
            match = MatchSession(bus=Bus(), clock=FakeClock())
            try:
                stranger = ClientSession("stranger", _FakeWebSocket(), Role.WHITE)
                match.release(stranger)
            finally:
                match._tick_task.cancel()

        _run(body)


class TestEnd:
    def test_end_is_idempotent(self):
        async def body():
            match = MatchSession(bus=Bus(), clock=FakeClock())
            match.end(reason="king_captured")
            match.end(reason="king_captured")
            await asyncio.sleep(0.01)
            assert match.status is MatchStatus.ENDED

        _run(body)

    def test_king_capture_ends_the_match(self):
        async def body():
            match = MatchSession(bus=Bus(), clock=FakeClock())
            match.stack.engine.notify_king_captured()
            await asyncio.sleep(0.01)
            assert match.status is MatchStatus.ENDED

        _run(body)

    def test_end_tears_down_the_tick_task(self):
        async def body():
            match = MatchSession(bus=Bus(), clock=FakeClock(), tick_ms=5)
            match.end(reason="king_captured")
            await asyncio.sleep(0.05)
            assert match._tick_task.done()

        _run(body)


class TestTickLoop:
    def test_tick_advances_engine_time_and_publishes_state(self):
        async def body():
            bus = Bus()
            received = []

            async def handler(event):
                received.append(event)

            match = MatchSession(bus=bus, clock=FakeClock(), tick_ms=5)
            bus.subscribe(f"room:{match.room_id}", handler)
            await asyncio.sleep(0.05)
            match.end(reason="test cleanup")
            await asyncio.sleep(0.01)
            assert len(received) > 0

        _run(body)

    def test_tick_carries_active_motions_and_cooldowns(self):
        async def body():
            bus = Bus()
            received = []

            async def handler(event):
                received.append(event)

            match = MatchSession(bus=bus, clock=FakeClock(), tick_ms=5)
            bus.subscribe(f"room:{match.room_id}", handler)
            match.stack.engine.request_move(Position(6, 4), Position(5, 4))
            await asyncio.sleep(0.05)
            match.end(reason="test cleanup")
            await asyncio.sleep(0.01)

            ticks = [e for e in received if isinstance(e, RoomStateTick)]
            assert ticks
            assert any(tick.active_motions for tick in ticks)

        _run(body)
