"""
Isolated unit tests for the pure Model layer.

Covers:
  - Position: value semantics, equality, hashing, immutability
  - PieceState: enum membership, exactly three values
  - Piece: token storage, default state, lifecycle transitions, no extra attrs
  - Board: construction, get/set, boundary guard, dimensions, overwrite
"""
import pytest
from model.position import Position
from model.piece import Piece, PieceState
from model.board import Board


# ------------------------------------------------------------------ #
# Position                                                            #
# ------------------------------------------------------------------ #

class TestPosition:
    def test_stores_row_and_col(self):
        p = Position(2, 5)
        assert p.row == 2
        assert p.col == 5

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


# ------------------------------------------------------------------ #
# PieceState                                                          #
# ------------------------------------------------------------------ #

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


# ------------------------------------------------------------------ #
# Piece                                                               #
# ------------------------------------------------------------------ #

class TestPiece:
    def test_default_state_is_idle(self):
        p = Piece("wR")
        assert p.state == PieceState.IDLE

    def test_token_stored(self):
        p = Piece("bK")
        assert p.token == "bK"

    def test_state_can_be_set_to_moving(self):
        p = Piece("wB")
        p.state = PieceState.MOVING
        assert p.state == PieceState.MOVING

    def test_state_can_be_set_to_captured(self):
        p = Piece("bQ")
        p.state = PieceState.CAPTURED
        assert p.state == PieceState.CAPTURED

    def test_state_does_not_hold_path(self):
        p = Piece("wN")
        assert not hasattr(p, "path")

    def test_state_does_not_hold_destination(self):
        p = Piece("wN")
        assert not hasattr(p, "destination")

    def test_state_does_not_hold_speed(self):
        p = Piece("wN")
        assert not hasattr(p, "speed")


# ------------------------------------------------------------------ #
# Board                                                               #
# ------------------------------------------------------------------ #

class TestBoard:
    def _make_board(self):
        """2-row × 3-col board, all cells initialised to '.'."""
        return Board(rows=2, cols=3)

    def test_dimensions(self):
        b = self._make_board()
        assert b.rows == 2
        assert b.cols == 3

    def test_initial_cells_are_empty(self):
        b = self._make_board()
        for r in range(2):
            for c in range(3):
                assert b.get(Position(r, c)) == "."

    def test_set_and_get_token(self):
        b = self._make_board()
        b.set(Position(0, 1), "wR")
        assert b.get(Position(0, 1)) == "wR"

    def test_set_does_not_affect_other_cells(self):
        b = self._make_board()
        b.set(Position(0, 0), "bK")
        assert b.get(Position(0, 1)) == "."

    def test_is_inside_valid(self):
        b = self._make_board()
        assert b.is_inside(Position(0, 0)) is True
        assert b.is_inside(Position(1, 2)) is True

    def test_is_inside_out_of_bounds_row(self):
        b = self._make_board()
        assert b.is_inside(Position(2, 0)) is False

    def test_is_inside_out_of_bounds_col(self):
        b = self._make_board()
        assert b.is_inside(Position(0, 3)) is False

    def test_is_inside_negative(self):
        b = self._make_board()
        assert b.is_inside(Position(-1, 0)) is False

    def test_get_outside_raises(self):
        b = self._make_board()
        with pytest.raises((IndexError, ValueError)):
            b.get(Position(99, 99))

    def test_set_outside_raises(self):
        b = self._make_board()
        with pytest.raises((IndexError, ValueError)):
            b.set(Position(99, 99), "wR")

    def test_overwrite_token(self):
        b = self._make_board()
        b.set(Position(1, 1), "wK")
        b.set(Position(1, 1), "bK")
        assert b.get(Position(1, 1)) == "bK"
