import pytest
from unittest.mock import MagicMock
from chess_engine.model.position import Position
from chess_engine.model.piece import Piece, PieceType, Color
from chess_engine.realtime.arbiter import RealTimeArbiter
from chess_engine.rules.trajectory import linear_path, has_route_conflict
from app_gateways.text_cli.translator import board_from_token_lines as _parse

_WR = Piece(PieceType.ROOK, Color.WHITE)
_BR = Piece(PieceType.ROOK, Color.BLACK)
_WB = Piece(PieceType.BISHOP, Color.WHITE)
_WQ = Piece(PieceType.QUEEN, Color.WHITE)
_WK = Piece(PieceType.KING, Color.WHITE)
_BK = Piece(PieceType.KING, Color.BLACK)


class TestLinearPath:
    def test_horizontal_path(self):
        assert linear_path(Position(0,0), Position(0,3)) == [
            Position(0,0), Position(0,1), Position(0,2), Position(0,3)]

    def test_vertical_path(self):
        assert linear_path(Position(0,0), Position(3,0)) == [
            Position(0,0), Position(1,0), Position(2,0), Position(3,0)]

    def test_diagonal_path(self):
        assert linear_path(Position(0,0), Position(2,2)) == [
            Position(0,0), Position(1,1), Position(2,2)]

    def test_single_cell_jump(self):
        assert linear_path(Position(1,1), Position(1,1)) == [Position(1,1)]

    def test_knight_shaped_move_returns_endpoints_without_hanging(self):
        assert linear_path(Position(0,0), Position(2,1)) == [Position(0,0), Position(2,1)]

    def test_reverse_horizontal(self):
        assert linear_path(Position(0,3), Position(0,0)) == [
            Position(0,3), Position(0,2), Position(0,1), Position(0,0)]


class TestHasRouteConflict:
    def test_overlapping_horizontal_routes_conflict(self):
        assert has_route_conflict(Position(0,0), Position(0,4), Position(0,2), Position(0,6)) is True

    def test_non_overlapping_routes_no_conflict(self):
        assert has_route_conflict(Position(0,0), Position(0,1), Position(0,3), Position(0,5)) is False

    def test_perpendicular_crossing_routes_conflict(self):
        assert has_route_conflict(Position(0,2), Position(4,2), Position(2,0), Position(2,4)) is True

    def test_jump_source_eq_destination_no_conflict(self):
        assert has_route_conflict(Position(1,1), Position(1,1), Position(0,0), Position(3,3)) is False

    def test_identical_routes_conflict(self):
        assert has_route_conflict(Position(0,0), Position(0,3), Position(0,0), Position(0,3)) is True


class TestEnemyMidRouteCollision:
    def _arbiter(self, lines):
        board = _parse(lines)
        return RealTimeArbiter(board=board, game_engine=MagicMock()), board

    def test_enemy_pieces_collide_earlier_one_cancelled(self):
        arbiter, board = self._arbiter([". . . . ."])
        board.set(Position(0, 0), _WR)
        board.set(Position(0, 4), _BR)
        arbiter.start_motion(_WR, Position(0,0), Position(0,4), duration_ms=4000)
        arbiter.start_motion(_BR, Position(0,4), Position(0,0), duration_ms=4000)
        arbiter.advance_time(2000)
        cells = [board.get(Position(0, c)) for c in range(5)]
        assert _WR in cells or _BR in cells

    def test_mover_captures_hold_piece_once_it_actually_arrives(self):
        arbiter, board = self._arbiter(["wK . . bR"])
        arbiter.start_motion(_WK, Position(0,0), Position(0,0), duration_ms=1000)
        arbiter.start_motion(_BR, Position(0,3), Position(0,0), duration_ms=3000)
        arbiter.advance_time(1000)
        # Not colliding yet: the rook hasn't reached (0,0), so the hold motion
        # resolves normally and the king sits back down.
        assert board.get(Position(0, 0)) == _WK
        arbiter.advance_time(2000)
        # Once the rook actually lands, it captures the king that finished
        # resting there long before.
        assert board.get(Position(0, 0)) == _BR

    def test_enemy_linear_vs_linear_head_on_loser_fully_captured(self):
        arbiter, board = self._arbiter([". . . . ."])
        board.set(Position(0, 0), _WR)
        board.set(Position(0, 4), _BR)
        arbiter.start_motion(_WR, Position(0,0), Position(0,4), duration_ms=4000)
        arbiter.start_motion(_BR, Position(0,4), Position(0,0), duration_ms=4000)
        arbiter.advance_time(2000)
        cells = [board.get(Position(0, c)) for c in range(5)]
        assert (_WR in cells) != (_BR in cells)


class TestFriendlyMidRouteCollision:
    def _arbiter(self, lines):
        board = _parse(lines)
        return RealTimeArbiter(board=board, game_engine=MagicMock()), board

    def test_friendly_collision_does_not_capture(self):
        arbiter, board = self._arbiter([". . . . ."])
        board.set(Position(0, 0), _WR)
        board.set(Position(0, 2), _WQ)
        arbiter.start_motion(_WR, Position(0,0), Position(0,4), duration_ms=4000)
        arbiter.start_motion(_WQ, Position(0,2), Position(0,4), duration_ms=2000)
        arbiter.advance_time(2000)
        all_pieces = [board.get(Position(0, c)) for c in range(5)]
        assert _WR in all_pieces
        assert _WQ in all_pieces

    def test_friendly_no_collision_when_paths_dont_overlap(self):
        arbiter, board = self._arbiter([". . . . . . ."])
        board.set(Position(0, 0), _WR)
        board.set(Position(0, 3), _WB)
        arbiter.start_motion(_WR, Position(0,0), Position(0,2), duration_ms=2000)
        arbiter.start_motion(_WB, Position(0,3), Position(0,6), duration_ms=3000)
        arbiter.advance_time(2000)
        assert board.get(Position(0, 2)) == _WR


class TestCollisionOrdering:
    def _arbiter(self, lines):
        board = _parse(lines)
        return RealTimeArbiter(board=board, game_engine=MagicMock()), board

    def test_linear_arrival_resolved_before_jump_arrival(self):
        arbiter, board = self._arbiter(["wK . bR"])
        arbiter.start_motion(_WK, Position(0,0), Position(0,0), duration_ms=1000)
        arbiter.start_motion(_BR, Position(0,2), Position(0,0), duration_ms=1000)
        arbiter.advance_time(1000)
        assert board.get(Position(0, 2)) is None

    def test_multiple_linear_motions_complete_in_order(self):
        arbiter, board = self._arbiter([". . . . ."])
        board.set(Position(0, 0), _WR)
        board.set(Position(0, 4), _BR)
        arbiter.start_motion(_WR, Position(0,0), Position(0,2), duration_ms=2000)
        arbiter.start_motion(_BR, Position(0,4), Position(0,2), duration_ms=2000)
        arbiter.advance_time(2000)
        result = board.get(Position(0, 2))
        assert result in {_WR, _BR}


class TestJumpDefendsAgainstIncomingCapture:
    # Regression coverage for the "jumping pawn eaten by the piece that
    # arrives" bug: a piece actively holding a jump on a cell must survive
    # and capture an enemy motion that lands on that same cell, instead of
    # being captured itself (or silently erased).
    def _arbiter(self, lines):
        board = _parse(lines)
        return RealTimeArbiter(board=board, game_engine=MagicMock()), board

    def test_jump_survives_and_captures_enemy_landing_on_same_cell(self):
        arbiter, board = self._arbiter(["wP . . bP .", ". . . . ."])
        wp = board.get(Position(0, 0))
        bp = board.get(Position(0, 3))
        # black starts an in-place jump on its own cell
        arbiter.start_motion(bp, Position(0, 3), Position(0, 3), duration_ms=1000)
        arbiter.advance_time(500)
        # white starts a linear move landing on the same cell mid-jump
        arbiter.start_motion(wp, Position(0, 0), Position(0, 3), duration_ms=1000)
        arbiter.advance_time(1000)
        assert board.get(Position(0, 3)) == bp
        assert board.get(Position(0, 0)) is None

    def test_jump_started_after_attacker_still_wins(self):
        arbiter, board = self._arbiter(["wP . . bP .", ". . . . ."])
        wp = board.get(Position(0, 0))
        bp = board.get(Position(0, 3))
        arbiter.start_motion(wp, Position(0, 0), Position(0, 3), duration_ms=1000)
        arbiter.advance_time(900)
        arbiter.start_motion(bp, Position(0, 3), Position(0, 3), duration_ms=1000)
        arbiter.advance_time(1000)
        assert board.get(Position(0, 3)) == bp
        assert board.get(Position(0, 0)) is None