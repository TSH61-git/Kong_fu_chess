import pytest
from chess_engine.model.board import Board
from chess_engine.model.position import Position
from chess_engine.input.board_mapper import BoardMapper
from config import CELL_SIZE


def _board(rows, cols):
    return Board(rows=rows, cols=cols)


class TestCellSizeConstant:
    def test_cell_size_is_100(self):
        assert CELL_SIZE == 100


class TestPixelToCell:
    def test_origin_pixel_maps_to_row0_col0(self):
        assert BoardMapper(_board(4, 4)).pixel_to_cell(0, 0) == Position(0, 0)

    def test_pixel_50_50_maps_to_row0_col0(self):
        assert BoardMapper(_board(4, 4)).pixel_to_cell(50, 50) == Position(0, 0)

    def test_pixel_99_99_maps_to_row0_col0(self):
        assert BoardMapper(_board(4, 4)).pixel_to_cell(99, 99) == Position(0, 0)

    def test_pixel_100_0_maps_to_row0_col1(self):
        assert BoardMapper(_board(4, 4)).pixel_to_cell(100, 0) == Position(0, 1)

    def test_pixel_0_100_maps_to_row1_col0(self):
        assert BoardMapper(_board(4, 4)).pixel_to_cell(0, 100) == Position(1, 0)

    def test_pixel_250_350_maps_to_row3_col2(self):
        assert BoardMapper(_board(8, 8)).pixel_to_cell(250, 350) == Position(3, 2)

    def test_pixel_maps_col_from_x_and_row_from_y(self):
        assert BoardMapper(_board(4, 4)).pixel_to_cell(200, 100) == Position(1, 2)


class TestBoundaryAccepted:
    def test_last_valid_col_pixel_accepted(self):
        assert BoardMapper(_board(4, 4)).pixel_to_cell(300, 0) == Position(0, 3)

    def test_last_valid_row_pixel_accepted(self):
        assert BoardMapper(_board(4, 4)).pixel_to_cell(0, 300) == Position(3, 0)

    def test_last_cell_corner_pixel_accepted(self):
        assert BoardMapper(_board(4, 4)).pixel_to_cell(300, 300) == Position(3, 3)

    def test_last_pixel_inside_last_cell_accepted(self):
        assert BoardMapper(_board(4, 4)).pixel_to_cell(399, 399) == Position(3, 3)


class TestOutOfBoundsReturnsNone:
    def test_x_exactly_at_board_width_returns_none(self):
        assert BoardMapper(_board(4, 4)).pixel_to_cell(400, 0) is None

    def test_y_exactly_at_board_height_returns_none(self):
        assert BoardMapper(_board(4, 4)).pixel_to_cell(0, 400) is None

    def test_negative_x_returns_none(self):
        assert BoardMapper(_board(4, 4)).pixel_to_cell(-1, 0) is None

    def test_negative_y_returns_none(self):
        assert BoardMapper(_board(4, 4)).pixel_to_cell(0, -1) is None

    def test_both_negative_returns_none(self):
        assert BoardMapper(_board(4, 4)).pixel_to_cell(-50, -50) is None

    def test_far_outside_returns_none(self):
        assert BoardMapper(_board(4, 4)).pixel_to_cell(9999, 9999) is None

    def test_x_in_bounds_y_out_of_bounds_returns_none(self):
        assert BoardMapper(_board(4, 4)).pixel_to_cell(50, 400) is None

    def test_x_out_of_bounds_y_in_bounds_returns_none(self):
        assert BoardMapper(_board(4, 4)).pixel_to_cell(400, 50) is None


class TestBoardMapperImmutability:
    def test_pixel_to_cell_does_not_mutate_board(self):
        board = _board(4, 4)
        board.set(Position(0, 0), "wR")
        BoardMapper(board).pixel_to_cell(50, 50)
        assert board.get(Position(0, 0)) == "wR"

    def test_out_of_bounds_call_does_not_mutate_board(self):
        board = _board(4, 4)
        board.set(Position(3, 3), "bK")
        BoardMapper(board).pixel_to_cell(9999, 9999)
        assert board.get(Position(3, 3)) == "bK"
