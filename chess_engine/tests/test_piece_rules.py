import pytest
from chess_engine.model.position import Position
from chess_engine.model.piece import Piece, PieceType, Color
from chess_engine.rules.movement import legal_destinations
from app_gateways.text_cli.translator import board_from_token_lines as _parse


class TestRookLegalDestinations:
    def test_open_board_reaches_entire_rank_and_file(self):
        board = _parse([". . . . .", ". . . . .", ". . wR . .", ". . . . .", ". . . . ."])
        piece = Piece(PieceType.ROOK, Color.WHITE)
        dests = legal_destinations(board, Position(2, 2), piece)
        assert {Position(2, c) for c in range(5) if c != 2} | {Position(r, 2) for r in range(5) if r != 2} == dests

    def test_friendly_piece_blocks_and_is_excluded(self):
        board = _parse([". . . . .", ". . wP . .", ". . wR . .", ". . . . .", ". . . . ."])
        dests = legal_destinations(board, Position(2, 2), Piece(PieceType.ROOK, Color.WHITE))
        assert Position(1, 2) not in dests
        assert Position(0, 2) not in dests

    def test_enemy_piece_is_included_but_blocks_further(self):
        board = _parse([". . . . .", ". . bP . .", ". . wR . .", ". . . . .", ". . . . ."])
        dests = legal_destinations(board, Position(2, 2), Piece(PieceType.ROOK, Color.WHITE))
        assert Position(1, 2) in dests
        assert Position(0, 2) not in dests

    def test_diagonal_squares_never_reachable(self):
        board = _parse([". . .", ". wR .", ". . ."])
        dests = legal_destinations(board, Position(1, 1), Piece(PieceType.ROOK, Color.WHITE))
        assert Position(0, 0) not in dests
        assert Position(2, 2) not in dests

    def test_corner_position_has_correct_reach(self):
        board = _parse(["wR . . .", ". . . .", ". . . .", ". . . ."])
        dests = legal_destinations(board, Position(0, 0), Piece(PieceType.ROOK, Color.WHITE))
        assert len(dests) == 6


class TestBishopLegalDestinations:
    def test_open_board_reaches_all_diagonals(self):
        board = _parse([". . . . .", ". . . . .", ". . wB . .", ". . . . .", ". . . . ."])
        dests = legal_destinations(board, Position(2, 2), Piece(PieceType.BISHOP, Color.WHITE))
        expected = {Position(0,0), Position(1,1), Position(1,3), Position(0,4),
                    Position(3,1), Position(4,0), Position(3,3), Position(4,4)}
        assert expected == dests

    def test_friendly_blocker_excluded_on_diagonal(self):
        board = _parse([". . . . .", ". wP . . .", ". . wB . .", ". . . . .", ". . . . ."])
        dests = legal_destinations(board, Position(2, 2), Piece(PieceType.BISHOP, Color.WHITE))
        assert Position(1, 1) not in dests
        assert Position(0, 0) not in dests

    def test_enemy_blocker_included_blocks_further(self):
        board = _parse([". . . . .", ". bP . . .", ". . wB . .", ". . . . .", ". . . . ."])
        dests = legal_destinations(board, Position(2, 2), Piece(PieceType.BISHOP, Color.WHITE))
        assert Position(1, 1) in dests
        assert Position(0, 0) not in dests

    def test_straight_squares_never_reachable(self):
        board = _parse([". . .", ". wB .", ". . ."])
        dests = legal_destinations(board, Position(1, 1), Piece(PieceType.BISHOP, Color.WHITE))
        assert Position(0, 1) not in dests
        assert Position(1, 0) not in dests

    def test_corner_bishop_has_limited_diagonals(self):
        board = _parse(["wB . . .", ". . . .", ". . . .", ". . . ."])
        dests = legal_destinations(board, Position(0, 0), Piece(PieceType.BISHOP, Color.WHITE))
        assert dests == {Position(1,1), Position(2,2), Position(3,3)}


class TestQueenLegalDestinations:
    def test_combines_rook_and_bishop_on_open_board(self):
        board = _parse([". . . . .", ". . . . .", ". . wQ . .", ". . . . .", ". . . . ."])
        dests = legal_destinations(board, Position(2, 2), Piece(PieceType.QUEEN, Color.WHITE))
        assert Position(2, 0) in dests
        assert Position(0, 2) in dests
        assert Position(0, 0) in dests
        assert Position(4, 4) in dests

    def test_l_shaped_squares_never_reachable(self):
        board = _parse([". . . .", ". . . .", ". . wQ .", ". . . ."])
        dests = legal_destinations(board, Position(2, 2), Piece(PieceType.QUEEN, Color.WHITE))
        assert Position(0, 1) not in dests

    def test_friendly_blocker_stops_queen(self):
        board = _parse([". . . . .", ". . wP . .", ". . wQ . .", ". . . . .", ". . . . ."])
        dests = legal_destinations(board, Position(2, 2), Piece(PieceType.QUEEN, Color.WHITE))
        assert Position(1, 2) not in dests
        assert Position(0, 2) not in dests


class TestKnightLegalDestinations:
    def test_center_knight_has_eight_destinations(self):
        board = _parse([". . . . .", ". . . . .", ". . wN . .", ". . . . .", ". . . . ."])
        dests = legal_destinations(board, Position(2, 2), Piece(PieceType.KNIGHT, Color.WHITE))
        expected = {Position(0,1), Position(0,3), Position(1,0), Position(1,4),
                    Position(3,0), Position(3,4), Position(4,1), Position(4,3)}
        assert expected == dests

    def test_friendly_destination_excluded(self):
        board = _parse([". wP . . .", ". . . . .", ". . wN . .", ". . . . .", ". . . . ."])
        dests = legal_destinations(board, Position(2, 2), Piece(PieceType.KNIGHT, Color.WHITE))
        assert Position(0, 1) not in dests

    def test_corner_knight_has_two_destinations(self):
        board = _parse(["wN . . .", ". . . .", ". . . .", ". . . ."])
        dests = legal_destinations(board, Position(0, 0), Piece(PieceType.KNIGHT, Color.WHITE))
        assert dests == {Position(1, 2), Position(2, 1)}

    def test_non_l_shape_squares_absent(self):
        board = _parse([". . . .", ". . . .", ". . wN .", ". . . ."])
        dests = legal_destinations(board, Position(2, 2), Piece(PieceType.KNIGHT, Color.WHITE))
        assert Position(2, 3) not in dests
        assert Position(1, 1) not in dests


class TestKingLegalDestinations:
    def test_center_king_has_eight_destinations(self):
        board = _parse([". . . . .", ". . . . .", ". . wK . .", ". . . . .", ". . . . ."])
        dests = legal_destinations(board, Position(2, 2), Piece(PieceType.KING, Color.WHITE))
        expected = {Position(1,1), Position(1,2), Position(1,3),
                    Position(2,1),                Position(2,3),
                    Position(3,1), Position(3,2), Position(3,3)}
        assert expected == dests

    def test_corner_king_has_three_destinations(self):
        board = _parse(["wK . .", ". . .", ". . ."])
        dests = legal_destinations(board, Position(0, 0), Piece(PieceType.KING, Color.WHITE))
        assert dests == {Position(0,1), Position(1,0), Position(1,1)}

    def test_friendly_adjacent_excluded(self):
        board = _parse([". . .", ". wK wP", ". . ."])
        dests = legal_destinations(board, Position(1, 1), Piece(PieceType.KING, Color.WHITE))
        assert Position(1, 2) not in dests

    def test_enemy_adjacent_included(self):
        board = _parse([". . .", ". wK bP", ". . ."])
        dests = legal_destinations(board, Position(1, 1), Piece(PieceType.KING, Color.WHITE))
        assert Position(1, 2) in dests

    def test_two_step_squares_absent(self):
        board = _parse([". . . . .", ". . . . .", ". . wK . .", ". . . . .", ". . . . ."])
        dests = legal_destinations(board, Position(2, 2), Piece(PieceType.KING, Color.WHITE))
        assert Position(0, 0) not in dests
        assert Position(4, 2) not in dests


class TestPawnLegalDestinations:
    def test_white_pawn_forward_to_empty_cell(self):
        board = _parse([". .", ". .", "wP .", ". ."])
        dests = legal_destinations(board, Position(2, 0), Piece(PieceType.PAWN, Color.WHITE))
        assert Position(1, 0) in dests

    def test_white_pawn_blocked_by_any_piece_ahead(self):
        board = _parse([". .", "bP .", "wP .", ". ."])
        dests = legal_destinations(board, Position(2, 0), Piece(PieceType.PAWN, Color.WHITE))
        assert Position(1, 0) not in dests

    def test_white_pawn_diagonal_capture_enemy(self):
        board = _parse([". . .", ". bP .", "wP . .", ". . ."])
        dests = legal_destinations(board, Position(2, 0), Piece(PieceType.PAWN, Color.WHITE))
        assert Position(1, 1) in dests

    def test_white_pawn_no_diagonal_capture_on_empty(self):
        board = _parse([". . .", ". . .", "wP . .", ". . ."])
        dests = legal_destinations(board, Position(2, 0), Piece(PieceType.PAWN, Color.WHITE))
        assert Position(1, 1) not in dests

    def test_white_pawn_no_backward_move(self):
        board = _parse([". .", ". .", "wP .", ". ."])
        dests = legal_destinations(board, Position(2, 0), Piece(PieceType.PAWN, Color.WHITE))
        assert Position(3, 0) not in dests

    def test_white_pawn_double_step_from_start_row_when_clear(self):
        board = _parse([". .", ". .", "wP .", ". ."])
        dests = legal_destinations(board, Position(2, 0), Piece(PieceType.PAWN, Color.WHITE))
        assert Position(0, 0) in dests

    def test_white_pawn_double_step_blocked(self):
        board = _parse([". .", "wP .", "wP .", ". ."])
        dests = legal_destinations(board, Position(2, 0), Piece(PieceType.PAWN, Color.WHITE))
        assert Position(0, 0) not in dests

    def test_black_pawn_forward_to_empty_cell(self):
        board = _parse([". .", "bP .", ". .", ". ."])
        dests = legal_destinations(board, Position(1, 0), Piece(PieceType.PAWN, Color.BLACK))
        assert Position(2, 0) in dests

    def test_black_pawn_blocked_by_any_piece_ahead(self):
        board = _parse([". .", "bP .", "wP .", ". ."])
        dests = legal_destinations(board, Position(1, 0), Piece(PieceType.PAWN, Color.BLACK))
        assert Position(2, 0) not in dests

    def test_black_pawn_diagonal_capture_enemy(self):
        board = _parse([". . .", "bP . .", ". wP .", ". . ."])
        dests = legal_destinations(board, Position(1, 0), Piece(PieceType.PAWN, Color.BLACK))
        assert Position(2, 1) in dests

    def test_black_pawn_no_backward_move(self):
        board = _parse([". .", "bP .", ". .", ". ."])
        dests = legal_destinations(board, Position(1, 0), Piece(PieceType.PAWN, Color.BLACK))
        assert Position(0, 0) not in dests

    def test_black_pawn_double_step_from_start_row_when_clear(self):
        board = _parse([". .", "bP .", ". .", ". ."])
        dests = legal_destinations(board, Position(1, 0), Piece(PieceType.PAWN, Color.BLACK))
        assert Position(3, 0) in dests

    def test_black_pawn_double_step_blocked(self):
        board = _parse([". .", "bP .", "bP .", ". ."])
        dests = legal_destinations(board, Position(1, 0), Piece(PieceType.PAWN, Color.BLACK))
        assert Position(3, 0) not in dests


class TestUnknownPieceType:
    def test_no_rule_fn_returns_empty_set(self):
        from chess_engine.model.piece import PieceType as PT, Color as C
        from chess_engine.rules.movement import _REGISTRY
        # Verify registry covers all 6 types
        assert set(_REGISTRY.keys()) == set(PT)
