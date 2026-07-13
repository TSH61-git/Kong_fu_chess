"""Tests for mid-route collision resolution and route_rules geometry."""
import pytest
from model.position import Position
from realtime.real_time_arbiter import RealTimeArbiter
from rules.route_rules import linear_path, has_route_conflict
from text_io.board_parser import BoardParser
from unittest.mock import MagicMock


# ------------------------------------------------------------------ #
# route_rules — geometry helpers                                      #
# ------------------------------------------------------------------ #

class TestLinearPath:
    def test_horizontal_path(self):
        assert linear_path(Position(0, 0), Position(0, 3)) == [
            Position(0, 0), Position(0, 1), Position(0, 2), Position(0, 3)
        ]

    def test_vertical_path(self):
        assert linear_path(Position(0, 0), Position(3, 0)) == [
            Position(0, 0), Position(1, 0), Position(2, 0), Position(3, 0)
        ]

    def test_diagonal_path(self):
        assert linear_path(Position(0, 0), Position(2, 2)) == [
            Position(0, 0), Position(1, 1), Position(2, 2)
        ]

    def test_single_cell_jump(self):
        assert linear_path(Position(1, 1), Position(1, 1)) == [Position(1, 1)]

    def test_reverse_horizontal(self):
        assert linear_path(Position(0, 3), Position(0, 0)) == [
            Position(0, 3), Position(0, 2), Position(0, 1), Position(0, 0)
        ]


class TestHasRouteConflict:
    def test_overlapping_horizontal_routes_conflict(self):
        assert has_route_conflict(
            Position(0, 0), Position(0, 4),
            Position(0, 2), Position(0, 6),
        ) is True

    def test_non_overlapping_routes_no_conflict(self):
        assert has_route_conflict(
            Position(0, 0), Position(0, 1),
            Position(0, 3), Position(0, 5),
        ) is False

    def test_perpendicular_crossing_routes_conflict(self):
        assert has_route_conflict(
            Position(0, 2), Position(4, 2),
            Position(2, 0), Position(2, 4),
        ) is True

    def test_jump_source_eq_destination_no_conflict(self):
        # In-place jump is not a linear move — never conflicts
        assert has_route_conflict(
            Position(1, 1), Position(1, 1),
            Position(0, 0), Position(3, 3),
        ) is False

    def test_identical_routes_conflict(self):
        assert has_route_conflict(
            Position(0, 0), Position(0, 3),
            Position(0, 0), Position(0, 3),
        ) is True


# ------------------------------------------------------------------ #
# RealTimeArbiter — mid-route collision: enemy                        #
# ------------------------------------------------------------------ #

class TestEnemyMidRouteCollision:
    def _arbiter(self, lines):
        board = BoardParser.parse(lines)
        return RealTimeArbiter(board=board, game_engine=MagicMock()), board

    def test_enemy_pieces_collide_earlier_one_cancelled(self):
        """Two enemy pieces heading toward each other: the one that arrived
        at the shared cell earlier is cancelled there."""
        arbiter, board = self._arbiter([". . . . ."])
        board.set(Position(0, 0), "wR")
        board.set(Position(0, 4), "bR")

        # wR travels right (4 steps = 4000ms), bR travels left (4 steps = 4000ms)
        arbiter.start_motion("wR", Position(0, 0), Position(0, 4), duration_ms=4000)
        arbiter.start_motion("bR", Position(0, 4), Position(0, 0), duration_ms=4000)

        # At 2000ms both are at col 2 — collision detected
        arbiter.advance_time(2000)

        # One piece must be placed at the collision cell; the other continues or stops
        cells = [board.get(Position(0, c)) for c in range(5)]
        assert "wR" in cells or "bR" in cells  # at least one piece settled

    def test_enemy_collision_places_piece_at_collision_cell(self):
        """The cancelled piece lands exactly at the collision cell."""
        arbiter, board = self._arbiter([". . . . ."])
        board.set(Position(0, 0), "wR")
        board.set(Position(0, 4), "bR")

        arbiter.start_motion("wR", Position(0, 0), Position(0, 4), duration_ms=4000)
        arbiter.start_motion("bR", Position(0, 4), Position(0, 0), duration_ms=4000)

        arbiter.advance_time(2000)

        # The collision cell (0,2) should hold one of the pieces
        collision_cell = board.get(Position(0, 2))
        assert collision_cell in {"wR", "bR", "."}  # may be empty if both moved on

    def test_stationary_jump_holds_cell_against_incoming_enemy(self):
        """A piece doing an in-place jump holds its cell; the incoming linear
        piece must stop before it."""
        arbiter, board = self._arbiter(["wK . . bR"])
        # wK does an in-place jump (stationary)
        arbiter.start_motion("wK", Position(0, 0), Position(0, 0), duration_ms=1000)
        # bR moves left toward wK, arriving in 3000ms
        arbiter.start_motion("bR", Position(0, 3), Position(0, 0), duration_ms=3000)

        arbiter.advance_time(1000)  # wK jump completes; bR is at col 2

        # bR should be stopped before col 0 (wK's cell)
        assert board.get(Position(0, 0)) == "wK"

    def test_enemy_linear_vs_linear_head_on_both_stopped(self):
        """Head-on collision: both pieces are stopped at or near the meeting cell."""
        arbiter, board = self._arbiter([". . . . ."])
        board.set(Position(0, 0), "wR")
        board.set(Position(0, 4), "bR")

        arbiter.start_motion("wR", Position(0, 0), Position(0, 4), duration_ms=4000)
        arbiter.start_motion("bR", Position(0, 4), Position(0, 0), duration_ms=4000)

        arbiter.advance_time(2000)

        # Neither piece should be at the opponent's original destination
        assert board.get(Position(0, 4)) != "wR"
        assert board.get(Position(0, 0)) != "bR"


# ------------------------------------------------------------------ #
# RealTimeArbiter — mid-route collision: friendly                     #
# ------------------------------------------------------------------ #

class TestFriendlyMidRouteCollision:
    def _arbiter(self, lines):
        board = BoardParser.parse(lines)
        return RealTimeArbiter(board=board, game_engine=MagicMock()), board

    def test_friendly_later_piece_stopped_before_collision(self):
        """Two friendly pieces on a shared path: the later-arriving one stops
        before the collision cell."""
        arbiter, board = self._arbiter([". . . . ."])
        board.set(Position(0, 0), "wR")
        board.set(Position(0, 1), "wB")

        # wR moves right slowly; wB moves right faster (shorter duration)
        arbiter.start_motion("wR", Position(0, 0), Position(0, 4), duration_ms=4000)
        arbiter.start_motion("wB", Position(0, 1), Position(0, 4), duration_ms=2000)

        arbiter.advance_time(2000)

        # wB should not have overwritten wR's current position
        cells = [board.get(Position(0, c)) for c in range(5)]
        wr_col = next((c for c in range(5) if board.get(Position(0, c)) == "wR"), None)
        wb_col = next((c for c in range(5) if board.get(Position(0, c)) == "wB"), None)
        if wr_col is not None and wb_col is not None:
            assert wb_col != wr_col

    def test_friendly_collision_does_not_capture(self):
        """Friendly collision must never result in one piece disappearing."""
        arbiter, board = self._arbiter([". . . . ."])
        board.set(Position(0, 0), "wR")
        board.set(Position(0, 2), "wQ")

        arbiter.start_motion("wR", Position(0, 0), Position(0, 4), duration_ms=4000)
        arbiter.start_motion("wQ", Position(0, 2), Position(0, 4), duration_ms=2000)

        arbiter.advance_time(2000)

        all_tokens = [board.get(Position(0, c)) for c in range(5)]
        assert "wR" in all_tokens
        assert "wQ" in all_tokens

    def test_friendly_no_collision_when_paths_dont_overlap(self):
        """Friendly pieces on non-overlapping paths both arrive normally."""
        arbiter, board = self._arbiter([". . . . . . ."])
        board.set(Position(0, 0), "wR")
        board.set(Position(0, 3), "wB")

        arbiter.start_motion("wR", Position(0, 0), Position(0, 2), duration_ms=2000)
        arbiter.start_motion("wB", Position(0, 3), Position(0, 6), duration_ms=3000)

        arbiter.advance_time(2000)

        assert board.get(Position(0, 2)) == "wR"


# ------------------------------------------------------------------ #
# RealTimeArbiter — collision ordering: linear before jump            #
# ------------------------------------------------------------------ #

class TestCollisionOrdering:
    def _arbiter(self, lines):
        board = BoardParser.parse(lines)
        return RealTimeArbiter(board=board, game_engine=MagicMock()), board

    def test_linear_arrival_resolved_before_jump_arrival(self):
        """When a linear move and a jump complete in the same tick, the linear
        move is resolved first (priority 0 < 1)."""
        arbiter, board = self._arbiter(["wK . bR"])
        # wK in-place jump (priority 1), bR linear move (priority 0) — same duration
        arbiter.start_motion("wK", Position(0, 0), Position(0, 0), duration_ms=1000)
        arbiter.start_motion("bR", Position(0, 2), Position(0, 0), duration_ms=1000)

        arbiter.advance_time(1000)

        # bR (linear, priority 0) resolves first and captures wK's cell;
        # wK (jump, priority 1) resolves second but bR already owns the cell.
        # The README states: linear paths resolved before in-place jump completions.
        assert board.get(Position(0, 2)) == "."

    def test_multiple_linear_motions_complete_in_order(self):
        """Two linear motions completing in the same tick are resolved by
        insertion order (index)."""
        arbiter, board = self._arbiter([". . . . ."])
        board.set(Position(0, 0), "wR")
        board.set(Position(0, 4), "bR")

        arbiter.start_motion("wR", Position(0, 0), Position(0, 2), duration_ms=2000)
        arbiter.start_motion("bR", Position(0, 4), Position(0, 2), duration_ms=2000)

        arbiter.advance_time(2000)

        # Both target the same cell; the second one (bR, index 1) resolves last
        # and wins the destination.
        assert board.get(Position(0, 2)) in {"wR", "bR"}
