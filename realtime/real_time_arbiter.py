"""Real-time motion coordinator for the application service layer."""
from __future__ import annotations

from typing import Optional

from model.board import Board
from model.piece import Piece, PieceState
from model.position import Position
from realtime.motion import Motion
from rules.promotion_rules import get_promoted_token

CELL_SIZE = 100
PIECE_SPEED = 100


class RealTimeArbiter:
    """Coordinate multiple active motions and resolve arrivals atomically.

    The arbiter is the only component that mutates the board during a motion.
    It keeps each moving piece logically at its source until the exact arrival
    millisecond, then clears the source, resolves captures, and places the
    piece at the destination.
    """

    def __init__(self, board: Board, game_engine: Optional[object] = None) -> None:
        self._board = board
        self._game_engine = game_engine
        self._active_motions: list[Motion] = []
        self._active_piece: Optional[Piece] = None
        self._motion_pieces: dict[Motion, Piece] = {}

    @property
    def active_motion(self) -> Optional[Motion]:
        """Return the most recently started active motion, if one exists."""
        if not self._active_motions:
            return None
        return self._active_motions[-1]

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
        """Return True when at least one motion is currently being tracked."""
        return bool(self._active_motions)

    def get_active_motions(self) -> list[Motion]:
        """Return a snapshot of all active motions currently tracked by the arbiter."""
        return list(self._active_motions)

    def start_motion(
        self,
        piece: str,
        source: Position,
        destination: Position,
        duration_ms: Optional[int] = None,
    ) -> None:
        """Begin a new motion and mark the moving piece as in transit."""
        resolved_duration = (
            duration_ms if duration_ms is not None else self._calculate_duration_ms(source, destination)
        )
        motion = Motion(
            piece=piece,
            source=source,
            destination=destination,
            elapsed_ms=0,
            duration_ms=resolved_duration,
        )
        self._active_motions.append(motion)
        self._active_piece = Piece(piece)
        self._active_piece.state = PieceState.MOVING
        self._motion_pieces[motion] = self._active_piece

    def advance_time(self, ms: int) -> None:
        """Advance all active motions by ms milliseconds and resolve arrivals."""
        if not self._active_motions or ms <= 0:
            return

        completed: list[tuple[int, int, Motion]] = []
        for index, motion in enumerate(self._active_motions):
            motion.elapsed_ms += ms
            if motion.elapsed_ms >= motion.duration_ms:
                priority = 0 if motion.source != motion.destination else 1
                completed.append((priority, index, motion))

        if not completed:
            return

        completed.sort(key=lambda item: (item[0], item[1]))
        for _, _, motion in completed:
            if motion in self._active_motions:
                self._active_motions.remove(motion)
                self._resolve_arrival(motion)

    def _resolve_arrival(self, motion: Motion) -> None:
        """Apply the arrival transition atomically to the board.

        After a piece arrives at its destination:
          1. Clear the source cell.
          2. Check if the destination held a King (capture detection).
          3. Place the piece at the destination, overwriting any occupant.
          4. Check for pawn promotion and apply it if needed.
          5. Mark the motion's piece as idle and remove it from active tracking.
        """
        self._board.set(motion.source, ".")
        victim = self._board.get(motion.destination)
        if victim != "." and self._is_king(victim):
            if self._game_engine is not None:
                self._game_engine.notify_king_captured()
        self._board.set(motion.destination, motion.piece)

        self._apply_promotion_if_needed(motion.destination, motion.piece)

        piece = self._motion_pieces.pop(motion, None)
        if piece is not None:
            piece.state = PieceState.IDLE

    def _apply_promotion_if_needed(self, destination: Position, piece_token: str) -> None:
        """Check if a piece should be promoted upon arrival and apply the transformation.
        
        Extraction flow:
          - Piece token format: two characters, e.g. 'wP', 'bP', 'wK'.
          - Color (first character): 'w' or 'b'.
          - Piece type (second character): 'P', 'R', 'B', 'N', 'Q', 'K'.
        
        If the piece type transforms (e.g. Pawn to Queen), atomically update
        the destination cell with the new token.
        
        Args:
            destination: The arrival position.
            piece_token: The two-character token string of the moving piece.
        """
        if len(piece_token) < 2:
            return

        color = piece_token[0]
        piece_type = piece_token[1]

        promoted_type = get_promoted_token(
            piece_type, destination.row, self._board.rows, color
        )

        # Apply promotion if the piece type changed
        if promoted_type != piece_type:
            promoted_token = color + promoted_type
            self._board.set(destination, promoted_token)

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
