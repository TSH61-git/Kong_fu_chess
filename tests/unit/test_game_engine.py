"""
Unit tests for engine/game_engine.py — GameEngine application service.

Test groups:
  MoveResult contract       — frozen dataclass fields and immutability
  GameSnapshot contract     — frozen dataclass fields, deep-copy isolation
  Guard 1: game_over        — request_move rejected before RuleEngine consulted
  Guard 2: motion_in_progress — request_move rejected before RuleEngine consulted
  Guard 3: rule validation  — invalid moves propagate RuleEngine reason verbatim
  Guard 4: valid move       — arbiter.start_motion called with correct args
  wait()                    — delegates to arbiter.advance_time, no board mutation
  snapshot()                — reflects live board state, selected_cell, game_over
  notify_king_captured()    — sets game_over flag; subsequent request_move blocked
  Board immutability        — GameEngine never mutates board inside request_move

All tests are written BEFORE the implementation exists (TDD red phase).
"""
import pytest
from unittest.mock import MagicMock, call
from text_io.board_parser import BoardParser
from model.position import Position
from rules.rule_engine import RuleEngine
from engine.game_engine import GameEngine, MoveResult, GameSnapshot


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _board(lines):
    return BoardParser.parse(lines)


def _mock_arbiter(has_active=False):
    """Return a mock IRealTimeArbiter with configurable has_active_motion."""
    arbiter = MagicMock()
    arbiter.has_active_motion.return_value = has_active
    arbiter.is_in_cooldown.return_value = False
    return arbiter


def _engine(lines, has_active=False):
    """Build a (GameEngine, mock_arbiter) pair from board text lines."""
    board = _board(lines)
    rule_engine = RuleEngine()
    arbiter = _mock_arbiter(has_active)
    engine = GameEngine(board=board, rule_engine=rule_engine, arbiter=arbiter)
    return engine, arbiter


# ------------------------------------------------------------------ #
# MoveResult contract                                                 #
# ------------------------------------------------------------------ #

class TestMoveResultContract:
    def test_has_is_accepted_field(self):
        mr = MoveResult(is_accepted=True, reason="ok")
        assert mr.is_accepted is True

    def test_has_reason_field(self):
        mr = MoveResult(is_accepted=False, reason="game_over")
        assert mr.reason == "game_over"

    def test_is_immutable_is_accepted(self):
        mr = MoveResult(is_accepted=True, reason="ok")
        with pytest.raises((AttributeError, TypeError)):
            mr.is_accepted = False

    def test_is_immutable_reason(self):
        mr = MoveResult(is_accepted=True, reason="ok")
        with pytest.raises((AttributeError, TypeError)):
            mr.reason = "tampered"


# ------------------------------------------------------------------ #
# GameSnapshot contract                                               #
# ------------------------------------------------------------------ #

class TestGameSnapshotContract:
    def test_has_board_width(self):
        engine, _ = _engine(["wR . bK"])
        snap = engine.snapshot()
        assert snap.board_width == 3

    def test_has_board_height(self):
        engine, _ = _engine(["wR . bK", ". . ."])
        snap = engine.snapshot()
        assert snap.board_height == 2

    def test_board_grid_reflects_current_state(self):
        engine, _ = _engine(["wR . bK"])
        snap = engine.snapshot()
        assert snap.board_grid[0][0] == "wR"
        assert snap.board_grid[0][1] == "."
        assert snap.board_grid[0][2] == "bK"

    def test_board_grid_is_deep_copy_not_live_reference(self):
        """Mutating the snapshot grid must not affect the live board."""
        board = _board(["wR . bK"])
        rule_engine = RuleEngine()
        arbiter = _mock_arbiter()
        engine = GameEngine(board=board, rule_engine=rule_engine, arbiter=arbiter)
        snap = engine.snapshot()
        snap.board_grid[0][0] = "TAMPERED"
        # Live board must be unchanged
        assert board.get(Position(0, 0)) == "wR"

    def test_selected_cell_none_by_default(self):
        engine, _ = _engine(["wR ."])
        snap = engine.snapshot()
        assert snap.selected_cell is None

    def test_selected_cell_reflects_injected_value(self):
        engine, _ = _engine(["wR ."])
        snap = engine.snapshot(selected_cell=Position(0, 0))
        assert snap.selected_cell == Position(0, 0)

    def test_game_over_false_by_default(self):
        engine, _ = _engine(["wR ."])
        snap = engine.snapshot()
        assert snap.game_over is False

    def test_game_over_true_after_king_captured(self):
        engine, _ = _engine(["wR . bK"])
        engine.notify_king_captured()
        snap = engine.snapshot()
        assert snap.game_over is True

    def test_snapshot_is_frozen(self):
        engine, _ = _engine(["wR ."])
        snap = engine.snapshot()
        with pytest.raises((AttributeError, TypeError)):
            snap.game_over = True


# ------------------------------------------------------------------ #
# Guard 1 — game_over blocks request_move                            #
# ------------------------------------------------------------------ #

class TestGuardGameOver:
    def test_returns_game_over_reason(self):
        engine, arbiter = _engine(["wR . ."])
        engine.notify_king_captured()
        result = engine.request_move(Position(0, 0), Position(0, 2))
        assert result.is_accepted is False
        assert result.reason == "game_over"

    def test_rule_engine_not_consulted_when_game_over(self):
        """RuleEngine.validate_move must never be called after game ends."""
        board = _board(["wR . ."])
        mock_rule_engine = MagicMock()
        arbiter = _mock_arbiter()
        engine = GameEngine(board=board, rule_engine=mock_rule_engine, arbiter=arbiter)
        engine.notify_king_captured()
        engine.request_move(Position(0, 0), Position(0, 2))
        mock_rule_engine.validate_move.assert_not_called()

    def test_arbiter_not_called_when_game_over(self):
        engine, arbiter = _engine(["wR . ."])
        engine.notify_king_captured()
        engine.request_move(Position(0, 0), Position(0, 2))
        arbiter.start_motion.assert_not_called()

    def test_multiple_requests_all_blocked_after_game_over(self):
        engine, _ = _engine(["wR . ."])
        engine.notify_king_captured()
        r1 = engine.request_move(Position(0, 0), Position(0, 1))
        r2 = engine.request_move(Position(0, 0), Position(0, 2))
        assert r1.reason == "game_over"
        assert r2.reason == "game_over"


# ------------------------------------------------------------------ #
# Guard 2 — motion_in_progress blocks request_move                   #
# ------------------------------------------------------------------ #

class TestGuardMotionInProgress:
    def test_allows_new_motion_when_another_is_active(self):
        engine, _ = _engine(["wR . ."], has_active=True)
        result = engine.request_move(Position(0, 0), Position(0, 2))
        assert result.is_accepted is True
        assert result.reason == "ok"

    def test_rule_engine_is_still_consulted_when_motion_active(self):
        board = _board(["wR . ."])
        mock_rule_engine = MagicMock()
        arbiter = _mock_arbiter(has_active=True)
        engine = GameEngine(board=board, rule_engine=mock_rule_engine, arbiter=arbiter)
        engine.request_move(Position(0, 0), Position(0, 2))
        mock_rule_engine.validate_move.assert_called_once()

    def test_arbiter_start_motion_is_called_when_motion_active(self):
        engine, arbiter = _engine(["wR . ."], has_active=True)
        engine.request_move(Position(0, 0), Position(0, 2))
        arbiter.start_motion.assert_called_once()

    def test_game_over_takes_priority_over_active_motion(self):
        """game_over guard must fire before any move request is accepted."""
        board = _board(["wR . ."])
        mock_rule_engine = MagicMock()
        arbiter = _mock_arbiter(has_active=True)
        engine = GameEngine(board=board, rule_engine=mock_rule_engine, arbiter=arbiter)
        engine.notify_king_captured()
        result = engine.request_move(Position(0, 0), Position(0, 2))
        assert result.reason == "game_over"


# ------------------------------------------------------------------ #
# Guard 3 — RuleEngine validation reasons propagated                 #
# ------------------------------------------------------------------ #

class TestGuardRuleValidation:
    def test_outside_board_reason_propagated(self):
        engine, _ = _engine(["wR ."])
        result = engine.request_move(Position(0, 0), Position(99, 99))
        assert result.is_accepted is False
        assert result.reason == "outside_board"

    def test_empty_source_reason_propagated(self):
        engine, _ = _engine(["wR ."])
        result = engine.request_move(Position(0, 1), Position(0, 0))
        assert result.is_accepted is False
        assert result.reason == "empty_source"

    def test_friendly_destination_reason_propagated(self):
        engine, _ = _engine(["wR wB"])
        result = engine.request_move(Position(0, 0), Position(0, 1))
        assert result.is_accepted is False
        assert result.reason == "friendly_destination"

    def test_illegal_piece_move_reason_propagated(self):
        engine, _ = _engine(["wR . .", ". . .", ". . ."])
        result = engine.request_move(Position(0, 0), Position(2, 2))
        assert result.is_accepted is False
        assert result.reason == "illegal_piece_move"

    def test_arbiter_not_called_on_invalid_move(self):
        engine, arbiter = _engine(["wR . ."])
        engine.request_move(Position(0, 0), Position(2, 2))
        arbiter.start_motion.assert_not_called()


# ------------------------------------------------------------------ #
# Guard 4 — valid move accepted, arbiter.start_motion called         #
# ------------------------------------------------------------------ #

class TestValidMoveAccepted:
    def test_returns_accepted_true_and_ok_reason(self):
        engine, _ = _engine(["wR . ."])
        result = engine.request_move(Position(0, 0), Position(0, 2))
        assert result.is_accepted is True
        assert result.reason == "ok"

    def test_arbiter_start_motion_called_with_correct_args(self):
        engine, arbiter = _engine(["wR . ."])
        engine.request_move(Position(0, 0), Position(0, 2))
        arbiter.start_motion.assert_called_once_with(
            piece="wR",
            source=Position(0, 0),
            destination=Position(0, 2),
        )

    def test_request_jump_returns_ok_and_starts_motion_in_place(self):
        engine, arbiter = _engine(["wR . ."])
        result = engine.request_jump(Position(0, 0))
        assert result.is_accepted is True
        assert result.reason == "ok"
        arbiter.start_motion.assert_called_once_with(
            piece="wR",
            source=Position(0, 0),
            destination=Position(0, 0),
            duration_ms=1000,
        )

    def test_request_jump_rejects_empty_source(self):
        engine, arbiter = _engine([". . ."])
        result = engine.request_jump(Position(0, 0))
        assert result.is_accepted is False
        assert result.reason == "empty_source"
        arbiter.start_motion.assert_not_called()

    def test_arbiter_start_motion_piece_token_correct_for_bishop(self):
        engine, arbiter = _engine([
            "wB . . .",
            ". . . .",
            ". . . .",
            ". . . .",
        ])
        engine.request_move(Position(0, 0), Position(3, 3))
        arbiter.start_motion.assert_called_once_with(
            piece="wB",
            source=Position(0, 0),
            destination=Position(3, 3),
        )

    def test_valid_capture_accepted(self):
        engine, arbiter = _engine(["wR . bR"])
        result = engine.request_move(Position(0, 0), Position(0, 2))
        assert result.is_accepted is True
        arbiter.start_motion.assert_called_once_with(
            piece="wR",
            source=Position(0, 0),
            destination=Position(0, 2),
        )


# ------------------------------------------------------------------ #
# wait() — delegates to arbiter, never touches board                 #
# ------------------------------------------------------------------ #

class TestWait:
    def test_wait_calls_arbiter_advance_time(self):
        engine, arbiter = _engine(["wR ."])
        engine.wait(500)
        arbiter.advance_time.assert_called_once_with(500)

    def test_wait_does_not_mutate_board(self):
        board = _board(["wR ."])
        rule_engine = RuleEngine()
        arbiter = _mock_arbiter()
        engine = GameEngine(board=board, rule_engine=rule_engine, arbiter=arbiter)
        engine.wait(1000)
        assert board.get(Position(0, 0)) == "wR"
        assert board.get(Position(0, 1)) == "."

    def test_wait_zero_ms_still_delegates(self):
        engine, arbiter = _engine(["wR ."])
        engine.wait(0)
        arbiter.advance_time.assert_called_once_with(0)

    def test_wait_large_value_delegates_correctly(self):
        engine, arbiter = _engine(["wR ."])
        engine.wait(99999)
        arbiter.advance_time.assert_called_once_with(99999)


# ------------------------------------------------------------------ #
# snapshot() — reflects live state                                   #
# ------------------------------------------------------------------ #

class TestSnapshot:
    def test_snapshot_dimensions_match_board(self):
        engine, _ = _engine(["wR . .", ". . ."])
        snap = engine.snapshot()
        assert snap.board_width == 3
        assert snap.board_height == 2

    def test_snapshot_grid_row_count(self):
        engine, _ = _engine(["wR . .", ". . ."])
        snap = engine.snapshot()
        assert len(snap.board_grid) == 2

    def test_snapshot_grid_col_count(self):
        engine, _ = _engine(["wR . .", ". . ."])
        snap = engine.snapshot()
        assert all(len(row) == 3 for row in snap.board_grid)

    def test_snapshot_game_over_false_initially(self):
        engine, _ = _engine(["wR ."])
        assert engine.snapshot().game_over is False

    def test_snapshot_game_over_true_after_notify(self):
        engine, _ = _engine(["wR ."])
        engine.notify_king_captured()
        assert engine.snapshot().game_over is True


# ------------------------------------------------------------------ #
# notify_king_captured() — sets game_over                            #
# ------------------------------------------------------------------ #

class TestNotifyKingCaptured:
    def test_sets_game_over_flag(self):
        engine, _ = _engine(["wR . bK"])
        assert engine.snapshot().game_over is False
        engine.notify_king_captured()
        assert engine.snapshot().game_over is True

    def test_idempotent_double_call(self):
        engine, _ = _engine(["wR . bK"])
        engine.notify_king_captured()
        engine.notify_king_captured()
        assert engine.snapshot().game_over is True

    def test_blocks_all_subsequent_moves(self):
        engine, arbiter = _engine(["wR . ."])
        engine.notify_king_captured()
        engine.request_move(Position(0, 0), Position(0, 1))
        engine.request_move(Position(0, 0), Position(0, 2))
        arbiter.start_motion.assert_not_called()
