import asyncio

from chess_engine.input.controller import Controller
from chess_engine.model.board import Board
from chess_engine.model.piece import Color, Piece, PieceType
from chess_engine.model.position import Position
from chess_engine.rules.engine import RuleEngine
from chess_engine.wire.notation import serialize_board

from app_gateways.gui.network_facade import NetworkGameFacade, build_network_runtime


def _run(body) -> None:
    asyncio.run(body())


class TestRequestMove:
    def test_builds_and_sends_the_wire_command_for_the_piece_at_source(self):
        async def body():
            board = Board(rows=8, cols=8)
            board.set(Position(6, 4), Piece(PieceType.QUEEN, Color.WHITE))
            sent = []

            async def send_envelope(envelope):
                sent.append(envelope)

            facade = NetworkGameFacade(board, send_envelope)
            facade.request_move(Position(6, 4), Position(3, 4))
            await asyncio.sleep(0.01)

            assert sent == [{"type": "move", "data": {"cmd": "WQe2e5"}}]

        _run(body)

    def test_empty_source_sends_nothing(self):
        async def body():
            board = Board(rows=8, cols=8)
            sent = []

            async def send_envelope(envelope):
                sent.append(envelope)

            facade = NetworkGameFacade(board, send_envelope)
            facade.request_move(Position(6, 4), Position(3, 4))
            await asyncio.sleep(0.01)

            assert sent == []

        _run(body)


class TestRequestJump:
    def test_duplicates_the_square_into_source_and_destination(self):
        async def body():
            board = Board(rows=8, cols=8)
            board.set(Position(6, 4), Piece(PieceType.PAWN, Color.WHITE))
            sent = []

            async def send_envelope(envelope):
                sent.append(envelope)

            facade = NetworkGameFacade(board, send_envelope)
            facade.request_jump(Position(6, 4))
            await asyncio.sleep(0.01)

            assert sent == [{"type": "jump", "data": {"cmd": "WPe2e2"}}]

        _run(body)


class TestValidateMove:
    def test_delegates_to_a_local_rule_engine(self):
        board = Board(rows=8, cols=8)
        board.set(Position(6, 4), Piece(PieceType.QUEEN, Color.WHITE))
        board.set(Position(3, 4), Piece(PieceType.PAWN, Color.WHITE))

        async def noop_send(_envelope):
            pass

        facade = NetworkGameFacade(board, noop_send)
        expected = RuleEngine().validate_move(board, Position(6, 4), Position(3, 4))
        assert facade.validate_move(board, Position(6, 4), Position(3, 4)) == expected
        assert expected.reason == "friendly_destination"


class TestApplyStateTick:
    def test_refreshes_board_motions_cooldowns_and_game_over(self):
        board = Board(rows=8, cols=8)

        async def noop_send(_envelope):
            pass

        facade = NetworkGameFacade(board, noop_send)
        source_board = Board(rows=8, cols=8)
        source_board.set(Position(0, 0), Piece(PieceType.ROOK, Color.BLACK))

        facade.apply_state_tick(
            board_grid=serialize_board(source_board),
            active_motions=[{
                "piece": "wQ", "source": "e2", "destination": "e5",
                "elapsed_ms": 100, "duration_ms": 700,
            }],
            cooldowns=[{"square": "e5", "remaining_ms": 640}],
            game_over=True,
        )

        assert board.get(Position(0, 0)) == Piece(PieceType.ROOK, Color.BLACK)
        [motion] = facade.get_active_motions()
        assert motion.source == Position(6, 4) and motion.destination == Position(3, 4)
        assert facade.get_cooldowns() == {Position(3, 4): 640}
        assert facade.get_snapshot().game_over is True


class TestApplyMoveAccepted:
    def test_feeds_move_history(self):
        board = Board(rows=8, cols=8)

        async def noop_send(_envelope):
            pass

        facade = NetworkGameFacade(board, noop_send)
        facade.apply_move_accepted(
            Color.WHITE, PieceType.QUEEN, Position(6, 4), Position(3, 4), is_capture=False,
        )
        [entry] = facade.history_entries()
        assert entry.color == Color.WHITE
        assert entry.piece_type == PieceType.QUEEN
        assert entry.display_text() == "Qe5"


class TestApplyPieceCaptured:
    def test_feeds_score_manager(self):
        board = Board(rows=8, cols=8)

        async def noop_send(_envelope):
            pass

        facade = NetworkGameFacade(board, noop_send)
        facade.apply_piece_captured(PieceType.QUEEN, Color.BLACK, captured_by=Color.WHITE)

        captured = facade.get_captured(Color.WHITE)
        assert len(captured) == 1
        assert captured[0].piece.piece_type == PieceType.QUEEN
        assert facade.get_scores()[Color.WHITE] == 9


class TestInitialScores:
    def test_get_scores_starts_from_the_injected_snapshot(self):
        async def noop_send(_envelope):
            pass

        board = Board(rows=8, cols=8)
        facade = NetworkGameFacade(board, noop_send, initial_scores=(9, 3))
        assert facade.get_scores() == {Color.WHITE: 9, Color.BLACK: 3}

    def test_later_captures_add_on_top_of_the_initial_snapshot(self):
        async def noop_send(_envelope):
            pass

        board = Board(rows=8, cols=8)
        facade = NetworkGameFacade(board, noop_send, initial_scores=(9, 3))
        facade.apply_piece_captured(PieceType.PAWN, Color.BLACK, captured_by=Color.WHITE)
        assert facade.get_scores()[Color.WHITE] == 10
        assert facade.get_scores()[Color.BLACK] == 3

    def test_defaults_to_zero_zero(self):
        async def noop_send(_envelope):
            pass

        board = Board(rows=8, cols=8)
        facade = NetworkGameFacade(board, noop_send)
        assert facade.get_scores() == {Color.WHITE: 0, Color.BLACK: 0}


class TestAdvanceTime:
    def test_is_a_noop(self):
        board = Board(rows=8, cols=8)

        async def noop_send(_envelope):
            pass

        facade = NetworkGameFacade(board, noop_send)
        facade.advance_time(50)  # must not raise


class TestBuildNetworkRuntime:
    def test_engine_and_arbiter_are_the_same_facade(self):
        async def noop_send(_envelope):
            pass

        board = Board(rows=8, cols=8)
        runtime = build_network_runtime(board, noop_send)
        assert runtime.engine is runtime.arbiter
        assert isinstance(runtime.engine, NetworkGameFacade)

    def test_controller_is_wired_to_the_facade_and_board(self):
        async def noop_send(_envelope):
            pass

        board = Board(rows=8, cols=8)
        runtime = build_network_runtime(board, noop_send)
        assert isinstance(runtime.controller, Controller)
        assert runtime.board is board

    def test_room_id_and_read_only_thread_through_to_the_facade(self):
        async def noop_send(_envelope):
            pass

        board = Board(rows=8, cols=8)
        runtime = build_network_runtime(board, noop_send, room_id="ABC123", read_only=True, initial_scores=(9, 3))
        assert runtime.engine.get_room_id() == "ABC123"
        assert runtime.engine.is_read_only() is True
        assert runtime.engine.get_scores() == {Color.WHITE: 9, Color.BLACK: 3}

    def test_defaults_are_none_and_not_read_only(self):
        async def noop_send(_envelope):
            pass

        board = Board(rows=8, cols=8)
        runtime = build_network_runtime(board, noop_send)
        assert runtime.engine.get_room_id() is None
        assert runtime.engine.is_read_only() is False


class TestReadOnly:
    def test_request_move_is_a_noop_when_read_only(self):
        async def body():
            board = Board(rows=8, cols=8)
            board.set(Position(6, 4), Piece(PieceType.QUEEN, Color.WHITE))
            sent = []

            async def send_envelope(envelope):
                sent.append(envelope)

            facade = NetworkGameFacade(board, send_envelope, read_only=True)
            facade.request_move(Position(6, 4), Position(3, 4))
            await asyncio.sleep(0.01)

            assert sent == []

        _run(body)

    def test_request_jump_is_a_noop_when_read_only(self):
        async def body():
            board = Board(rows=8, cols=8)
            board.set(Position(6, 4), Piece(PieceType.PAWN, Color.WHITE))
            sent = []

            async def send_envelope(envelope):
                sent.append(envelope)

            facade = NetworkGameFacade(board, send_envelope, read_only=True)
            facade.request_jump(Position(6, 4))
            await asyncio.sleep(0.01)

            assert sent == []

        _run(body)


class TestIsWaitingForOpponent:
    def test_false_before_any_state_tick_arrives(self):
        async def noop_send(_envelope):
            pass

        board = Board(rows=8, cols=8)
        facade = NetworkGameFacade(board, noop_send, room_id="ABC123")
        assert facade.is_waiting_for_opponent() is False

    def test_true_once_a_frozen_state_tick_arrives(self):
        async def noop_send(_envelope):
            pass

        board = Board(rows=8, cols=8)
        facade = NetworkGameFacade(board, noop_send, room_id="ABC123")
        facade.apply_state_tick(board_grid=[[None]], active_motions=[], cooldowns=[], game_over=False, frozen=True)
        assert facade.is_waiting_for_opponent() is True

    def test_false_once_an_unfrozen_state_tick_arrives(self):
        # Regression: a viewer joining an already-active room must not show
        # "waiting for opponent" just because it never saw match_ready —
        # the real signal is the server's frozen state, not player_names.
        async def noop_send(_envelope):
            pass

        board = Board(rows=8, cols=8)
        facade = NetworkGameFacade(board, noop_send, room_id="ABC123")
        facade.apply_state_tick(board_grid=[[None]], active_motions=[], cooldowns=[], game_over=False, frozen=False)
        assert facade.is_waiting_for_opponent() is False
