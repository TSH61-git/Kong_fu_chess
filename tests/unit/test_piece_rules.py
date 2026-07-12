"""
Unit tests for rules/movement_rules.py — Movement geometry layer.

Every test operates on a Board instance built via text_io.BoardParser.
Tests are grouped by piece type and cover:
  - Reachable squares on an open board
  - Path blocking by friendly pieces (cell excluded)
  - Path blocking by enemy pieces (cell included, no further slide)
  - Off-board positions never appear in the result set
  - Wrong-direction moves are absent from the result set
  - Pawn direction, forward-only movement, and diagonal capture rules

All tests are written BEFORE the implementation exists (TDD red phase).
"""
import pytest
from text_io.board_parser import BoardParser
from model.position import Position
from rules.movement_rules import legal_destinations


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _parse(lines):
    """Shorthand: build a Board from a list of token-row strings."""
    return BoardParser.parse(lines)


def _empty(rows, cols):
    """Build an all-empty Board of given dimensions."""
    return _parse(["." * cols if cols == 1 else " ".join(["." ] * cols)] * rows)


# ------------------------------------------------------------------ #
# Rook                                                                #
# ------------------------------------------------------------------ #

class TestRookLegalDestinations:
    def test_open_board_reaches_entire_rank_and_file(self):
        board = _parse([
            ". . . . .",
            ". . . . .",
            ". . wR . .",
            ". . . . .",
            ". . . . .",
        ])
        dests = legal_destinations(board, Position(2, 2), "wR")
        # All cells in row 2 and col 2 except the source itself
        expected_row = {Position(2, c) for c in range(5) if c != 2}
        expected_col = {Position(r, 2) for r in range(5) if r != 2}
        assert expected_row | expected_col == dests

    def test_friendly_piece_blocks_and_is_excluded(self):
        board = _parse([
            ". . . . .",
            ". . wP . .",
            ". . wR . .",
            ". . . . .",
            ". . . . .",
        ])
        dests = legal_destinations(board, Position(2, 2), "wR")
        assert Position(1, 2) not in dests   # friendly blocker — excluded
        assert Position(0, 2) not in dests   # behind friendly — excluded

    def test_enemy_piece_is_included_but_blocks_further(self):
        board = _parse([
            ". . . . .",
            ". . bP . .",
            ". . wR . .",
            ". . . . .",
            ". . . . .",
        ])
        dests = legal_destinations(board, Position(2, 2), "wR")
        assert Position(1, 2) in dests       # enemy — capturable
        assert Position(0, 2) not in dests   # behind enemy — blocked

    def test_blocked_on_all_four_sides_by_friendlies(self):
        board = _parse([
            ". . wP . .",
            ". . . . .",
            "wP . wR . wP",
            ". . . . .",
            ". . wP . .",
        ])
        dests = legal_destinations(board, Position(2, 2), "wR")
        # Only the empty cells between source and each friendly blocker
        assert Position(2, 1) in dests
        assert Position(2, 3) in dests
        assert Position(1, 2) in dests
        assert Position(3, 2) in dests
        assert Position(2, 0) not in dests
        assert Position(2, 4) not in dests
        assert Position(0, 2) not in dests
        assert Position(4, 2) not in dests

    def test_diagonal_squares_never_reachable(self):
        board = _parse([". . .", ". wR .", ". . ."])
        dests = legal_destinations(board, Position(1, 1), "wR")
        assert Position(0, 0) not in dests
        assert Position(0, 2) not in dests
        assert Position(2, 0) not in dests
        assert Position(2, 2) not in dests

    def test_corner_position_has_correct_reach(self):
        board = _parse([
            "wR . . .",
            ". . . .",
            ". . . .",
            ". . . .",
        ])
        dests = legal_destinations(board, Position(0, 0), "wR")
        assert Position(0, 1) in dests
        assert Position(0, 3) in dests
        assert Position(3, 0) in dests
        assert len(dests) == 6  # 3 along row + 3 along col


# ------------------------------------------------------------------ #
# Bishop                                                              #
# ------------------------------------------------------------------ #

class TestBishopLegalDestinations:
    def test_open_board_reaches_all_diagonals(self):
        board = _parse([
            ". . . . .",
            ". . . . .",
            ". . wB . .",
            ". . . . .",
            ". . . . .",
        ])
        dests = legal_destinations(board, Position(2, 2), "wB")
        expected = {
            Position(0, 0), Position(1, 1),               # NW diagonal
            Position(1, 3), Position(0, 4),               # NE diagonal
            Position(3, 1), Position(4, 0),               # SW diagonal
            Position(3, 3), Position(4, 4),               # SE diagonal
        }
        assert expected == dests

    def test_friendly_blocker_excluded_on_diagonal(self):
        board = _parse([
            ". . . . .",
            ". wP . . .",
            ". . wB . .",
            ". . . . .",
            ". . . . .",
        ])
        dests = legal_destinations(board, Position(2, 2), "wB")
        assert Position(1, 1) not in dests   # friendly — excluded
        assert Position(0, 0) not in dests   # behind friendly — excluded

    def test_enemy_blocker_included_blocks_further(self):
        board = _parse([
            ". . . . .",
            ". bP . . .",
            ". . wB . .",
            ". . . . .",
            ". . . . .",
        ])
        dests = legal_destinations(board, Position(2, 2), "wB")
        assert Position(1, 1) in dests       # enemy — capturable
        assert Position(0, 0) not in dests   # behind enemy — blocked

    def test_straight_squares_never_reachable(self):
        board = _parse([". . .", ". wB .", ". . ."])
        dests = legal_destinations(board, Position(1, 1), "wB")
        assert Position(0, 1) not in dests
        assert Position(1, 0) not in dests
        assert Position(1, 2) not in dests
        assert Position(2, 1) not in dests

    def test_corner_bishop_has_limited_diagonals(self):
        board = _parse([
            "wB . . .",
            ". . . .",
            ". . . .",
            ". . . .",
        ])
        dests = legal_destinations(board, Position(0, 0), "wB")
        assert dests == {Position(1, 1), Position(2, 2), Position(3, 3)}


# ------------------------------------------------------------------ #
# Queen                                                               #
# ------------------------------------------------------------------ #

class TestQueenLegalDestinations:
    def test_combines_rook_and_bishop_on_open_board(self):
        board = _parse([
            ". . . . .",
            ". . . . .",
            ". . wQ . .",
            ". . . . .",
            ". . . . .",
        ])
        dests = legal_destinations(board, Position(2, 2), "wQ")
        # Must include both straight and diagonal squares
        assert Position(2, 0) in dests   # rook-like
        assert Position(0, 2) in dests   # rook-like
        assert Position(0, 0) in dests   # bishop-like
        assert Position(4, 4) in dests   # bishop-like

    def test_l_shaped_squares_never_reachable(self):
        board = _parse([". . . .", ". . . .", ". . wQ .", ". . . ."])
        dests = legal_destinations(board, Position(2, 2), "wQ")
        assert Position(0, 1) not in dests
        assert Position(1, 0) not in dests

    def test_friendly_blocker_stops_queen(self):
        board = _parse([
            ". . . . .",
            ". . wP . .",
            ". . wQ . .",
            ". . . . .",
            ". . . . .",
        ])
        dests = legal_destinations(board, Position(2, 2), "wQ")
        assert Position(1, 2) not in dests
        assert Position(0, 2) not in dests


# ------------------------------------------------------------------ #
# Knight                                                              #
# ------------------------------------------------------------------ #

class TestKnightLegalDestinations:
    def test_center_knight_has_eight_destinations(self):
        board = _parse([
            ". . . . .",
            ". . . . .",
            ". . wN . .",
            ". . . . .",
            ". . . . .",
        ])
        dests = legal_destinations(board, Position(2, 2), "wN")
        expected = {
            Position(0, 1), Position(0, 3),
            Position(1, 0), Position(1, 4),
            Position(3, 0), Position(3, 4),
            Position(4, 1), Position(4, 3),
        }
        assert expected == dests

    def test_knight_jumps_over_all_intermediate_pieces(self):
        board = _parse([
            ". . . . .",
            ". wP wP . .",
            ". wP wN wP .",
            ". wP wP . .",
            ". . . . .",
        ])
        dests = legal_destinations(board, Position(2, 2), "wN")
        # All 8 L-shape targets that are on-board and not friendly
        assert Position(0, 1) in dests
        assert Position(0, 3) in dests

    def test_friendly_destination_excluded(self):
        board = _parse([
            ". . . . .",
            ". wP . . .",
            ". . wN . .",
            ". . . . .",
            ". . . . .",
        ])
        dests = legal_destinations(board, Position(2, 2), "wN")
        assert Position(1, 0) in dests    # empty — reachable
        # wP is at (1,1) — not an L-shape target from (2,2), so irrelevant here
        # Explicitly test a friendly at an L-shape target
        board2 = _parse([
            ". wP . . .",
            ". . . . .",
            ". . wN . .",
            ". . . . .",
            ". . . . .",
        ])
        dests2 = legal_destinations(board2, Position(2, 2), "wN")
        assert Position(0, 1) not in dests2   # friendly at L-shape target

    def test_corner_knight_has_two_destinations(self):
        board = _parse([
            "wN . . .",
            ". . . .",
            ". . . .",
            ". . . .",
        ])
        dests = legal_destinations(board, Position(0, 0), "wN")
        assert dests == {Position(1, 2), Position(2, 1)}

    def test_non_l_shape_squares_absent(self):
        board = _parse([". . . .", ". . . .", ". . wN .", ". . . ."])
        dests = legal_destinations(board, Position(2, 2), "wN")
        assert Position(2, 3) not in dests   # straight
        assert Position(1, 1) not in dests   # diagonal


# ------------------------------------------------------------------ #
# King                                                                #
# ------------------------------------------------------------------ #

class TestKingLegalDestinations:
    def test_center_king_has_eight_destinations(self):
        board = _parse([
            ". . . . .",
            ". . . . .",
            ". . wK . .",
            ". . . . .",
            ". . . . .",
        ])
        dests = legal_destinations(board, Position(2, 2), "wK")
        expected = {
            Position(1, 1), Position(1, 2), Position(1, 3),
            Position(2, 1),                 Position(2, 3),
            Position(3, 1), Position(3, 2), Position(3, 3),
        }
        assert expected == dests

    def test_corner_king_has_three_destinations(self):
        board = _parse([
            "wK . .",
            ". . .",
            ". . .",
        ])
        dests = legal_destinations(board, Position(0, 0), "wK")
        assert dests == {Position(0, 1), Position(1, 0), Position(1, 1)}

    def test_friendly_adjacent_excluded(self):
        board = _parse([
            ". . .",
            ". wK wP",
            ". . .",
        ])
        dests = legal_destinations(board, Position(1, 1), "wK")
        assert Position(1, 2) not in dests   # friendly — excluded

    def test_enemy_adjacent_included(self):
        board = _parse([
            ". . .",
            ". wK bP",
            ". . .",
        ])
        dests = legal_destinations(board, Position(1, 1), "wK")
        assert Position(1, 2) in dests       # enemy — capturable

    def test_two_step_squares_absent(self):
        board = _parse([
            ". . . . .",
            ". . . . .",
            ". . wK . .",
            ". . . . .",
            ". . . . .",
        ])
        dests = legal_destinations(board, Position(2, 2), "wK")
        assert Position(0, 0) not in dests
        assert Position(2, 4) not in dests
        assert Position(4, 2) not in dests


# ------------------------------------------------------------------ #
# Pawn                                                                #
# ------------------------------------------------------------------ #

class TestPawnLegalDestinations:
    # White moves toward row 0 (decreasing row index)
    def test_white_pawn_forward_to_empty_cell(self):
        board = _parse([". .", ". .", "wP .", ". ."])
        dests = legal_destinations(board, Position(2, 0), "wP")
        assert Position(1, 0) in dests

    def test_white_pawn_blocked_by_any_piece_ahead(self):
        board = _parse([". .", "bP .", "wP .", ". ."])
        dests = legal_destinations(board, Position(2, 0), "wP")
        assert Position(1, 0) not in dests   # blocked — enemy directly ahead

    def test_white_pawn_blocked_by_friendly_ahead(self):
        board = _parse([". .", "wP .", "wP .", ". ."])
        dests = legal_destinations(board, Position(2, 0), "wP")
        assert Position(1, 0) not in dests

    def test_white_pawn_diagonal_capture_enemy(self):
        board = _parse([". . .", ". bP .", "wP . .", ". . ."])
        dests = legal_destinations(board, Position(2, 0), "wP")
        assert Position(1, 1) in dests       # diagonal capture

    def test_white_pawn_no_diagonal_capture_on_empty(self):
        board = _parse([". . .", ". . .", "wP . .", ". . ."])
        dests = legal_destinations(board, Position(2, 0), "wP")
        assert Position(1, 1) not in dests   # empty diagonal — not a capture

    def test_white_pawn_no_diagonal_capture_on_friendly(self):
        board = _parse([". . .", ". wB .", "wP . .", ". . ."])
        dests = legal_destinations(board, Position(2, 0), "wP")
        assert Position(1, 1) not in dests   # friendly diagonal — excluded

    def test_white_pawn_no_backward_move(self):
        board = _parse([". .", ". .", "wP .", ". ."])
        dests = legal_destinations(board, Position(2, 0), "wP")
        assert Position(3, 0) not in dests

    def test_white_pawn_double_step_from_start_row_when_clear(self):
        board = _parse([". .", ". .", "wP .", ". ."])
        dests = legal_destinations(board, Position(2, 0), "wP")
        assert Position(0, 0) in dests

    def test_white_pawn_double_step_blocked_by_intermediate_or_final_piece(self):
        board = _parse([". .", "wP .", "wP .", ". ."])
        dests = legal_destinations(board, Position(2, 0), "wP")
        assert Position(0, 0) not in dests

    # Black moves toward last row (increasing row index)
    def test_black_pawn_forward_to_empty_cell(self):
        board = _parse([". .", "bP .", ". .", ". ."])
        dests = legal_destinations(board, Position(1, 0), "bP")
        assert Position(2, 0) in dests

    def test_black_pawn_blocked_by_any_piece_ahead(self):
        board = _parse([". .", "bP .", "wP .", ". ."])
        dests = legal_destinations(board, Position(1, 0), "bP")
        assert Position(2, 0) not in dests

    def test_black_pawn_diagonal_capture_enemy(self):
        board = _parse([". . .", "bP . .", ". wP .", ". . ."])
        dests = legal_destinations(board, Position(1, 0), "bP")
        assert Position(2, 1) in dests

    def test_black_pawn_no_backward_move(self):
        board = _parse([". .", "bP .", ". .", ". ."])
        dests = legal_destinations(board, Position(1, 0), "bP")
        assert Position(0, 0) not in dests

    def test_black_pawn_double_step_from_start_row_when_clear(self):
        board = _parse([". .", "bP .", ". .", ". ."])
        dests = legal_destinations(board, Position(1, 0), "bP")
        assert Position(3, 0) in dests

    def test_black_pawn_double_step_blocked_by_intermediate_or_final_piece(self):
        board = _parse([". .", "bP .", "bP .", ". ."])
        dests = legal_destinations(board, Position(1, 0), "bP")
        assert Position(3, 0) not in dests


# ------------------------------------------------------------------ #
# Unknown piece type                                                  #
# ------------------------------------------------------------------ #

class TestUnknownPieceType:
    def test_unknown_piece_returns_empty_set(self):
        # Board must be valid; we pass an unknown token string directly
        # to legal_destinations to test the registry miss path.
        board = _parse(["wR ."])
        dests = legal_destinations(board, Position(0, 0), "wX")
        assert dests == set()
