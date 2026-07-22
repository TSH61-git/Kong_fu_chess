import asyncio

from server.core.bus import Bus
from server.core.clock import FakeClock
from server.game.events import RoomStateTick
from server.game.match import MatchSession
from server.network.session import ClientSession, Role
from server.tests.support import build_test_repos, wait_until


class _FakeWebSocket:
    async def send(self, _message: str) -> None:
        pass


def _run(body) -> None:
    asyncio.run(body())


def _new_match(bus=None, room_id=None) -> MatchSession:
    auth_service, matches_repo = build_test_repos()
    return MatchSession(
        bus=bus or Bus(), clock=FakeClock(), auth_service=auth_service,
        matches_repo=matches_repo, room_id=room_id,
    )


def _unseated_session(session_id: str = "s1") -> ClientSession:
    return ClientSession(session_id, _FakeWebSocket())


class TestCustomRoomId:
    def test_injected_room_id_is_used_verbatim(self):
        async def body():
            match = _new_match(room_id="ABC123")
            try:
                assert match.room_id == "ABC123"
            finally:
                match._tick_task.cancel()

        _run(body)

    def test_omitted_room_id_falls_back_to_a_uuid(self):
        async def body():
            match = _new_match()
            try:
                assert len(match.room_id) == 36  # uuid4's canonical string length
            finally:
                match._tick_task.cancel()

        _run(body)


class TestPauseForOpponent:
    def test_freezes_the_match(self):
        async def body():
            match = _new_match()
            try:
                match.pause_for_opponent()
                assert match.is_frozen is True
            finally:
                match._tick_task.cancel()

        _run(body)

    def test_immediately_publishes_a_frozen_state_tick(self):
        # Regression: _run_tick_loop skips publishing entirely while frozen,
        # so without an explicit publish here a solo creator would never
        # receive any state_tick at all (let alone one saying frozen=True)
        # until a second player eventually joins.
        async def body():
            bus = Bus()
            received = []

            async def handler(event):
                received.append(event)

            match = _new_match(bus=bus)
            try:
                bus.subscribe(f"room:{match.room_id}", handler)
                match.pause_for_opponent()
                await wait_until(lambda: any(isinstance(e, RoomStateTick) for e in received))
                ticks = [e for e in received if isinstance(e, RoomStateTick)]
                assert any(tick.frozen for tick in ticks)
            finally:
                match._tick_task.cancel()

        _run(body)


class TestAddViewer:
    def test_add_viewer_sets_role_and_current_match(self):
        async def body():
            match = _new_match()
            try:
                viewer = _unseated_session("v1")
                match.add_viewer(viewer)
                assert viewer.role is Role.VIEWER
                assert viewer.current_match is match
                assert viewer in match.viewers
            finally:
                match._tick_task.cancel()

        _run(body)

    def test_viewers_are_included_in_broadcast_fanout(self):
        async def body():
            match = _new_match()
            try:
                viewer = _unseated_session("v1")
                match.add_viewer(viewer)
                assert viewer in match._sessions()
            finally:
                match._tick_task.cancel()

        _run(body)

    def test_add_viewer_immediately_backfills_state(self):
        async def body():
            bus = Bus()
            received = []

            async def handler(event):
                received.append(event)

            match = _new_match(bus=bus)
            try:
                bus.subscribe(f"room:{match.room_id}", handler)
                match.add_viewer(_unseated_session("v1"))
                await wait_until(lambda: len(received) > 0)
                assert len(received) > 0
            finally:
                match._tick_task.cancel()

        _run(body)


class TestReleaseViewer:
    def test_release_removes_a_viewer_and_clears_role(self):
        async def body():
            match = _new_match()
            try:
                viewer = _unseated_session("v1")
                match.add_viewer(viewer)
                match.release(viewer)
                assert viewer not in match.viewers
                assert viewer.role is None
                assert viewer.current_match is None
            finally:
                match._tick_task.cancel()

        _run(body)


class TestViewerDisconnect:
    def test_viewer_disconnect_does_not_trigger_forfeit_logic(self):
        async def body():
            match = _new_match()
            try:
                white = _unseated_session("s1")
                black = _unseated_session("s2")
                match.try_seat(white)
                match.try_seat(black)
                viewer = _unseated_session("v1")
                match.add_viewer(viewer)

                match.handle_disconnect(viewer)

                assert viewer not in match.viewers
                assert not match.is_frozen  # white/black seats untouched
                assert match.white is white
                assert match.black is black
            finally:
                match._tick_task.cancel()

        _run(body)

    def test_viewer_is_excluded_from_reconnect_bookkeeping(self):
        async def body():
            match = _new_match()
            try:
                viewer = _unseated_session("v1")
                viewer.user_id = 99
                match.add_viewer(viewer)
                match.handle_disconnect(viewer)
                assert match.is_awaiting_reconnect(99) is False
            finally:
                match._tick_task.cancel()

        _run(body)
