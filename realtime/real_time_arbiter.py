"""Real-time motion coordinator for the application service layer."""
from __future__ import annotations

from typing import Optional

from model.board import Board
from model.piece import Piece, PieceState
from model.position import Position
from realtime.motion import Motion

CELL_SIZE = 100
PIECE_SPEED = 100


class RealTimeArbiter:
    """Coordinate one active motion at a time and resolve arrivals atomically.

    The arbiter is the only component that mutates the board during a motion.
    It keeps the moving piece logically at its source until the exact arrival
    millisecond, then clears the source, resolves captures, and places the
    piece at the destination.
    """

    def __init__(self, board: Board, game_engine: Optional[object] = None) -> None:
        self._board = board
        self._game_engine = game_engine
        self._active_motion: Optional[Motion] = None
        self._active_piece: Optional[Piece] = None

    @property
    def active_motion(self) -> Optional[Motion]:
        """Return the currently tracked motion, if one exists."""
        return self._active_motion

    @property
    def active_piece(self) -> Optional[Piece]:
        """Return the moving piece object that is currently or was last moving."""
        return self._active_piece

    @property
    def game_engine(self) -> Optional[object]:
        """Return the application service hook used for king-capture notifications."""
        return self._game_engine

    @game_engine.setter
    def game_engine(self, value: Optional[object]) -> None:
        """Attach or detach the application service hook for notifications."""
        self._game_engine = value

    def attach_game_engine(self, game_engine: object) -> None:
        """Attach the application service hook used for king-capture notifications."""
        self.game_engine = game_engine

    def has_active_motion(self) -> bool:
        """Return True when a motion is currently being tracked."""
        return self._active_motion is not None

    def start_motion(
        self,
        piece: str,
        source: Position,
        destination: Position,
        duration_ms: Optional[int] = None,
    ) -> None:
        """Begin a new motion and mark the moving piece as in transit."""
        if self._active_motion is not None:
            raise RuntimeError("Only one motion may be active at a time.")

        resolved_duration = (
            duration_ms if duration_ms is not None else self._calculate_duration_ms(source, destination)
        )
        self._active_motion = Motion(
            piece=piece,
            source=source,
            destination=destination,
            elapsed_ms=0,
            duration_ms=resolved_duration,
        )
        self._active_piece = Piece(piece)
        self._active_piece.state = PieceState.MOVING

    def advance_time(self, ms: int) -> None:
        """Advance the active motion by ms milliseconds and resolve arrivals."""
        if self._active_motion is None or ms <= 0:
            return

        self._active_motion.elapsed_ms += ms
        if self._active_motion.elapsed_ms >= self._active_motion.duration_ms:
            self._resolve_arrival()

    def _resolve_arrival(self) -> None:
        """Apply the arrival transition atomically to the board."""
        motion = self._active_motion
        if motion is None:
            return

        self._board.set(motion.source, ".")
        victim = self._board.get(motion.destination)
        if victim != "." and self._is_king(victim):
            self._game_engine.notify_king_captured()
        self._board.set(motion.destination, motion.piece)

        if self._active_piece is not None:
            self._active_piece.state = PieceState.IDLE

        self._active_motion = None

    def _calculate_duration_ms(self, source: Position, destination: Position) -> int:
        """Return the travel time in milliseconds for this motion."""
        steps = max(
            abs(destination.row - source.row),
            abs(destination.col - source.col),
        )
        distance_px = steps * CELL_SIZE
        return int(distance_px / PIECE_SPEED * 1000)

    def _is_king(self, token: str) -> bool:
        """Return True when token represents a king piece."""
        return token in {"wK", "bK"}
