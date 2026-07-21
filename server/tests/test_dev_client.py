import asyncio
import sys

from chess_engine.model.piece import Color, PieceType
from chess_engine.model.position import Position

from server.dev_client import DevClient
from server.tests.support import wait_until


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


class _FakeFacade:
    def __init__(self) -> None:
        self.state_ticks: list[tuple] = []
        self.moves_accepted: list[tuple] = []
        self.pieces_captured: list[tuple] = []
        self.game_over_calls = 0
        self.winner_names: list = []
        self.game_over_reasons: list = []

    def apply_state_tick(self, board_grid, active_motions, cooldowns, game_over) -> None:
        self.state_ticks.append((board_grid, active_motions, cooldowns, game_over))

    def apply_move_accepted(self, color, piece_type, source, destination, is_capture) -> None:
        self.moves_accepted.append((color, piece_type, source, destination, is_capture))

    def apply_piece_captured(self, piece_type, piece_color, captured_by) -> None:
        self.pieces_captured.append((piece_type, piece_color, captured_by))

    def apply_game_over(self, reason=None, winner_username=None) -> None:
        self.game_over_calls += 1
        self.winner_names.append(winner_username)
        self.game_over_reasons.append(reason)


class TestAuthenticate:
    def test_register_success_sends_credentials_and_returns_true(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", _ScriptedStdin(["1\n", "alice\n", "hunter2\n"]))

        async def body():
            websocket = _FakeWebSocket()
            client = DevClient(websocket)

            async def respond():
                await wait_until(lambda: client._pending_response is not None)
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
                await wait_until(lambda: client._pending_response is not None)
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
                await wait_until(lambda: client._pending_response is not None)
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
                previous = None
                for reply in replies:
                    await wait_until(
                        lambda: client._pending_response is not None and client._pending_response is not previous,
                    )
                    previous = client._pending_response
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
        assert client._facade.game_over_reasons == ["king_captured"]
