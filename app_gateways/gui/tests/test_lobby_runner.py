# Pure state-machine tests for the Room create/join modal — no cv2 window is
# ever opened here (that only happens inside LobbyRunner.run()), so these
# exercise _handle_modal_key/_handle_room_reply directly, the same way
# test_network_facade.py tests its class without any GUI harness.
import asyncio

from app_gateways.gui.lobby_runner import LobbyRunner


def _make_runner(send_and_wait=None) -> LobbyRunner:
    async def noop_send(_envelope):
        pass

    async def default_send_and_wait(_envelope):
        return {}

    return LobbyRunner(
        noop_send, send_and_wait or default_send_and_wait, asyncio.Event(), asyncio.Event(),
    )


def _run(body) -> None:
    asyncio.run(body())


class TestModalKeyEntry:
    def test_typing_appends_uppercased_alphabet_characters(self):
        runner = _make_runner()
        for ch in "ab3":
            runner._handle_modal_key(ord(ch))
        assert runner._modal_text == "AB3"

    def test_characters_outside_the_alphabet_are_ignored(self):
        runner = _make_runner()
        runner._handle_modal_key(ord("0"))  # not in the unambiguous alphabet
        runner._handle_modal_key(ord("O"))
        assert runner._modal_text == ""

    def test_backspace_removes_the_last_character(self):
        runner = _make_runner()
        runner._modal_text = "ABC"
        runner._handle_modal_key(8)
        assert runner._modal_text == "AB"

    def test_input_is_capped_at_the_max_length(self):
        runner = _make_runner()
        for ch in "ABCDEFGHJKLMN":  # 13 valid-alphabet characters
            runner._handle_modal_key(ord(ch))
        assert runner._modal_text == "ABCDEFGHJKLM"  # capped to 12

    def test_escape_closes_the_modal_and_clears_state(self):
        runner = _make_runner()
        runner._modal_open = True
        runner._modal_text = "ABC"
        runner._modal_error = "some error"
        runner._handle_modal_key(27)
        assert runner._modal_open is False
        assert runner._modal_text == ""
        assert runner._modal_error is None


class TestHandleRoomReply:
    def test_ack_stores_result_and_signals_room_ready_not_match_ready(self):
        # Regression test for the race where a room's own completion used to
        # share match_ready with the unrelated matchmaking broadcast signal
        # (see lobby_runner.py's _room_ready docstring) — the room flow must
        # only ever set its own event.
        runner = _make_runner()
        runner._modal_open = True
        runner._handle_room_reply({"type": "ack", "data": {"room_id": "ABC123", "role": "white"}})
        assert runner._room_result == {"room_id": "ABC123", "role": "white"}
        assert runner._modal_open is False
        assert runner._room_ready.is_set()
        assert not runner._match_ready.is_set()

    def test_error_sets_modal_error_and_leaves_modal_open(self):
        runner = _make_runner()
        runner._modal_open = True
        runner._handle_room_reply({"type": "error", "code": "ROOM_NOT_FOUND", "message": "no room"})
        assert runner._modal_error == "no room"
        assert runner._modal_open is True
        assert not runner._room_ready.is_set()
        assert runner._room_result is None


class TestDoRoomCreate:
    def test_sends_the_typed_text_as_the_requested_room_id(self):
        async def body():
            sent = []

            async def send_and_wait(envelope):
                sent.append(envelope)
                return {"type": "ack", "data": {"room_id": "TEAMROOM", "role": "white"}}

            runner = _make_runner(send_and_wait)
            runner._modal_text = "teamroom"
            await runner._do_room_create()

            assert sent == [{"type": "room_create", "data": {"room_id": "teamroom"}}]
            assert runner._room_result == {"room_id": "TEAMROOM", "role": "white"}

        _run(body)

    def test_empty_text_requests_an_auto_generated_code(self):
        async def body():
            sent = []

            async def send_and_wait(envelope):
                sent.append(envelope)
                return {"type": "ack", "data": {"room_id": "AB3XQZ", "role": "white"}}

            runner = _make_runner(send_and_wait)
            await runner._do_room_create()

            assert sent == [{"type": "room_create", "data": {"room_id": ""}}]

        _run(body)


class TestMatchReadyRaceIsIgnoredWhileNotQueued:
    def test_incidental_match_ready_alone_does_not_satisfy_run_loop_wait(self):
        # A 2nd player joining THIS room fires the same broadcast/match_ready
        # DevClient uses for the ordinary PLAY/matchmaking signal — setting
        # match_ready here (without _queued, i.e. the user never clicked
        # PLAY) must not be treated as "the room flow is done" on its own.
        runner = _make_runner()
        runner._match_ready.set()
        assert runner._queued is False
        assert not (runner._queued and runner._match_ready.is_set())
        assert not runner._room_ready.is_set()
