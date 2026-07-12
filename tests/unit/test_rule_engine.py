"""
Unit tests for rules/rule_engine.py — RuleEngine validation service.

Tests verify:
  - MoveValidation is a read-only dataclass with is_valid and reason fields
  - Every invalid path returns the correct machine-readable reason string
  - The evaluation order is strictly enforced (outside_board before empty_source, etc.)
  - A fully valid move returns reason "ok" and is_valid True
  - RuleEngine never mutates the Board

All tests are written BEFORE the implementation exists (TDD red phase).
"""
import pytest
from text_io.board_parser import BoardParser
from model.position import Position
from rules.rule_engine import RuleEngine, MoveValidation


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _parse(lines):
    return BoardParser.parse(lines)


@pytest.fixture
def engine():
    return RuleEngine()


# ------------------------------------------------------------------ #
# MoveValidation dataclass contract                                   #
# ------------------------------------------------------------------ #

class TestMoveValidationContract:
    def test_has_is_valid_field(self):
        mv = MoveValidation(is_valid=True, reason="ok")
        assert mv.is_valid is True

    def test_has_reason_field(self):
        mv = MoveValidation(is_valid=False, reason="outside_board")
        assert mv.reason == "outside_board"

    def test_is_immutable(self):
        mv = MoveValidation(is_valid=True, reason="ok")
        with pytest.raises((AttributeError, TypeError)):
            mv.is_valid = False

    def test_reason_immutable(self):
        mv = MoveValidation(is_valid=True, reason="ok")
        with pytest.raises((AttributeError, TypeError)):
            mv.reason = "tampered"


# ------------------------------------------------------------------ #
# Guard 1 — outside_board                                            #
# ------------------------------------------------------------------ #

class TestOutsideBoard:
    def test_source_off_board_returns_outside_board(self, engine):
        board = _parse(["wR ."])
        result = engine.validate_move(board, Position(-1, 0), Position(0, 1))
        assert result.is_valid is False
        assert result.reason == "outside_board"

    def test_destination_off_board_returns_outside_board(self, engine):
        board = _parse(["wR ."])
        result = engine.validate_move(board, Position(0, 0), Position(0, 99))
        assert result.is_valid is False
        assert result.reason == "outside_board"

    def test_both_off_board_returns_outside_board(self, engine):
        board = _parse(["wR ."])
        result = engine.validate_move(board, Position(99, 0), Position(0, 99))
        assert result.is_valid is False
        assert result.reason == "outside_board"

    def test_negative_destination_row_returns_outside_board(self, engine):
        board = _parse(["wR ."])
        result = engine.validate_move(board, Position(0, 0), Position(-1, 0))
        assert result.is_valid is False
        assert result.reason == "outside_board"


# ------------------------------------------------------------------ #
# Guard 2 — empty_source                                             #
# ------------------------------------------------------------------ #

class TestEmptySource:
    def test_empty_source_cell_returns_empty_source(self, engine):
        board = _parse([". . wK"])
        result = engine.validate_move(board, Position(0, 0), Position(0, 2))
        assert result.is_valid is False
        assert result.reason == "empty_source"

    def test_empty_source_takes_priority_over_illegal_move(self, engine):
        """empty_source must be reported before illegal_piece_move."""
        board = _parse([". . ."])
        result = engine.validate_move(board, Position(0, 0), Position(0, 2))
        assert result.reason == "empty_source"


# ------------------------------------------------------------------ #
# Guard 3 — friendly_destination                                     #
# ------------------------------------------------------------------ #

class TestFriendlyDestination:
    def test_white_to_white_returns_friendly_destination(self, engine):
        board = _parse(["wR wB"])
        result = engine.validate_move(board, Position(0, 0), Position(0, 1))
        assert result.is_valid is False
        assert result.reason == "friendly_destination"

    def test_black_to_black_returns_friendly_destination(self, engine):
        board = _parse(["bR bB"])
        result = engine.validate_move(board, Position(0, 0), Position(0, 1))
        assert result.is_valid is False
        assert result.reason == "friendly_destination"

    def test_friendly_destination_before_illegal_piece_move(self, engine):
        """friendly_destination must be reported before illegal_piece_move."""
        board = _parse([". . .", "wR . wB", ". . ."])
        # wR at (1,0) → (1,2) is geometrically valid for a rook,
        # but (1,2) holds a friendly — friendly_destination wins.
        result = engine.validate_move(board, Position(1, 0), Position(1, 2))
        assert result.reason == "friendly_destination"


# ------------------------------------------------------------------ #
# Guard 4 — illegal_piece_move                                       #
# ------------------------------------------------------------------ #

class TestIllegalPieceMove:
    def test_rook_diagonal_is_illegal(self, engine):
        board = _parse([
            "wR . .",
            ". . .",
            ". . .",
        ])
        result = engine.validate_move(board, Position(0, 0), Position(2, 2))
        assert result.is_valid is False
        assert result.reason == "illegal_piece_move"

    def test_bishop_straight_is_illegal(self, engine):
        board = _parse([
            "wB . .",
            ". . .",
            ". . .",
        ])
        result = engine.validate_move(board, Position(0, 0), Position(0, 2))
        assert result.is_valid is False
        assert result.reason == "illegal_piece_move"

    def test_knight_non_l_shape_is_illegal(self, engine):
        board = _parse([
            "wN . . .",
            ". . . .",
            ". . . .",
        ])
        result = engine.validate_move(board, Position(0, 0), Position(0, 2))
        assert result.is_valid is False
        assert result.reason == "illegal_piece_move"

    def test_king_two_step_is_illegal(self, engine):
        board = _parse([
            "wK . .",
            ". . .",
            ". . .",
        ])
        result = engine.validate_move(board, Position(0, 0), Position(0, 2))
        assert result.is_valid is False
        assert result.reason == "illegal_piece_move"

    def test_pawn_backward_is_illegal(self, engine):
        board = _parse([
            ". .",
            ". .",
            "wP .",
            ". .",
        ])
        result = engine.validate_move(board, Position(2, 0), Position(3, 0))
        assert result.is_valid is False
        assert result.reason == "illegal_piece_move"

    def test_rook_blocked_by_friendly_is_illegal(self, engine):
        board = _parse([
            "wR wP . .",
        ])
        result = engine.validate_move(board, Position(0, 0), Position(0, 3))
        assert result.is_valid is False
        assert result.reason == "illegal_piece_move"


# ------------------------------------------------------------------ #
# Valid moves — reason "ok"                                          #
# ------------------------------------------------------------------ #

class TestValidMove:
    def test_rook_straight_move_is_ok(self, engine):
        board = _parse(["wR . . ."])
        result = engine.validate_move(board, Position(0, 0), Position(0, 3))
        assert result.is_valid is True
        assert result.reason == "ok"

    def test_bishop_diagonal_move_is_ok(self, engine):
        board = _parse([
            "wB . . .",
            ". . . .",
            ". . . .",
            ". . . .",
        ])
        result = engine.validate_move(board, Position(0, 0), Position(3, 3))
        assert result.is_valid is True
        assert result.reason == "ok"

    def test_knight_l_shape_is_ok(self, engine):
        board = _parse([
            "wN . . .",
            ". . . .",
            ". . . .",
        ])
        result = engine.validate_move(board, Position(0, 0), Position(2, 1))
        assert result.is_valid is True
        assert result.reason == "ok"

    def test_king_one_step_is_ok(self, engine):
        board = _parse([
            "wK . .",
            ". . .",
        ])
        result = engine.validate_move(board, Position(0, 0), Position(1, 1))
        assert result.is_valid is True
        assert result.reason == "ok"

    def test_pawn_forward_is_ok(self, engine):
        board = _parse([
            ". .",
            ". .",
            "wP .",
            ". .",
        ])
        result = engine.validate_move(board, Position(2, 0), Position(1, 0))
        assert result.is_valid is True
        assert result.reason == "ok"

    def test_rook_captures_enemy_is_ok(self, engine):
        board = _parse(["wR . bR"])
        result = engine.validate_move(board, Position(0, 0), Position(0, 2))
        assert result.is_valid is True
        assert result.reason == "ok"

    def test_queen_diagonal_capture_is_ok(self, engine):
        board = _parse([
            "wQ . . .",
            ". . . .",
            ". . bP .",
            ". . . .",
        ])
        result = engine.validate_move(board, Position(0, 0), Position(2, 2))
        assert result.is_valid is True
        assert result.reason == "ok"


# ------------------------------------------------------------------ #
# Board immutability — RuleEngine must never mutate the board        #
# ------------------------------------------------------------------ #

class TestBoardImmutability:
    def test_validate_move_does_not_mutate_board(self, engine):
        board = _parse(["wR . . bR"])
        token_before = board.get(Position(0, 0))
        engine.validate_move(board, Position(0, 0), Position(0, 3))
        assert board.get(Position(0, 0)) == token_before
        assert board.get(Position(0, 3)) == "bR"
