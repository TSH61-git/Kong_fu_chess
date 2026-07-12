"""
Unit tests for input/controller.py — Controller two-click selection state machine.

Tests verify the exact policy specified in the architecture:

First-click phase (no selection active):
  - Click outside board  → ignore, selection stays None
  - Click on empty cell  → ignore, selection stays None
  - Click on a piece     → selection set to that Position

Second-click phase (selection active):
  - Click outside board  → clear selection, request_move NOT called
  - Click inside board   → request_move(source, destination) called with
                           exact positions, selection cleared immediately
  - request_move is ALWAYS called on any valid second in-board click,
    regardless of whether the destination is empty or occupied

Invariants:
  - selection is always None after any second click (inside or outside)
  - Controller never calls Board.set or evaluates chess rules
  - request_move call arguments are verified precisely

All tests are written BEFORE the implementation exists (TDD red phase).
"""
import pytest
from unittest.mock import MagicMock, call
from text_io.board_parser import BoardParser
from model.position import Position
from input.board_mapper import BoardMapper
from input.controller import Controller
from rules.rule_engine import MoveValidation


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _board(lines):
    return BoardParser.parse(lines)


def _make(lines):
    """
    Build a (controller, mock_engine) pair from board text lines.
    The mock engine records all request_move calls.
    """
    board = _board(lines)
    mapper = BoardMapper(board)
    engine = MagicMock()
    ctrl = Controller(engine, mapper, board)
    return ctrl, engine


# ------------------------------------------------------------------ #
# First click — no selection active                                   #
# ------------------------------------------------------------------ #

class TestFirstClickNoSelection:
    def test_click_outside_board_leaves_selection_none(self):
        ctrl, engine = _make(["wR ."])
        ctrl.click(9999, 9999)
        assert ctrl.selected_cell is None

    def test_click_on_empty_cell_leaves_selection_none(self):
        ctrl, engine = _make(["wR ."])
        ctrl.click(150, 0)   # col=1 → '.'
        assert ctrl.selected_cell is None

    def test_click_on_piece_sets_selection(self):
        ctrl, engine = _make(["wR ."])
        ctrl.click(50, 0)    # col=0 → 'wR'
        assert ctrl.selected_cell == Position(0, 0)

    def test_click_on_piece_does_not_call_request_move(self):
        ctrl, engine = _make(["wR ."])
        ctrl.click(50, 0)
        engine.request_move.assert_not_called()

    def test_click_on_black_piece_sets_selection(self):
        ctrl, engine = _make(["bK ."])
        ctrl.click(50, 0)
        assert ctrl.selected_cell == Position(0, 0)

    def test_click_on_piece_second_row(self):
        ctrl, engine = _make(["wR .", ". bK"])
        ctrl.click(150, 100)   # x=150→col=1, y=100→row=1 → 'bK'
        assert ctrl.selected_cell == Position(1, 1)

    def test_no_request_move_on_first_click_outside(self):
        ctrl, engine = _make(["wR ."])
        ctrl.click(9999, 0)
        engine.request_move.assert_not_called()

    def test_no_request_move_on_first_click_empty(self):
        ctrl, engine = _make(["wR ."])
        ctrl.click(150, 0)
        engine.request_move.assert_not_called()


# ------------------------------------------------------------------ #
# Second click — selection active, click outside board               #
# ------------------------------------------------------------------ #

class TestSecondClickOutsideBoard:
    def test_clears_selection(self):
        ctrl, engine = _make(["wR ."])
        ctrl.click(50, 0)          # select wR at (0,0)
        ctrl.click(9999, 9999)     # second click outside
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


# ------------------------------------------------------------------ #
# Second click — selection active, click inside board                #
# ------------------------------------------------------------------ #

class TestSecondClickInsideBoard:
    def test_calls_request_move_with_correct_positions(self):
        ctrl, engine = _make(["wR . ."])
        ctrl.click(50, 0)      # select (0,0)
        ctrl.click(250, 0)     # target (0,2)
        engine.request_move.assert_called_once_with(
            source=Position(0, 0),
            destination=Position(0, 2),
        )

    def test_clears_selection_after_second_click(self):
        ctrl, engine = _make(["wR . ."])
        ctrl.click(50, 0)
        ctrl.click(250, 0)
        assert ctrl.selected_cell is None

    def test_request_move_called_even_when_destination_is_empty(self):
        """Controller does not evaluate legality — it always forwards the intent."""
        ctrl, engine = _make(["wR . ."])
        ctrl.click(50, 0)
        ctrl.click(150, 0)     # empty cell at (0,1)
        engine.request_move.assert_called_once_with(
            source=Position(0, 0),
            destination=Position(0, 1),
        )

    def test_request_move_called_when_destination_has_enemy(self):
        ctrl, engine = _make(["wR . bK"])
        ctrl.click(50, 0)
        ctrl.click(250, 0)
        engine.request_move.assert_called_once_with(
            source=Position(0, 0),
            destination=Position(0, 2),
        )

    def test_request_move_called_when_destination_has_friendly(self):
        """Controller does not enforce friendly-fire rules — engine does."""
        ctrl, engine = _make(["wR wB ."])
        ctrl.click(50, 0)
        ctrl.click(150, 0)
        engine.request_move.assert_called_once_with(
            source=Position(0, 0),
            destination=Position(0, 1),
        )

    def test_selection_cleared_even_if_destination_same_as_source(self):
        ctrl, engine = _make(["wR ."])
        ctrl.click(50, 0)
        ctrl.click(50, 0)      # second click on same cell
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
        ctrl.click(50, 0)       # select wR at (0,0)
        ctrl.click(250, 100)    # target bK at (1,2)
        engine.request_move.assert_called_once_with(
            source=Position(0, 0),
            destination=Position(1, 2),
        )


# ------------------------------------------------------------------ #
# Sequential clicks — full interaction sequences                     #
# ------------------------------------------------------------------ #

class TestSequentialClicks:
    def test_two_full_moves_in_sequence(self):
        ctrl, engine = _make(["wR . . bK"])
        # First move
        ctrl.click(50, 0)
        ctrl.click(150, 0)
        # Second move — re-select and move again
        ctrl.click(50, 0)
        ctrl.click(350, 0)
        assert engine.request_move.call_count == 2
        engine.request_move.assert_any_call(
            source=Position(0, 0), destination=Position(0, 1)
        )
        engine.request_move.assert_any_call(
            source=Position(0, 0), destination=Position(0, 3)
        )

    def test_outside_click_resets_then_new_selection_works(self):
        ctrl, engine = _make(["wR . ."])
        ctrl.click(50, 0)          # select
        ctrl.click(9999, 9999)     # cancel via outside click
        assert ctrl.selected_cell is None
        ctrl.click(50, 0)          # re-select
        assert ctrl.selected_cell == Position(0, 0)
        ctrl.click(250, 0)         # move
        engine.request_move.assert_called_once_with(
            source=Position(0, 0),
            destination=Position(0, 2),
        )

    def test_empty_first_click_then_piece_click_selects(self):
        ctrl, engine = _make(["wR . ."])
        ctrl.click(150, 0)     # empty cell — ignored
        assert ctrl.selected_cell is None
        ctrl.click(50, 0)      # piece — selected
        assert ctrl.selected_cell == Position(0, 0)

    def test_request_move_not_called_after_only_one_valid_click(self):
        ctrl, engine = _make(["wR ."])
        ctrl.click(50, 0)
        engine.request_move.assert_not_called()
