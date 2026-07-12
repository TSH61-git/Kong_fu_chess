"""
Unit tests for input/board_mapper.py — BoardMapper coordinate adapter.

Tests verify:
  - Correct pixel-to-cell translation for interior clicks
  - Exact boundary cells (first and last row/col) are accepted
  - Clicks one pixel outside any edge return None
  - Negative pixel coordinates return None
  - CELL_SIZE constant is exactly 100
  - BoardMapper never mutates the Board

All tests are written BEFORE the implementation exists (TDD red phase).
"""
import pytest
from text_io.board_parser import BoardParser
from model.position import Position
from input.board_mapper import BoardMapper, CELL_SIZE


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _board(rows, cols):
    """Build an all-empty Board of given dimensions."""
    line = " ".join(["."] * cols)
    return BoardParser.parse([line] * rows)


# ------------------------------------------------------------------ #
# CELL_SIZE constant                                                  #
# ------------------------------------------------------------------ #

class TestCellSizeConstant:
    def test_cell_size_is_100(self):
        assert CELL_SIZE == 100


# ------------------------------------------------------------------ #
# Basic pixel-to-cell translation                                     #
# ------------------------------------------------------------------ #

class TestPixelToCell:
    def test_origin_pixel_maps_to_row0_col0(self):
        board = _board(4, 4)
        mapper = BoardMapper(board)
        assert mapper.pixel_to_cell(0, 0) == Position(0, 0)

    def test_pixel_50_50_maps_to_row0_col0(self):
        """Centre of the first cell still maps to (0, 0)."""
        board = _board(4, 4)
        mapper = BoardMapper(board)
        assert mapper.pixel_to_cell(50, 50) == Position(0, 0)

    def test_pixel_99_99_maps_to_row0_col0(self):
        """Last pixel of the first cell still maps to (0, 0)."""
        board = _board(4, 4)
        mapper = BoardMapper(board)
        assert mapper.pixel_to_cell(99, 99) == Position(0, 0)

    def test_pixel_100_0_maps_to_row0_col1(self):
        """First pixel of the second column."""
        board = _board(4, 4)
        mapper = BoardMapper(board)
        assert mapper.pixel_to_cell(100, 0) == Position(0, 1)

    def test_pixel_0_100_maps_to_row1_col0(self):
        """First pixel of the second row."""
        board = _board(4, 4)
        mapper = BoardMapper(board)
        assert mapper.pixel_to_cell(0, 100) == Position(1, 0)

    def test_pixel_250_350_maps_to_row3_col2(self):
        """Interior cell on a larger board."""
        board = _board(8, 8)
        mapper = BoardMapper(board)
        assert mapper.pixel_to_cell(250, 350) == Position(3, 2)

    def test_pixel_maps_col_from_x_and_row_from_y(self):
        """x drives col, y drives row — not the other way around."""
        board = _board(4, 4)
        mapper = BoardMapper(board)
        result = mapper.pixel_to_cell(200, 100)
        assert result == Position(1, 2)


# ------------------------------------------------------------------ #
# Exact boundary cells — must be accepted                            #
# ------------------------------------------------------------------ #

class TestBoundaryAccepted:
    def test_last_valid_col_pixel_accepted(self):
        """Pixel at the start of the last column on a 4-col board."""
        board = _board(4, 4)
        mapper = BoardMapper(board)
        # col 3 starts at x=300
        assert mapper.pixel_to_cell(300, 0) == Position(0, 3)

    def test_last_valid_row_pixel_accepted(self):
        """Pixel at the start of the last row on a 4-row board."""
        board = _board(4, 4)
        mapper = BoardMapper(board)
        # row 3 starts at y=300
        assert mapper.pixel_to_cell(0, 300) == Position(3, 0)

    def test_last_cell_corner_pixel_accepted(self):
        """Top-left pixel of the bottom-right cell on a 4×4 board."""
        board = _board(4, 4)
        mapper = BoardMapper(board)
        assert mapper.pixel_to_cell(300, 300) == Position(3, 3)

    def test_last_pixel_inside_last_cell_accepted(self):
        """Pixel 399,399 is still inside the 4×4 board."""
        board = _board(4, 4)
        mapper = BoardMapper(board)
        assert mapper.pixel_to_cell(399, 399) == Position(3, 3)


# ------------------------------------------------------------------ #
# Out-of-bounds clicks — must return None                            #
# ------------------------------------------------------------------ #

class TestOutOfBoundsReturnsNone:
    def test_x_exactly_at_board_width_returns_none(self):
        """x=400 on a 4-col board is one pixel past the right edge."""
        board = _board(4, 4)
        mapper = BoardMapper(board)
        assert mapper.pixel_to_cell(400, 0) is None

    def test_y_exactly_at_board_height_returns_none(self):
        """y=400 on a 4-row board is one pixel past the bottom edge."""
        board = _board(4, 4)
        mapper = BoardMapper(board)
        assert mapper.pixel_to_cell(0, 400) is None

    def test_negative_x_returns_none(self):
        board = _board(4, 4)
        mapper = BoardMapper(board)
        assert mapper.pixel_to_cell(-1, 0) is None

    def test_negative_y_returns_none(self):
        board = _board(4, 4)
        mapper = BoardMapper(board)
        assert mapper.pixel_to_cell(0, -1) is None

    def test_both_negative_returns_none(self):
        board = _board(4, 4)
        mapper = BoardMapper(board)
        assert mapper.pixel_to_cell(-50, -50) is None

    def test_far_outside_returns_none(self):
        board = _board(4, 4)
        mapper = BoardMapper(board)
        assert mapper.pixel_to_cell(9999, 9999) is None

    def test_x_in_bounds_y_out_of_bounds_returns_none(self):
        board = _board(4, 4)
        mapper = BoardMapper(board)
        assert mapper.pixel_to_cell(50, 400) is None

    def test_x_out_of_bounds_y_in_bounds_returns_none(self):
        board = _board(4, 4)
        mapper = BoardMapper(board)
        assert mapper.pixel_to_cell(400, 50) is None


# ------------------------------------------------------------------ #
# Board immutability — BoardMapper must never mutate the board       #
# ------------------------------------------------------------------ #

class TestBoardMapperImmutability:
    def test_pixel_to_cell_does_not_mutate_board(self):
        board = _board(4, 4)
        board.set(Position(0, 0), "wR")
        mapper = BoardMapper(board)
        mapper.pixel_to_cell(50, 50)
        assert board.get(Position(0, 0)) == "wR"

    def test_out_of_bounds_call_does_not_mutate_board(self):
        board = _board(4, 4)
        board.set(Position(3, 3), "bK")
        mapper = BoardMapper(board)
        mapper.pixel_to_cell(9999, 9999)
        assert board.get(Position(3, 3)) == "bK"
