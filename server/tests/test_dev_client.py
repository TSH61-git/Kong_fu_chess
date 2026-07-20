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

    def apply_state_tick(self, board_grid, active_motions, cooldowns, game_over) -> None:
        self.state_ticks.append((board_grid, active_motions, cooldowns, game_over))

    def apply_move_accepted(self, color, piece_type, source, destination, is_capture) -> None:
        self.moves_accepted.append((color, piece_type, source, destination, is_capture))

    def apply_piece_captured(self, piece_type, piece_color, captured_by) -> None:
        self.pieces_captured.append((piece_type, piece_color, captured_by))

    def apply_game_over(self) -> None:
        self.game_over_calls += 1


class TestLineToEnvelope:
    def test_ping(self):
        assert _line_to_envelope("ping") == {"type": "ping", "data": {}}

    def test_move(self):
        assert _line_to_envelope("WQe2e5") == {"type": "move", "data": {"cmd": "WQe2e5"}}

    def test_jump_duplicates_the_square(self):
        assert _line_to_envelope("jump WPe2") == {"type": "jump", "data": {"cmd": "WPe2e2"}}


class TestRunShellPhase:
    def test_returns_true_promptly_when_match_ready_fires_with_no_stdin_input(self, monkeypatch):
        # Regression test: run_shell_phase() used to raise TypeError before
        # ever reaching this await point (asyncio.create_task() was called
        # on the Future returned by run_in_executor, which isn't a coroutine).
        monkeypatch.setattr(sys, "stdin", _NeverRespondingStdin())

        async def body():
            client = DevClient(_FakeWebSocket())

            async def trigger_ready():
                await asyncio.sleep(0.05)
                client._match_ready.set()

            asyncio.create_task(trigger_ready())
            result = await asyncio.wait_for(client.run_shell_phase(), timeout=2)
            assert result is True

        asyncio.run(body())


class TestHandleMessage:
    def test_seated_notice_prints_role(self, capsys):
        client = DevClient(_FakeWebSocket())
        client._handle_message({"type": "notice", "event": "seated", "data": {"role": "white"}})
        assert "WHITE" in capsys.readouterr().out

    def test_match_ready_broadcast_sets_the_event(self):
        client = DevClient(_FakeWebSocket())
        assert not client._match_ready.is_set()
        client._handle_message({"type": "broadcast", "event": "match_ready", "data": {}})
        assert client._match_ready.is_set()

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

    def test_game_over_is_forwarded(self):
        client = DevClient(_FakeWebSocket())
        client._facade = _FakeFacade()
        client._handle_message({"type": "broadcast", "event": "game_over", "data": {"reason": "king_captured"}})
        assert client._facade.game_over_calls == 1
