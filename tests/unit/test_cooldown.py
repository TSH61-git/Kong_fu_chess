"""Tests for cooldown mechanics — rules registry, arbiter tracking, engine guard."""
import pytest
from model.position import Position
from realtime.real_time_arbiter import RealTimeArbiter
from rules.cooldown_rules import get_cooldown_duration
from text_io.board_parser import BoardParser
from unittest.mock import MagicMock
from engine.game_engine import GameEngine
from rules.rule_engine import RuleEngine


# ------------------------------------------------------------------ #
# cooldown_rules — duration registry                                  #
# ------------------------------------------------------------------ #

class TestCooldownDurationRegistry:
    @pytest.mark.parametrize("token", ["wP", "wR", "wB", "wN", "wQ", "wK",
                                        "bP", "bR", "bB", "bN", "bQ", "bK"])
    def test_known_pieces_return_1000ms(self, token):
        assert get_cooldown_duration(token) == 1000

    def test_unknown_token_returns_default(self):
        assert get_cooldown_duration("wX") == 1000

    def test_malformed_single_char_returns_default(self):
        assert get_cooldown_duration("w") == 1000

    def test_empty_string_returns_default(self):
        assert get_cooldown_duration("") == 1000


# ------------------------------------------------------------------ #
# RealTimeArbiter — cooldown state after arrival                      #
# ------------------------------------------------------------------ #

class TestArbiterCooldownAfterArrival:
    def _arbiter(self, lines):
        board = BoardParser.parse(lines)
        return RealTimeArbiter(board=board, game_engine=MagicMock()), board

    def test_not_in_cooldown_before_arrival(self):
        arbiter, _ = self._arbiter(["wR . ."])
        arbiter.start_motion("wR", Position(0, 0), Position(0, 2))
        assert arbiter.is_in_cooldown(Position(0, 2)) is False

    def test_in_cooldown_immediately_after_arrival(self):
        arbiter, _ = self._arbiter(["wR . ."])
        arbiter.start_motion("wR", Position(0, 0), Position(0, 2))
        arbiter.advance_time(2000)
        assert arbiter.is_in_cooldown(Position(0, 2)) is True

    def test_cooldown_expires_after_full_duration(self):
        arbiter, _ = self._arbiter(["wR . ."])
        arbiter.start_motion("wR", Position(0, 0), Position(0, 2))
        arbiter.advance_time(2000)   # arrival
        arbiter.advance_time(1000)   # full cooldown elapsed
        assert arbiter.is_in_cooldown(Position(0, 2)) is False

    def test_cooldown_still_active_before_expiry(self):
        arbiter, _ = self._arbiter(["wR . ."])
        arbiter.start_motion("wR", Position(0, 0), Position(0, 2))
        arbiter.advance_time(2000)
        arbiter.advance_time(500)    # only half cooldown elapsed
        assert arbiter.is_in_cooldown(Position(0, 2)) is True

    def test_cooldown_ticks_without_active_motion(self):
        arbiter, _ = self._arbiter(["wR . ."])
        arbiter.start_motion("wR", Position(0, 0), Position(0, 2))
        arbiter.advance_time(2000)
        arbiter.advance_time(999)
        assert arbiter.is_in_cooldown(Position(0, 2)) is True
        arbiter.advance_time(1)
        assert arbiter.is_in_cooldown(Position(0, 2)) is False

    def test_source_cell_not_in_cooldown_after_departure(self):
        arbiter, _ = self._arbiter(["wR . ."])
        arbiter.start_motion("wR", Position(0, 0), Position(0, 2))
        arbiter.advance_time(2000)
        assert arbiter.is_in_cooldown(Position(0, 0)) is False

    def test_jump_arrival_sets_cooldown_on_same_cell(self):
        arbiter, _ = self._arbiter(["wR . ."])
        arbiter.start_motion("wR", Position(0, 0), Position(0, 0), duration_ms=1000)
        arbiter.advance_time(1000)
        assert arbiter.is_in_cooldown(Position(0, 0)) is True

    def test_unrelated_cell_never_in_cooldown(self):
        arbiter, _ = self._arbiter(["wR . ."])
        arbiter.start_motion("wR", Position(0, 0), Position(0, 2))
        arbiter.advance_time(2000)
        assert arbiter.is_in_cooldown(Position(0, 1)) is False


# ------------------------------------------------------------------ #
# GameEngine — cooldown_active guard                                  #
# ------------------------------------------------------------------ #

class TestEngineCooldownGuard:
    def _engine_with_cooldown(self, lines, cooldown_pos):
        board = BoardParser.parse(lines)
        rule_engine = RuleEngine()
        arbiter = MagicMock()
        arbiter.is_in_cooldown.side_effect = lambda pos: pos == cooldown_pos
        engine = GameEngine(board=board, rule_engine=rule_engine, arbiter=arbiter)
        return engine, arbiter

    def test_request_move_rejected_when_source_in_cooldown(self):
        engine, _ = self._engine_with_cooldown(["wR . ."], Position(0, 0))
        result = engine.request_move(Position(0, 0), Position(0, 2))
        assert result.is_accepted is False
        assert result.reason == "cooldown_active"

    def test_arbiter_start_motion_not_called_during_cooldown(self):
        engine, arbiter = self._engine_with_cooldown(["wR . ."], Position(0, 0))
        engine.request_move(Position(0, 0), Position(0, 2))
        arbiter.start_motion.assert_not_called()

    def test_request_jump_rejected_when_in_cooldown(self):
        engine, _ = self._engine_with_cooldown(["wR . ."], Position(0, 0))
        result = engine.request_jump(Position(0, 0))
        assert result.is_accepted is False
        assert result.reason == "cooldown_active"

    def test_different_piece_not_blocked_by_other_cooldown(self):
        # wR at (0,0) is in cooldown; wR at (0,4) is not — it should move freely
        board = BoardParser.parse(["wR . . . wR ."])
        rule_engine = RuleEngine()
        arbiter = MagicMock()
        arbiter.is_in_cooldown.side_effect = lambda pos: pos == Position(0, 0)
        engine = GameEngine(board=board, rule_engine=rule_engine, arbiter=arbiter)
        result = engine.request_move(Position(0, 4), Position(0, 5))
        assert result.is_accepted is True

    def test_game_over_takes_priority_over_cooldown(self):
        engine, arbiter = self._engine_with_cooldown(["wR . ."], Position(0, 0))
        engine.notify_king_captured()
        result = engine.request_move(Position(0, 0), Position(0, 2))
        assert result.reason == "game_over"
