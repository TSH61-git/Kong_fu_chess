"""
Isolated unit tests for the Text I/O Utilities layer.

Covers:
  - BoardParser: valid input, empty-line skipping, unknown tokens,
                 row-width mismatch, empty input
  - BoardPrinter: line count, row content, full round-trip fidelity
"""
import pytest
from text_io.board_parser import BoardParser
from text_io.board_printer import BoardPrinter
from model.position import Position


# ------------------------------------------------------------------ #
# BoardParser                                                         #
# ------------------------------------------------------------------ #

class TestBoardParser:
    def test_valid_input_produces_correct_dimensions(self):
        lines = ["wR . bK", ". wK ."]
        board = BoardParser.parse(lines)
        assert board.rows == 2
        assert board.cols == 3

    def test_valid_input_places_tokens_correctly(self):
        lines = ["wR . bK", ". wK ."]
        board = BoardParser.parse(lines)
        assert board.get(Position(0, 0)) == "wR"
        assert board.get(Position(0, 1)) == "."
        assert board.get(Position(0, 2)) == "bK"
        assert board.get(Position(1, 1)) == "wK"

    def test_empty_lines_are_skipped(self):
        lines = ["", "wK bK", "", ". ."]
        board = BoardParser.parse(lines)
        assert board.rows == 2

    def test_unknown_token_raises(self):
        with pytest.raises(ValueError):
            BoardParser.parse(["wR XX ."])

    def test_row_width_mismatch_raises(self):
        with pytest.raises(ValueError):
            BoardParser.parse(["wR . .", "wR ."])

    def test_empty_input_raises(self):
        with pytest.raises(ValueError):
            BoardParser.parse([])

    def test_all_empty_lines_raises(self):
        with pytest.raises(ValueError):
            BoardParser.parse(["", "  "])

    def test_single_cell_board(self):
        board = BoardParser.parse(["wK"])
        assert board.rows == 1
        assert board.cols == 1
        assert board.get(Position(0, 0)) == "wK"

    def test_all_standard_tokens_accepted(self):
        line = "wK bK wR bR wB bB wQ bQ wN bN wP bP ."
        board = BoardParser.parse([line])
        assert board.cols == 13

    def test_dot_only_board(self):
        board = BoardParser.parse([". . .", ". . ."])
        assert board.rows == 2
        assert board.cols == 3


# ------------------------------------------------------------------ #
# BoardPrinter                                                        #
# ------------------------------------------------------------------ #

class TestBoardPrinter:
    def _board_from(self, lines):
        return BoardParser.parse(lines)

    def test_print_lines_count_matches_rows(self):
        board = self._board_from(["wR . bK", ". wK ."])
        lines = BoardPrinter.to_lines(board)
        assert len(lines) == 2

    def test_print_first_row_content(self):
        board = self._board_from(["wR . bK", ". wK ."])
        lines = BoardPrinter.to_lines(board)
        assert lines[0] == "wR . bK"

    def test_print_second_row_content(self):
        board = self._board_from(["wR . bK", ". wK ."])
        lines = BoardPrinter.to_lines(board)
        assert lines[1] == ". wK ."

    def test_roundtrip_fidelity(self):
        original = ["wR bR wB bB", "wQ bQ wK bK"]
        board = self._board_from(original)
        assert BoardPrinter.to_lines(board) == original

    def test_single_row_roundtrip(self):
        original = ["wK . bK"]
        board = self._board_from(original)
        assert BoardPrinter.to_lines(board) == original

    def test_all_dots_roundtrip(self):
        original = [". . .", ". . ."]
        board = self._board_from(original)
        assert BoardPrinter.to_lines(board) == original
