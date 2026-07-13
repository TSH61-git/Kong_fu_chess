import pytest
from unittest.mock import MagicMock
from chess_engine.model.position import Position
from chess_engine.rules.engine import RuleEngine
from chess_engine.engine.game_engine import GameEngine
from chess_engine.engine.helpers.snapshot_models import MoveResult, GameSnapshot
from app_gateways.text_cli.translator import board_from_token_lines as _board


def _mock_arbiter(has_active=False):
    arbiter = MagicMock()
    arbiter.has_active_motion.return_value = has_active
    arbiter.is_in_cooldown.return_value = False
    return arbiter


def _engine(lines, has_active=False):
    board = _board(lines)
    engine = GameEngine(board=board, rule_engine=RuleEngine(), arbiter=_mock_arbiter(has_active))
    return engine, engine._arbiter


class TestMoveResultContract:
    def test_has_is_accepted_field(self):
        assert MoveResult(is_accepted=True, reason="ok").is_accepted is True

    def test_has_reason_field(self):
        assert MoveResult(is_accepted=False, reason="game_over").reason == "game_over"

    def test_is_immutable_is_accepted(self):
        mr = MoveResult(is_accepted=True, reason="ok")
        with pytest.raises((AttributeError, TypeError)):
            mr.is_accepted = False

    def test_is_immutable_reason(self):
        mr = MoveResult(is_accepted=True, reason="ok")
        with pytest.raises((AttributeError, TypeError)):
            mr.reason = "tampered"


class TestGuardGameOver:
    def test_returns_game_over_reason(self):
        engine, _ = _engine(["wR . ."])
        engine.notify_king_captured()
        result = engine.request_move(Position(0, 0), Position(0, 2))
        assert result.is_accepted is False and result.reason == "game_over"

    def test_rule_engine_not_consulted_when_game_over(self):
        board = _board(["wR . ."])
        mock_re = MagicMock()
        engine = GameEngine(board=board, rule_engine=mock_re, arbiter=_mock_arbiter())
        engine.notify_king_captured()
        engine.request_move(Position(0, 0), Position(0, 2))
        mock_re.validate_move.assert_not_called()

    def test_arbiter_not_called_when_game_over(self):
        engine, arbiter = _engine(["wR . ."])
        engine.notify_king_captured()
        engine.request_move(Position(0, 0), Position(0, 2))
        arbiter.start_motion.assert_not_called()

    def test_multiple_requests_all_blocked_after_game_over(self):
        engine, _ = _engine(["wR . ."])
        engine.notify_king_captured()
        assert engine.request_move(Position(0, 0), Position(0, 1)).reason == "game_over"
        assert engine.request_move(Position(0, 0), Position(0, 2)).reason == "game_over"


class TestGuardMotionInProgress:
    def test_allows_new_motion_when_another_is_active(self):
        engine, _ = _engine(["wR . ."], has_active=True)
        result = engine.request_move(Position(0, 0), Position(0, 2))
        assert result.is_accepted is True and result.reason == "ok"

    def test_game_over_takes_priority_over_active_motion(self):
        board = _board(["wR . ."])
        engine = GameEngine(board=board, rule_engine=MagicMock(), arbiter=_mock_arbiter(has_active=True))
        engine.notify_king_captured()
        assert engine.request_move(Position(0, 0), Position(0, 2)).reason == "game_over"


class TestGuardRuleValidation:
    def test_outside_board_reason_propagated(self):
        engine, _ = _engine(["wR ."])
        assert engine.request_move(Position(0, 0), Position(99, 99)).reason == "outside_board"

    def test_empty_source_reason_propagated(self):
        engine, _ = _engine(["wR ."])
        assert engine.request_move(Position(0, 1), Position(0, 0)).reason == "empty_source"

    def test_friendly_destination_reason_propagated(self):
        engine, _ = _engine(["wR wB"])
        assert engine.request_move(Position(0, 0), Position(0, 1)).reason == "friendly_destination"

    def test_illegal_piece_move_reason_propagated(self):
        engine, _ = _engine(["wR . .", ". . .", ". . ."])
        assert engine.request_move(Position(0, 0), Position(2, 2)).reason == "illegal_piece_move"

    def test_arbiter_not_called_on_invalid_move(self):
        engine, arbiter = _engine(["wR . ."])
        engine.request_move(Position(0, 0), Position(2, 2))
        arbiter.start_motion.assert_not_called()


class TestValidMoveAccepted:
    def test_returns_accepted_true_and_ok_reason(self):
        engine, _ = _engine(["wR . ."])
        result = engine.request_move(Position(0, 0), Position(0, 2))
        assert result.is_accepted is True and result.reason == "ok"

    def test_request_jump_rejects_empty_source(self):
        engine, arbiter = _engine([". . ."])
        result = engine.request_jump(Position(0, 0))
        assert result.is_accepted is False and result.reason == "empty_source"
        arbiter.start_motion.assert_not_called()

    def test_valid_capture_accepted(self):
        engine, _ = _engine(["wR . bR"])
        result = engine.request_move(Position(0, 0), Position(0, 2))
        assert result.is_accepted is True


class TestWait:
    def test_wait_calls_arbiter_advance_time(self):
        engine, arbiter = _engine(["wR ."])
        engine.wait(500)
        arbiter.advance_time.assert_called_once_with(500)

    def test_wait_zero_ms_still_delegates(self):
        engine, arbiter = _engine(["wR ."])
        engine.wait(0)
        arbiter.advance_time.assert_called_once_with(0)


class TestSnapshot:
    def test_snapshot_dimensions_match_board(self):
        engine, _ = _engine(["wR . .", ". . ."])
        snap = engine.snapshot()
        assert snap.board_width == 3 and snap.board_height == 2

    def test_snapshot_game_over_false_initially(self):
        engine, _ = _engine(["wR ."])
        assert engine.snapshot().game_over is False

    def test_snapshot_game_over_true_after_notify(self):
        engine, _ = _engine(["wR ."])
        engine.notify_king_captured()
        assert engine.snapshot().game_over is True


class TestNotifyKingCaptured:
    def test_sets_game_over_flag(self):
        engine, _ = _engine(["wR . bK"])
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
