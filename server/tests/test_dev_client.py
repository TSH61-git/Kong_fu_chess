import asyncio
import sys
import time

from chess_engine.model.piece import Color, PieceType
from chess_engine.model.position import Position

from server.dev_client import DevClient, _line_to_envelope


class _FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, message: str) -> None:
        self.sent.append(message)


class _ScriptedStdin:
    # Feeds queued lines one readline() call at a time; raises if the script
    # runs dry, so a test can't silently hang on a real blocking read.
    def __init__(self, lines: list[str]) -> None:
        self._lines = list(lines)

    def readline(self) -> str:
        if not self._lines:
            raise AssertionError("stdin script ran out of lines")
        return self._lines.pop(0)


class _NeverRespondingStdin:
    # Simulates a user who never types anything — readline() blocks far
    # longer than any test timeout, so the only way run_shell_phase() can
    # return is via the match_ready path, exactly like a fast opponent
    # connecting before this player types a command.
    def readline(self) -> str:
        time.sleep(10)
        return ""


class _FakeFacade:
    def __init__(self) -> None:
        self.state_ticks: list[tuple] = []
        self.moves_accepted: list[tuple] = []
        self.pieces_captured: list[tuple] = []
        self.game_over_calls = 0
        self.winner_names: list = []

    def apply_state_tick(self, board_grid, active_motions, cooldowns, game_over) -> None:
        self.state_ticks.append((board_grid, active_motions, cooldowns, game_over))

    def apply_move_accepted(self, color, piece_type, source, destination, is_capture) -> None:
        self.moves_accepted.append((color, piece_type, source, destination, is_capture))

    def apply_piece_captured(self, piece_type, piece_color, captured_by) -> None:
        self.pieces_captured.append((piece_type, piece_color, captured_by))

    def apply_game_over(self, winner_username=None) -> None:
        self.game_over_calls += 1
        self.winner_names.append(winner_username)


class TestLineToEnvelope:
    def test_ping(self):
        assert _line_to_envelope("ping") == {"type": "ping", "data": {}}

    def test_move(self):
        assert _line_to_envelope("WQe2e5") == {"type": "move", "data": {"cmd": "WQe2e5"}}

    def test_jump_duplicates_the_square(self):
        assert _line_to_envelope("jump WPe2") == {"type": "jump", "data": {"cmd": "WPe2e2"}}


class TestWaitForMatchReady:
    def test_returns_true_promptly_when_match_ready_fires_with_no_stdin_input(self, monkeypatch):
        # Regression test: this loop used to raise TypeError before ever
        # reaching this await point (asyncio.create_task() was called on the
        # Future returned by run_in_executor, which isn't a coroutine).
        monkeypatch.setattr(sys, "stdin", _NeverRespondingStdin())

        async def body():
            client = DevClient(_FakeWebSocket())

            async def trigger_ready():
                await asyncio.sleep(0.05)
                client._match_ready.set()

            asyncio.create_task(trigger_ready())
            result = await asyncio.wait_for(client._wait_for_match_ready(), timeout=2)
            assert result is True

        asyncio.run(body())


class TestAuthenticate:
    def test_register_success_sends_credentials_and_returns_true(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", _ScriptedStdin(["1\n", "alice\n", "hunter2\n"]))

        async def body():
            websocket = _FakeWebSocket()
            client = DevClient(websocket)

            async def respond():
                await asyncio.sleep(0.01)
                client._handle_message({"type": "ack", "in_reply_to": None, "ok": True, "data": {}})

            asyncio.create_task(respond())
            result = await asyncio.wait_for(client._authenticate(), timeout=2)
            assert result is True

            import json as _json
            sent = _json.loads(websocket.sent[0])
            assert sent == {"type": "register", "data": {"username": "alice", "password": "hunter2"}}

        asyncio.run(body())

    def test_login_success_sends_the_login_command_type(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", _ScriptedStdin(["2\n", "bob\n", "pw\n"]))

        async def body():
            websocket = _FakeWebSocket()
            client = DevClient(websocket)

            async def respond():
                await asyncio.sleep(0.01)
                client._handle_message({"type": "ack", "in_reply_to": None, "ok": True, "data": {}})

            asyncio.create_task(respond())
            result = await asyncio.wait_for(client._authenticate(), timeout=2)
            assert result is True
            import json as _json
            sent = _json.loads(websocket.sent[0])
            assert sent == {"type": "login", "data": {"username": "bob", "password": "pw"}}

        asyncio.run(body())

    def test_invalid_choice_reprompts(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", _ScriptedStdin(["9\n", "1\n", "alice\n", "hunter2\n"]))

        async def body():
            websocket = _FakeWebSocket()
            client = DevClient(websocket)

            async def respond():
                await asyncio.sleep(0.01)
                client._handle_message({"type": "ack", "in_reply_to": None, "ok": True, "data": {}})

            asyncio.create_task(respond())
            result = await asyncio.wait_for(client._authenticate(), timeout=2)
            assert result is True

        asyncio.run(body())

    def test_error_reply_reprompts_instead_of_giving_up(self, monkeypatch):
        monkeypatch.setattr(
            sys, "stdin", _ScriptedStdin(["1\n", "alice\n", "hunter2\n", "1\n", "bob\n", "hunter2\n"]),
        )

        async def body():
            websocket = _FakeWebSocket()
            client = DevClient(websocket)
            replies = iter([
                {"type": "error", "code": "USERNAME_TAKEN", "message": "taken"},
                {"type": "ack", "in_reply_to": None, "ok": True, "data": {}},
            ])

            async def respond():
                for reply in replies:
                    await asyncio.sleep(0.01)
                    client._handle_message(reply)

            asyncio.create_task(respond())
            result = await asyncio.wait_for(client._authenticate(), timeout=2)
            assert result is True

        asyncio.run(body())

    def test_stdin_closing_mid_prompt_returns_false(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", _ScriptedStdin(["1\n", ""]))  # EOF after the menu choice

        async def body():
            client = DevClient(_FakeWebSocket())
            result = await asyncio.wait_for(client._authenticate(), timeout=2)
            assert result is False

        asyncio.run(body())


class TestHandleMessage:
    def test_seated_notice_prints_role(self, capsys):
        client = DevClient(_FakeWebSocket())
        client._handle_message({"type": "notice", "event": "seated", "data": {"role": "white"}})
        assert "WHITE" in capsys.readouterr().out

    def test_match_ready_broadcast_sets_the_event_and_stores_names(self):
        client = DevClient(_FakeWebSocket())
        assert not client._match_ready.is_set()
        client._handle_message({
            "type": "broadcast", "event": "match_ready",
            "data": {"white_username": "alice", "black_username": "bob"},
        })
        assert client._match_ready.is_set()
        assert client._player_names == ("alice", "bob")

    def test_error_is_printed(self, capsys):
        client = DevClient(_FakeWebSocket())
        client._handle_message({"type": "error", "code": "NOT_YOUR_COLOR", "data": {}, "message": "nope"})
        assert "NOT_YOUR_COLOR" in capsys.readouterr().out

    def test_broadcast_before_facade_exists_is_a_noop(self):
        client = DevClient(_FakeWebSocket())
        client._handle_message({
            "type": "broadcast", "event": "state_tick",
            "data": {"board_grid": [], "active_motions": [], "cooldowns": [], "game_over": False},
        })  # must not raise even though no facade has been created yet

    def test_state_tick_is_forwarded_to_the_facade(self):
        client = DevClient(_FakeWebSocket())
        client._facade = _FakeFacade()
        client._handle_message({
            "type": "broadcast", "event": "state_tick",
            "data": {"board_grid": [["wQ"]], "active_motions": [], "cooldowns": [], "game_over": True},
        })
        assert client._facade.state_ticks == [([["wQ"]], [], [], True)]

    def test_move_accepted_is_forwarded_with_parsed_types(self):
        client = DevClient(_FakeWebSocket())
        client._facade = _FakeFacade()
        client._handle_message({
            "type": "broadcast", "event": "move_accepted",
            "data": {
                "color": "white", "piece_type": "queen",
                "source": "e2", "destination": "e5", "is_capture": False,
            },
        })
        [(color, piece_type, source, destination, is_capture)] = client._facade.moves_accepted
        assert color == Color.WHITE
        assert piece_type == PieceType.QUEEN
        assert source == Position(6, 4)
        assert destination == Position(3, 4)
        assert is_capture is False

    def test_piece_captured_is_forwarded_with_parsed_types(self):
        client = DevClient(_FakeWebSocket())
        client._facade = _FakeFacade()
        client._handle_message({
            "type": "broadcast", "event": "piece_captured",
            "data": {"piece_type": "pawn", "piece_color": "black", "captured_by": "white"},
        })
        [(piece_type, piece_color, captured_by)] = client._facade.pieces_captured
        assert piece_type == PieceType.PAWN
        assert piece_color == Color.BLACK
        assert captured_by == Color.WHITE

    def test_game_over_is_forwarded_with_the_winner_name(self):
        client = DevClient(_FakeWebSocket())
        client._facade = _FakeFacade()
        client._handle_message({
            "type": "broadcast", "event": "game_over",
            "data": {"reason": "king_captured", "winner_username": "alice"},
        })
        assert client._facade.game_over_calls == 1
        assert client._facade.winner_names == ["alice"]
