import pytest
from unittest.mock import MagicMock
from chess_engine.model.board import Board
from chess_engine.model.position import Position
from chess_engine.rules.engine import MoveValidation
from chess_engine.input.board_mapper import BoardMapper
from chess_engine.input.controller import Controller


def _board(lines):
    tokens = [line.split() for line in lines if line.strip()]
    rows, cols = len(tokens), len(tokens[0])
    board = Board(rows=rows, cols=cols)
    for r, row in enumerate(tokens):
        for c, tok in enumerate(row):
            if tok != ".":
                board.set(Position(r, c), tok)
    return board


def _make(lines):
    board = _board(lines)
    mapper = BoardMapper(board)
    engine = MagicMock()
    ctrl = Controller(engine, mapper, board)
    return ctrl, engine


class TestFirstClickNoSelection:
    def test_click_outside_board_leaves_selection_none(self):
        ctrl, _ = _make(["wR ."])
        ctrl.click(9999, 9999)
        assert ctrl.selected_cell is None

    def test_click_on_empty_cell_leaves_selection_none(self):
        ctrl, _ = _make(["wR ."])
        ctrl.click(150, 0)
        assert ctrl.selected_cell is None

    def test_click_on_piece_sets_selection(self):
        ctrl, _ = _make(["wR ."])
        ctrl.click(50, 0)
        assert ctrl.selected_cell == Position(0, 0)

    def test_click_on_piece_does_not_call_request_move(self):
        ctrl, engine = _make(["wR ."])
        ctrl.click(50, 0)
        engine.request_move.assert_not_called()

    def test_click_on_black_piece_sets_selection(self):
        ctrl, _ = _make(["bK ."])
        ctrl.click(50, 0)
        assert ctrl.selected_cell == Position(0, 0)

    def test_click_on_piece_second_row(self):
        ctrl, _ = _make(["wR .", ". bK"])
        ctrl.click(150, 100)
        assert ctrl.selected_cell == Position(1, 1)

    def test_no_request_move_on_first_click_outside(self):
        ctrl, engine = _make(["wR ."])
        ctrl.click(9999, 0)
        engine.request_move.assert_not_called()

    def test_no_request_move_on_first_click_empty(self):
        ctrl, engine = _make(["wR ."])
        ctrl.click(150, 0)
        engine.request_move.assert_not_called()


class TestSecondClickOutsideBoard:
    def test_clears_selection(self):
        ctrl, _ = _make(["wR ."])
        ctrl.click(50, 0)
        ctrl.click(9999, 9999)
        assert ctrl.selected_cell is None

    def test_does_not_call_request_move(self):
        ctrl, engine = _make(["wR ."])
        ctrl.click(50, 0)
        ctrl.click(9999, 9999)
        engine.request_move.assert_not_called()

    def test_negative_pixel_clears_selection(self):
        ctrl, engine = _make(["wR ."])
        ctrl.click(50, 0)
        ctrl.click(-1, -1)
        assert ctrl.selected_cell is None
        engine.request_move.assert_not_called()

    def test_x_out_y_in_clears_selection(self):
        ctrl, engine = _make(["wR ."])
        ctrl.click(50, 0)
        ctrl.click(9999, 0)
        assert ctrl.selected_cell is None
        engine.request_move.assert_not_called()


class TestSecondClickInsideBoard:
    def test_calls_request_move_with_correct_positions(self):
        ctrl, engine = _make(["wR . ."])
        ctrl.click(50, 0)
        ctrl.click(250, 0)
        engine.request_move.assert_called_once_with(
            source=Position(0, 0), destination=Position(0, 2))

    def test_clears_selection_after_second_click(self):
        ctrl, _ = _make(["wR . ."])
        ctrl.click(50, 0)
        ctrl.click(250, 0)
        assert ctrl.selected_cell is None

    def test_request_move_called_even_when_destination_is_empty(self):
        ctrl, engine = _make(["wR . ."])
        ctrl.click(50, 0)
        ctrl.click(150, 0)
        engine.request_move.assert_called_once_with(
            source=Position(0, 0), destination=Position(0, 1))

    def test_request_move_called_when_destination_has_enemy(self):
        ctrl, engine = _make(["wR . bK"])
        ctrl.click(50, 0)
        ctrl.click(250, 0)
        engine.request_move.assert_called_once_with(
            source=Position(0, 0), destination=Position(0, 2))

    def test_request_move_called_when_destination_has_friendly(self):
        ctrl, engine = _make(["wR wB ."])
        ctrl.click(50, 0)
        ctrl.click(150, 0)
        engine.request_move.assert_called_once_with(
            source=Position(0, 0), destination=Position(0, 1))

    def test_selection_cleared_even_if_destination_same_as_source(self):
        ctrl, _ = _make(["wR ."])
        ctrl.click(50, 0)
        ctrl.click(50, 0)
        assert ctrl.selected_cell is None

    def test_friendly_destination_swaps_selection_without_requesting_move(self):
        ctrl, engine = _make(["wR wB ."])
        engine.validate_move.return_value = MoveValidation(is_valid=False, reason="friendly_destination")
        ctrl.click(50, 0)
        ctrl.click(150, 0)
        assert ctrl.selected_cell == Position(0, 1)
        engine.request_move.assert_not_called()

    def test_request_move_source_and_destination_correct_on_multirow_board(self):
        ctrl, engine = _make(["wR . .", ". . bK"])
        ctrl.click(50, 0)
        ctrl.click(250, 100)
        engine.request_move.assert_called_once_with(
            source=Position(0, 0), destination=Position(1, 2))


class TestSequentialClicks:
    def test_two_full_moves_in_sequence(self):
        ctrl, engine = _make(["wR . . bK"])
        ctrl.click(50, 0)
        ctrl.click(150, 0)
        ctrl.click(50, 0)
        ctrl.click(350, 0)
        assert engine.request_move.call_count == 2

    def test_outside_click_resets_then_new_selection_works(self):
        ctrl, engine = _make(["wR . ."])
        ctrl.click(50, 0)
        ctrl.click(9999, 9999)
        assert ctrl.selected_cell is None
        ctrl.click(50, 0)
        assert ctrl.selected_cell == Position(0, 0)
        ctrl.click(250, 0)
        engine.request_move.assert_called_once_with(
            source=Position(0, 0), destination=Position(0, 2))

    def test_empty_first_click_then_piece_click_selects(self):
        ctrl, _ = _make(["wR . ."])
        ctrl.click(150, 0)
        assert ctrl.selected_cell is None
        ctrl.click(50, 0)
        assert ctrl.selected_cell == Position(0, 0)

    def test_request_move_not_called_after_only_one_valid_click(self):
        ctrl, engine = _make(["wR ."])
        ctrl.click(50, 0)
        engine.request_move.assert_not_called()
