"""Unit tests for the real-time motion arbiter."""
from unittest.mock import MagicMock

from model.piece import PieceState
from model.position import Position
from realtime.real_time_arbiter import RealTimeArbiter
from text_io.board_parser import BoardParser


class TestRealTimeArbiter:
    def test_start_motion_tracks_active_motion_and_piece_state(self):
        board = BoardParser.parse(["wR . ."])
        game_engine = MagicMock()
        arbiter = RealTimeArbiter(board=board, game_engine=game_engine)

        arbiter.start_motion("wR", Position(0, 0), Position(0, 2))

        assert arbiter.has_active_motion() is True
        assert arbiter.active_motion is not None
        assert arbiter.active_motion.duration_ms == 2000
        assert arbiter.active_motion.piece == "wR"
        assert board.get(Position(0, 0)) == "wR"

    def test_advance_time_arrives_atomically_and_resets_piece_state(self):
        board = BoardParser.parse(["wR . ."])
        game_engine = MagicMock()
        arbiter = RealTimeArbiter(board=board, game_engine=game_engine)
        arbiter.start_motion("wR", Position(0, 0), Position(0, 2))

        arbiter.advance_time(2000)

        assert arbiter.has_active_motion() is False
        assert board.get(Position(0, 0)) == "."
        assert board.get(Position(0, 2)) == "wR"
        assert arbiter.active_piece.state is PieceState.IDLE

    def test_advance_time_notifies_game_engine_when_king_is_captured(self):
        board = BoardParser.parse(["wR . bK"])
        game_engine = MagicMock()
        arbiter = RealTimeArbiter(board=board, game_engine=game_engine)
        arbiter.start_motion("wR", Position(0, 0), Position(0, 2))

        arbiter.advance_time(2000)

        game_engine.notify_king_captured.assert_called_once_with()

    def test_advance_time_resolves_jump_after_horizontal_move_and_overwrites_destination(self):
        board = BoardParser.parse(["wK . bR"])
        game_engine = MagicMock()
        arbiter = RealTimeArbiter(board=board, game_engine=game_engine)
        arbiter.start_motion("wK", Position(0, 0), Position(0, 0), duration_ms=1000)
        arbiter.start_motion("bR", Position(0, 2), Position(0, 0), duration_ms=1000)

        arbiter.advance_time(1000)

        assert board.get(Position(0, 0)) == "wK"
        assert board.get(Position(0, 2)) == "."
