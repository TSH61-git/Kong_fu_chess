from unittest.mock import MagicMock
from chess_engine.model.piece import Piece, PieceType, Color, PieceState
from chess_engine.model.position import Position
from chess_engine.realtime.arbiter import RealTimeArbiter
from app_gateways.text_cli.translator import board_from_token_lines as _parse

_WR = Piece(PieceType.ROOK, Color.WHITE)
_BK = Piece(PieceType.KING, Color.BLACK)
_BR = Piece(PieceType.ROOK, Color.BLACK)
_WK = Piece(PieceType.KING, Color.WHITE)


class TestRealTimeArbiter:
    def test_start_motion_tracks_active_motion_and_piece_state(self):
        board = _parse(["wR . ."])
        arbiter = RealTimeArbiter(board=board, game_engine=MagicMock())
        arbiter.start_motion(_WR, Position(0, 0), Position(0, 2))
        assert arbiter.has_active_motion() is True
        assert arbiter.active_motion.duration_ms == 2000
        assert arbiter.active_motion.piece == _WR
        assert board.get(Position(0, 0)) == _WR

    def test_advance_time_arrives_atomically_and_resets_piece_state(self):
        board = _parse(["wR . ."])
        arbiter = RealTimeArbiter(board=board, game_engine=MagicMock())
        arbiter.start_motion(_WR, Position(0, 0), Position(0, 2))
        arbiter.advance_time(2000)
        assert arbiter.has_active_motion() is False
        assert board.get(Position(0, 0)) is None
        assert board.get(Position(0, 2)) == _WR
        assert arbiter.active_piece.state is PieceState.IDLE

    def test_advance_time_notifies_game_engine_when_king_is_captured(self):
        board = _parse(["wR . bK"])
        game_engine = MagicMock()
        arbiter = RealTimeArbiter(board=board, game_engine=game_engine)
        arbiter.start_motion(_WR, Position(0, 0), Position(0, 2))
        arbiter.advance_time(2000)
        game_engine.notify_king_captured.assert_called_once_with()

    def test_advance_time_resolves_jump_before_linear_arrival(self):
        board = _parse(["wK . bR"])
        arbiter = RealTimeArbiter(board=board, game_engine=MagicMock())
        arbiter.start_motion(_WK, Position(0, 0), Position(0, 0), duration_ms=1000)
        arbiter.start_motion(_BR, Position(0, 2), Position(0, 0), duration_ms=1000)
        arbiter.advance_time(1000)
        assert board.get(Position(0, 0)) == _WK
        assert board.get(Position(0, 2)) is None
