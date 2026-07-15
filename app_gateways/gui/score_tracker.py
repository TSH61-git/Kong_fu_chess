from __future__ import annotations
import time
from dataclasses import dataclass

from chess_engine.engine.helpers.snapshot_models import GameSnapshot
from chess_engine.model.piece import Color, Piece
from chess_engine.realtime.motion import Motion


@dataclass
class CapturedEntry:
    piece: Piece
    captured_by: Color
    timestamp: float   # time.time() at capture moment


class ScoreTracker:
    def __init__(self) -> None:
        self._entries: list[CapturedEntry] = []
        self._prev_grid: list[list] | None = None
        # Motion source/destination cells as of the *previous* update() call.
        # A motion's board mutation (source cleared, destination overwritten)
        # and its removal from the arbiter's active list both happen inside
        # the same advance_time() call, so by the frame we observe the change
        # the motion is already gone from `motions`. We must compare against
        # last frame's in-flight cells, not this frame's.
        self._prev_moving_sources: set[tuple[int, int]] = set()
        self._prev_arriving_dests: set[tuple[int, int]] = set()

    def update(self, snapshot: GameSnapshot, motions: list[Motion]) -> None:
        moving_sources = {(m.source.row, m.source.col) for m in motions}
        arriving_dests = {(m.destination.row, m.destination.col) for m in motions}

        if self._prev_grid is not None:
            for row in range(snapshot.board_height):
                for col in range(snapshot.board_width):
                    prev: Piece | None = self._prev_grid[row][col]
                    curr: Piece | None = snapshot.board_grid[row][col]
                    key = (row, col)

                    if prev is None or key in self._prev_moving_sources:
                        continue  # empty, or piece that was mid-flight left here
                    if curr is not None and curr.color == prev.color:
                        continue  # same piece still there

                    if key in self._prev_arriving_dests:
                        captured_by = Color.WHITE if prev.color == Color.BLACK else Color.BLACK
                        self._entries.append(CapturedEntry(
                            piece=prev,
                            captured_by=captured_by,
                            timestamp=time.time(),
                        ))

        self._prev_grid = snapshot.board_grid
        self._prev_moving_sources = moving_sources
        self._prev_arriving_dests = arriving_dests

    def get_captured(self, color: Color) -> list[CapturedEntry]:
        return [e for e in self._entries if e.captured_by == color]
