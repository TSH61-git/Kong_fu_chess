import pytest
from chess_engine.model.position import Position
from chess_engine.model.piece import Piece, PieceType, Color
from chess_engine.rules.engine import RuleEngine, MoveValidation
from app_gateways.text_cli.translator import board_from_token_lines as _parse


@pytest.fixture
def engine():
    return RuleEngine()


class TestMoveValidationContract:
    def test_has_is_valid_field(self):
        assert MoveValidation(is_valid=True, reason="ok").is_valid is True

    def test_has_reason_field(self):
        assert MoveValidation(is_valid=False, reason="outside_board").reason == "outside_board"

    def test_is_immutable(self):
        mv = MoveValidation(is_valid=True, reason="ok")
        with pytest.raises((AttributeError, TypeError)):
            mv.is_valid = False

    def test_reason_immutable(self):
        mv = MoveValidation(is_valid=True, reason="ok")
        with pytest.raises((AttributeError, TypeError)):
            mv.reason = "tampered"


class TestOutsideBoard:
    def test_source_off_board(self, engine):
        board = _parse(["wR ."])
        assert engine.validate_move(board, Position(-1, 0), Position(0, 1)).reason == "outside_board"

    def test_destination_off_board(self, engine):
        board = _parse(["wR ."])
        assert engine.validate_move(board, Position(0, 0), Position(0, 99)).reason == "outside_board"

    def test_both_off_board(self, engine):
        board = _parse(["wR ."])
        assert engine.validate_move(board, Position(99, 0), Position(0, 99)).reason == "outside_board"

    def test_negative_destination_row(self, engine):
        board = _parse(["wR ."])
        assert engine.validate_move(board, Position(0, 0), Position(-1, 0)).reason == "outside_board"


class TestEmptySource:
    def test_empty_source_cell(self, engine):
        board = _parse([". . wK"])
        assert engine.validate_move(board, Position(0, 0), Position(0, 2)).reason == "empty_source"

    def test_empty_source_priority(self, engine):
        board = _parse([". . ."])
        assert engine.validate_move(board, Position(0, 0), Position(0, 2)).reason == "empty_source"


class TestFriendlyDestination:
    def test_white_to_white(self, engine):
        board = _parse(["wR wB"])
        assert engine.validate_move(board, Position(0, 0), Position(0, 1)).reason == "friendly_destination"

    def test_black_to_black(self, engine):
        board = _parse(["bR bB"])
        assert engine.validate_move(board, Position(0, 0), Position(0, 1)).reason == "friendly_destination"

    def test_friendly_before_illegal_move(self, engine):
        board = _parse([". . .", "wR . wB", ". . ."])
        assert engine.validate_move(board, Position(1, 0), Position(1, 2)).reason == "friendly_destination"


class TestIllegalPieceMove:
    def test_rook_diagonal_is_illegal(self, engine):
        board = _parse(["wR . .", ". . .", ". . ."])
        assert engine.validate_move(board, Position(0, 0), Position(2, 2)).reason == "illegal_piece_move"

    def test_bishop_straight_is_illegal(self, engine):
        board = _parse(["wB . .", ". . .", ". . ."])
        assert engine.validate_move(board, Position(0, 0), Position(0, 2)).reason == "illegal_piece_move"

    def test_knight_non_l_shape_is_illegal(self, engine):
        board = _parse(["wN . . .", ". . . .", ". . . ."])
        assert engine.validate_move(board, Position(0, 0), Position(0, 2)).reason == "illegal_piece_move"

    def test_king_two_step_is_illegal(self, engine):
        board = _parse(["wK . .", ". . .", ". . ."])
        assert engine.validate_move(board, Position(0, 0), Position(0, 2)).reason == "illegal_piece_move"

    def test_pawn_backward_is_illegal(self, engine):
        board = _parse([". .", ". .", "wP .", ". ."])
        assert engine.validate_move(board, Position(2, 0), Position(3, 0)).reason == "illegal_piece_move"

    def test_rook_blocked_by_friendly_is_illegal(self, engine):
        board = _parse(["wR wP . ."])
        assert engine.validate_move(board, Position(0, 0), Position(0, 3)).reason == "illegal_piece_move"


class TestValidMove:
    def test_rook_straight_move_is_ok(self, engine):
        board = _parse(["wR . . ."])
        r = engine.validate_move(board, Position(0, 0), Position(0, 3))
        assert r.is_valid is True and r.reason == "ok"

    def test_bishop_diagonal_move_is_ok(self, engine):
        board = _parse(["wB . . .", ". . . .", ". . . .", ". . . ."])
        r = engine.validate_move(board, Position(0, 0), Position(3, 3))
        assert r.is_valid is True and r.reason == "ok"

    def test_knight_l_shape_is_ok(self, engine):
        board = _parse(["wN . . .", ". . . .", ". . . ."])
        r = engine.validate_move(board, Position(0, 0), Position(2, 1))
        assert r.is_valid is True and r.reason == "ok"

    def test_king_one_step_is_ok(self, engine):
        board = _parse(["wK . .", ". . ."])
        r = engine.validate_move(board, Position(0, 0), Position(1, 1))
        assert r.is_valid is True and r.reason == "ok"

    def test_pawn_forward_is_ok(self, engine):
        board = _parse([". .", ". .", "wP .", ". ."])
        r = engine.validate_move(board, Position(2, 0), Position(1, 0))
        assert r.is_valid is True and r.reason == "ok"

    def test_rook_captures_enemy_is_ok(self, engine):
        board = _parse(["wR . bR"])
        r = engine.validate_move(board, Position(0, 0), Position(0, 2))
        assert r.is_valid is True and r.reason == "ok"

    def test_queen_diagonal_capture_is_ok(self, engine):
        board = _parse(["wQ . . .", ". . . .", ". . bP .", ". . . ."])
        r = engine.validate_move(board, Position(0, 0), Position(2, 2))
        assert r.is_valid is True and r.reason == "ok"


class TestBoardImmutability:
    def test_validate_move_does_not_mutate_board(self, engine):
        board = _parse(["wR . . bR"])
        wr = board.get(Position(0, 0))
        br = board.get(Position(0, 3))
        engine.validate_move(board, Position(0, 0), Position(0, 3))
        assert board.get(Position(0, 0)) == wr
        assert board.get(Position(0, 3)) == br
