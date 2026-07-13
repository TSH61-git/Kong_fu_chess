import pytest
from chess_engine.model.position import Position
from chess_engine.model.piece import Piece, PieceType, Color, PieceState
from chess_engine.model.board import Board


class TestPosition:
    def test_stores_row_and_col(self):
        p = Position(2, 5)
        assert p.row == 2 and p.col == 5

    def test_equality_by_value(self):
        assert Position(1, 3) == Position(1, 3)

    def test_inequality(self):
        assert Position(1, 3) != Position(1, 4)

    def test_hashable_usable_in_set(self):
        s = {Position(0, 0), Position(0, 0), Position(1, 1)}
        assert len(s) == 2

    def test_hashable_usable_as_dict_key(self):
        d = {Position(0, 0): "a", Position(1, 1): "b"}
        assert d[Position(0, 0)] == "a"

    def test_immutable_row(self):
        p = Position(1, 2)
        with pytest.raises((AttributeError, TypeError)):
            p.row = 99

    def test_immutable_col(self):
        p = Position(1, 2)
        with pytest.raises((AttributeError, TypeError)):
            p.col = 99

    def test_repr_contains_row_and_col(self):
        r = repr(Position(3, 7))
        assert "3" in r and "7" in r


class TestPieceType:
    def test_all_six_types_exist(self):
        assert PieceType.KING and PieceType.QUEEN and PieceType.ROOK
        assert PieceType.BISHOP and PieceType.KNIGHT and PieceType.PAWN

    def test_exactly_six_members(self):
        assert len(PieceType) == 6

    def test_members_are_distinct(self):
        types = list(PieceType)
        assert len(set(types)) == 6


class TestColor:
    def test_white_and_black_exist(self):
        assert Color.WHITE and Color.BLACK

    def test_exactly_two_members(self):
        assert len(Color) == 2

    def test_members_are_distinct(self):
        assert Color.WHITE != Color.BLACK


class TestPieceState:
    def test_has_idle(self):
        assert PieceState.IDLE is not None

    def test_has_moving(self):
        assert PieceState.MOVING is not None

    def test_has_captured(self):
        assert PieceState.CAPTURED is not None

    def test_exactly_three_members(self):
        assert len(PieceState) == 3

    def test_members_are_distinct(self):
        assert PieceState.IDLE != PieceState.MOVING
        assert PieceState.MOVING != PieceState.CAPTURED
        assert PieceState.IDLE != PieceState.CAPTURED


class TestPiece:
    def test_stores_piece_type_and_color(self):
        p = Piece(PieceType.ROOK, Color.WHITE)
        assert p.piece_type == PieceType.ROOK
        assert p.color == Color.WHITE

    def test_default_state_is_idle(self):
        p = Piece(PieceType.KING, Color.BLACK)
        assert p.state == PieceState.IDLE

    def test_state_can_be_set_to_moving(self):
        p = Piece(PieceType.BISHOP, Color.WHITE)
        p.state = PieceState.MOVING
        assert p.state == PieceState.MOVING

    def test_state_can_be_set_to_captured(self):
        p = Piece(PieceType.QUEEN, Color.BLACK)
        p.state = PieceState.CAPTURED
        assert p.state == PieceState.CAPTURED

    def test_equality_by_type_and_color(self):
        assert Piece(PieceType.ROOK, Color.WHITE) == Piece(PieceType.ROOK, Color.WHITE)

    def test_inequality_different_type(self):
        assert Piece(PieceType.ROOK, Color.WHITE) != Piece(PieceType.BISHOP, Color.WHITE)

    def test_inequality_different_color(self):
        assert Piece(PieceType.ROOK, Color.WHITE) != Piece(PieceType.ROOK, Color.BLACK)

    def test_no_raw_token_attribute(self):
        p = Piece(PieceType.KNIGHT, Color.WHITE)
        assert not hasattr(p, "token")


class TestBoard:
    def _make(self):
        return Board(rows=2, cols=3)

    def test_dimensions(self):
        b = self._make()
        assert b.rows == 2 and b.cols == 3

    def test_initial_cells_are_none(self):
        b = self._make()
        for r in range(2):
            for c in range(3):
                assert b.get(Position(r, c)) is None

    def test_set_and_get_piece(self):
        b = self._make()
        p = Piece(PieceType.ROOK, Color.WHITE)
        b.set(Position(0, 1), p)
        assert b.get(Position(0, 1)) == p

    def test_set_none_clears_cell(self):
        b = self._make()
        b.set(Position(0, 0), Piece(PieceType.KING, Color.BLACK))
        b.set(Position(0, 0), None)
        assert b.get(Position(0, 0)) is None

    def test_set_does_not_affect_other_cells(self):
        b = self._make()
        b.set(Position(0, 0), Piece(PieceType.KING, Color.BLACK))
        assert b.get(Position(0, 1)) is None

    def test_is_inside_valid(self):
        b = self._make()
        assert b.is_inside(Position(0, 0)) is True
        assert b.is_inside(Position(1, 2)) is True

    def test_is_inside_out_of_bounds(self):
        b = self._make()
        assert b.is_inside(Position(2, 0)) is False
        assert b.is_inside(Position(0, 3)) is False
        assert b.is_inside(Position(-1, 0)) is False

    def test_get_outside_raises(self):
        b = self._make()
        with pytest.raises((IndexError, ValueError)):
            b.get(Position(99, 99))

    def test_set_outside_raises(self):
        b = self._make()
        with pytest.raises((IndexError, ValueError)):
            b.set(Position(99, 99), None)

    def test_overwrite_piece(self):
        b = self._make()
        b.set(Position(1, 1), Piece(PieceType.KING, Color.WHITE))
        b.set(Position(1, 1), Piece(PieceType.KING, Color.BLACK))
        assert b.get(Position(1, 1)) == Piece(PieceType.KING, Color.BLACK)
