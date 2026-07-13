import pytest
from unittest.mock import MagicMock
from chess_engine.model.position import Position
from chess_engine.model.piece import Piece, PieceType, Color
from chess_engine.realtime.arbiter import RealTimeArbiter, _COOLDOWN_MS
from chess_engine.rules.engine import RuleEngine
from app_gateways.text_cli.translator import board_from_token_lines as _parse

_WR = Piece(PieceType.ROOK, Color.WHITE)


class TestCooldownDurationRegistry:
    def test_cooldown_constant_is_1000ms(self):
        assert _COOLDOWN_MS == 1000


class TestArbiterCooldownAfterArrival:
    def _arbiter(self, lines):
        board = _parse(lines)
        return RealTimeArbiter(board=board, game_engine=MagicMock()), board

    def test_not_in_cooldown_before_arrival(self):
        arbiter, _ = self._arbiter(["wR . ."])
        arbiter.start_motion(_WR, Position(0, 0), Position(0, 2))
        assert arbiter.is_in_cooldown(Position(0, 2)) is False

    def test_in_cooldown_immediately_after_arrival(self):
        arbiter, _ = self._arbiter(["wR . ."])
        arbiter.start_motion(_WR, Position(0, 0), Position(0, 2))
        arbiter.advance_time(2000)
        assert arbiter.is_in_cooldown(Position(0, 2)) is True

    def test_cooldown_expires_after_full_duration(self):
        arbiter, _ = self._arbiter(["wR . ."])
        arbiter.start_motion(_WR, Position(0, 0), Position(0, 2))
        arbiter.advance_time(2000)
        arbiter.advance_time(1000)
        assert arbiter.is_in_cooldown(Position(0, 2)) is False

    def test_cooldown_still_active_before_expiry(self):
        arbiter, _ = self._arbiter(["wR . ."])
        arbiter.start_motion(_WR, Position(0, 0), Position(0, 2))
        arbiter.advance_time(2000)
        arbiter.advance_time(500)
        assert arbiter.is_in_cooldown(Position(0, 2)) is True

    def test_cooldown_ticks_without_active_motion(self):
        arbiter, _ = self._arbiter(["wR . ."])
        arbiter.start_motion(_WR, Position(0, 0), Position(0, 2))
        arbiter.advance_time(2000)
        arbiter.advance_time(999)
        assert arbiter.is_in_cooldown(Position(0, 2)) is True
        arbiter.advance_time(1)
        assert arbiter.is_in_cooldown(Position(0, 2)) is False

    def test_source_cell_not_in_cooldown_after_departure(self):
        arbiter, _ = self._arbiter(["wR . ."])
        arbiter.start_motion(_WR, Position(0, 0), Position(0, 2))
        arbiter.advance_time(2000)
        assert arbiter.is_in_cooldown(Position(0, 0)) is False

    def test_jump_arrival_sets_cooldown_on_same_cell(self):
        arbiter, _ = self._arbiter(["wR . ."])
        arbiter.start_motion(_WR, Position(0, 0), Position(0, 0), duration_ms=1000)
        arbiter.advance_time(1000)
        assert arbiter.is_in_cooldown(Position(0, 0)) is True

    def test_unrelated_cell_never_in_cooldown(self):
        arbiter, _ = self._arbiter(["wR . ."])
        arbiter.start_motion(_WR, Position(0, 0), Position(0, 2))
        arbiter.advance_time(2000)
        assert arbiter.is_in_cooldown(Position(0, 1)) is False


class TestEngineCooldownGuard:
    def _engine_with_cooldown(self, lines, cooldown_pos):
        board = _parse(lines)
        rule_engine = RuleEngine()
        arbiter = MagicMock()
        arbiter.is_in_cooldown.side_effect = lambda pos: pos == cooldown_pos
        from chess_engine.engine.game_engine import GameEngine
        engine = GameEngine(board=board, rule_engine=rule_engine, arbiter=arbiter)
        return engine, arbiter

    def test_request_move_rejected_when_source_in_cooldown(self):
        engine, _ = self._engine_with_cooldown(["wR . ."], Position(0, 0))
        result = engine.request_move(Position(0, 0), Position(0, 2))
        assert result.is_accepted is False and result.reason == "cooldown_active"

    def test_arbiter_start_motion_not_called_during_cooldown(self):
        engine, arbiter = self._engine_with_cooldown(["wR . ."], Position(0, 0))
        engine.request_move(Position(0, 0), Position(0, 2))
        arbiter.start_motion.assert_not_called()

    def test_request_jump_rejected_when_in_cooldown(self):
        engine, _ = self._engine_with_cooldown(["wR . ."], Position(0, 0))
        result = engine.request_jump(Position(0, 0))
        assert result.is_accepted is False and result.reason == "cooldown_active"

    def test_game_over_takes_priority_over_cooldown(self):
        engine, _ = self._engine_with_cooldown(["wR . ."], Position(0, 0))
        engine.notify_king_captured()
        result = engine.request_move(Position(0, 0), Position(0, 2))
        assert result.reason == "game_over"
