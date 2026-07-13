"""Real-time motion coordinator for the application service layer."""
from __future__ import annotations

from typing import Optional

from model.board import Board
from model.piece import Piece, PieceState
from model.position import Position
from realtime.motion import Motion
from rules.movement_rules import legal_destinations
from rules.promotion_rules import get_promoted_token
from rules.route_rules import linear_path

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

        for motion in list(self._active_motions):
            motion.elapsed_ms += ms

        self._resolve_mid_route_collisions()

        completed: list[tuple[int, int, Motion]] = []
        for index, motion in enumerate(self._active_motions):
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

    # ------------------------------------------------------------------ #
    # Mid-route collision                                                  #
    # ------------------------------------------------------------------ #

    def _current_cell(self, motion: Motion) -> Position:
        """Return the logical grid cell the motion occupies at its current elapsed_ms.

        For in-place jumps (source == destination) the cell is always the source.
        For linear moves, map the elapsed ratio to the path index.
        """
        if motion.source == motion.destination or motion.duration_ms == 0:
            return motion.source

        path = linear_path(motion.source, motion.destination)
        if len(path) <= 1:
            return motion.source

        ratio = min(motion.elapsed_ms / motion.duration_ms, 1.0)
        index = int(ratio * (len(path) - 1))
        return path[index]

    def _cancel_motion(self, motion: Motion, land_at: Position) -> None:
        """Remove motion from active tracking and place the piece at land_at."""
        if motion in self._active_motions:
            self._active_motions.remove(motion)
        self._board.set(motion.source, ".")
        self._board.set(land_at, motion.piece)
        piece = self._motion_pieces.pop(motion, None)
        if piece is not None:
            piece.state = PieceState.IDLE

    def _resolve_mid_route_collisions(self) -> None:
        """Detect and resolve mid-route collisions between all active motion pairs.

        Enemy collision: the piece that arrived at the shared cell later captures
        the one that arrived earlier — the earlier motion is cancelled at that cell.

        Friendly collision: the later-arriving piece is stopped at the last legal
        cell before the collision point. If no legal intermediate stop exists the
        motion is reverted to its source.
        """
        motions = list(self._active_motions)
        to_cancel: dict[Motion, Position] = {}

        for i in range(len(motions)):
            for j in range(i + 1, len(motions)):
                a, b = motions[i], motions[j]
                if a in to_cancel or b in to_cancel:
                    continue

                cell_a = self._current_cell(a)
                cell_b = self._current_cell(b)

                if cell_a != cell_b:
                    continue

                color_a = a.piece[0] if len(a.piece) >= 1 else ""
                color_b = b.piece[0] if len(b.piece) >= 1 else ""

                # In-place jumps are treated as already-settled on their cell,
                # so a linear mover arriving at the same cell is always "later".
                a_is_jump = a.source == a.destination
                b_is_jump = b.source == b.destination
                if a_is_jump and not b_is_jump:
                    later, earlier = b, a
                elif b_is_jump and not a_is_jump:
                    later, earlier = a, b
                else:
                    ratio_a = a.elapsed_ms / a.duration_ms if a.duration_ms > 0 else 1.0
                    ratio_b = b.elapsed_ms / b.duration_ms if b.duration_ms > 0 else 1.0
                    later, earlier = (b, a) if ratio_b >= ratio_a else (a, b)

                if color_a != color_b:
                    # Enemy: later piece captures earlier.
                    # Special case: if the earlier piece is a stationary jump, it holds
                    # its cell — the incoming linear piece is stopped one cell before it.
                    if earlier.source == earlier.destination:
                        # Jump holds the cell; stop the linear piece one step before.
                        path = linear_path(later.source, later.destination)
                        stop_cell = self._last_legal_stop_before(later, path, cell_a)
                        to_cancel[later] = stop_cell
                    else:
                        # Normal case: cancel the earlier motion at the collision cell.
                        to_cancel[earlier] = cell_a
                else:
                    # Friendly: stop the later piece before the collision cell
                    path = linear_path(later.source, later.destination)
                    stop_cell = self._last_legal_stop_before(later, path, cell_a)
                    to_cancel[later] = stop_cell

        for motion, land_at in to_cancel.items():
            if motion in self._active_motions:
                self._cancel_motion(motion, land_at)

    def _last_legal_stop_before(
        self, motion: Motion, path: list[Position], collision_cell: Position
    ) -> Position:
        """Return the last legal intermediate stop before collision_cell on path.

        Walks path candidates in reverse from just before the collision cell.
        Returns the first cell that is a legal destination from the source, or
        the motion's source if no legal intermediate stop exists.
        """
        try:
            collision_index = path.index(collision_cell)
        except ValueError:
            return motion.source

        candidates = path[1:collision_index]  # exclude source and collision cell
        legal = legal_destinations(self._board, motion.source, motion.piece)
        for candidate in reversed(candidates):
            if candidate in legal:
                return candidate

        return motion.source

    # ------------------------------------------------------------------ #
    # Arrival resolution                                                   #
    # ------------------------------------------------------------------ #

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
        """Check if a piece should be promoted upon arrival and apply the transformation."""
        if len(piece_token) < 2:
            return

        color = piece_token[0]
        piece_type = piece_token[1]

        promoted_type = get_promoted_token(
            piece_type, destination.row, self._board.rows, color
        )

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
