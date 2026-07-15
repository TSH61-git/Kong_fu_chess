from chess_engine.engine.helpers.snapshot_models import GameSnapshot
from chess_engine.model.piece import Piece, PieceType, Color
from chess_engine.model.position import Position
from chess_engine.realtime.motion import Motion
from app_gateways.gui.score_tracker import ScoreTracker

_WR = Piece(PieceType.ROOK, Color.WHITE)
_BP = Piece(PieceType.PAWN, Color.BLACK)


def _snapshot(grid: list[list]) -> GameSnapshot:
    return GameSnapshot(
        board_width=len(grid[0]),
        board_height=len(grid),
        board_grid=grid,
        selected_cell=None,
        game_over=False,
    )


class TestScoreTrackerCapture:
    def test_capture_completing_in_the_same_frame_the_motion_disappears(self):
        """
        The arbiter clears the source cell, fills the destination cell, and
        drops the motion from its active list all inside one advance_time()
        call. ScoreTracker must still attribute the capture correctly using
        last frame's in-flight cells, not this frame's (now-empty) motions.
        """
        tracker = ScoreTracker()
        motion = Motion(piece=_WR, source=Position(4, 4), destination=Position(4, 6),
                         elapsed_ms=1950, duration_ms=2000)

        # frame 1: rook still mid-flight, pawn still sitting at the destination
        grid_mid_flight = [[None] * 8 for _ in range(8)]
        grid_mid_flight[4][4] = _WR
        grid_mid_flight[4][6] = _BP
        tracker.update(_snapshot(grid_mid_flight), motions=[motion])

        # frame 2: motion just completed within this same advance_time() call —
        # board already shows the rook at the destination and the motions list
        # is already empty.
        grid_after = [[None] * 8 for _ in range(8)]
        grid_after[4][6] = _WR
        tracker.update(_snapshot(grid_after), motions=[])

        captured_by_white = tracker.get_captured(Color.WHITE)
        captured_by_black = tracker.get_captured(Color.BLACK)

        assert len(captured_by_white) == 1
        assert captured_by_white[0].piece == _BP
        assert captured_by_black == []  # rook must not be falsely reported as captured

    def test_piece_simply_moving_away_is_not_registered_as_captured(self):
        tracker = ScoreTracker()
        motion = Motion(piece=_WR, source=Position(4, 4), destination=Position(4, 6),
                         elapsed_ms=1950, duration_ms=2000)

        grid_mid_flight = [[None] * 8 for _ in range(8)]
        grid_mid_flight[4][4] = _WR
        tracker.update(_snapshot(grid_mid_flight), motions=[motion])

        grid_after = [[None] * 8 for _ in range(8)]
        grid_after[4][6] = _WR
        tracker.update(_snapshot(grid_after), motions=[])

        assert tracker.get_captured(Color.WHITE) == []
        assert tracker.get_captured(Color.BLACK) == []
