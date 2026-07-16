# Real-time motion coordinator — fully typed, string-blind.
from __future__ import annotations
from typing import Optional
from chess_engine.model.board import Board
from chess_engine.model.piece import Piece, PieceType, Color, PieceState
from chess_engine.model.position import Position
from chess_engine.realtime.motion import Motion
from chess_engine.rules.movement import legal_destinations
from chess_engine.rules.trajectory import linear_path
from config import CELL_SIZE, PIECE_SPEED

_COOLDOWN_MS = 1000
_PROMOTION_TYPE = PieceType.QUEEN


def _promoted(piece: Piece, row: int, max_rows: int) -> Piece:
    # Return a promoted Piece if the pawn reached its back rank, else same piece.
    if piece.piece_type != PieceType.PAWN:
        return piece
    promotion_row = 0 if piece.color == Color.WHITE else (max_rows - 1)
    if row == promotion_row:
        return Piece(_PROMOTION_TYPE, piece.color)
    return piece


class RealTimeArbiter:
    # Coordinate multiple active motions and resolve arrivals atomically.

    def __init__(self, board: Board, game_engine: Optional[object] = None) -> None:
        self._board = board
        self._game_engine = game_engine
        self._active_motions: list[Motion] = []
        self._active_piece: Optional[Piece] = None
        self._motion_pieces: dict[Motion, Piece] = {}
        self._cooldowns: dict[Position, int] = {}
        self._captures: list[tuple[Piece, Color]] = []

    @property
    def active_motion(self) -> Optional[Motion]:
        return self._active_motions[-1] if self._active_motions else None

    @property
    def active_piece(self) -> Optional[Piece]:
        return self._active_piece

    @property
    def game_engine(self) -> Optional[object]:
        return self._game_engine

    @game_engine.setter
    def game_engine(self, value: Optional[object]) -> None:
        self._game_engine = value

    def attach_game_engine(self, game_engine: object) -> None:
        self.game_engine = game_engine

    def has_active_motion(self) -> bool:
        return bool(self._active_motions)

    def get_active_motions(self) -> list[Motion]:
        return list(self._active_motions)

    def get_cooldowns(self) -> dict[Position, int]:
        return dict(self._cooldowns)

    def take_captures(self) -> list[tuple[Piece, Color]]:
        # Drain and return capture events recorded since the last call
        # (mid-route / jump-defense captures only — see _capture_motion).
        captures = self._captures
        self._captures = []
        return captures

    def start_motion(
        self,
        piece: Piece,
        source: Position,
        destination: Position,
        duration_ms: Optional[int] = None,
    ) -> None:
        resolved_duration = (
            duration_ms if duration_ms is not None
            else self._calculate_duration_ms(source, destination)
        )
        motion = Motion(piece=piece, source=source, destination=destination,
                        elapsed_ms=0, duration_ms=resolved_duration)
        self._active_motions.append(motion)
        self._active_piece = Piece(piece.piece_type, piece.color)
        self._active_piece.state = PieceState.MOVING
        self._motion_pieces[motion] = self._active_piece

    def is_in_cooldown(self, pos: Position) -> bool:
        if pos not in self._cooldowns:
            return False
        piece = self._board.get(pos)
        return piece is not None and piece.state != PieceState.MOVING

    def is_destination_claimed(self, destination: Position, color: Color) -> bool:
        # True if a friendly piece is already mid-flight (or holding a jump)
        # to this square — the board itself won't show that until it lands,
        # so callers must ask here before starting a second motion onto it.
        for motion in self._active_motions:
            if motion.source == motion.destination:
                continue
            if motion.destination == destination and motion.piece.color == color:
                return True
        return False

    def advance_time(self, ms: int) -> None:
        if ms <= 0:
            return
        self._cooldowns = {
            pos: remaining - ms
            for pos, remaining in self._cooldowns.items()
            if remaining - ms > 0
        }
        if not self._active_motions:
            return
        for motion in list(self._active_motions):
            motion.elapsed_ms += ms
        self._resolve_mid_route_collisions()
        completed: list[tuple[int, int, Motion]] = []
        for index, motion in enumerate(self._active_motions):
            if motion.elapsed_ms >= motion.duration_ms:
                is_hold = motion.source == motion.destination
                if is_hold and self._has_pending_enemy_contest(motion):
                    continue
                priority = 0 if not is_hold else 1
                completed.append((priority, index, motion))
        if not completed:
            return
        completed.sort(key=lambda item: (item[0], item[1]))
        for _, _, motion in completed:
            if motion in self._active_motions:
                self._active_motions.remove(motion)
                self._resolve_arrival(motion)

    def _has_pending_enemy_contest(self, motion: Motion) -> bool:
        for other in self._active_motions:
            if other is motion or other.piece.color == motion.piece.color:
                continue
            if other.destination != motion.source or other.elapsed_ms >= other.duration_ms:
                continue
            if other.duration_ms <= motion.duration_ms:
                return True
        return False

    def _current_cell(self, motion: Motion) -> Position:
        if motion.source == motion.destination or motion.duration_ms == 0:
            return motion.source
        path = linear_path(motion.source, motion.destination)
        if len(path) <= 1:
            return motion.source
        ratio = min(motion.elapsed_ms / motion.duration_ms, 1.0)
        return path[int(ratio * (len(path) - 1))]

    def _cancel_motion(self, motion: Motion, land_at: Position) -> None:
        if motion in self._active_motions:
            self._active_motions.remove(motion)
        self._board.set(motion.source, None)
        self._board.set(land_at, motion.piece)
        self._cooldowns[land_at] = _COOLDOWN_MS
        piece = self._motion_pieces.pop(motion, None)
        if piece is not None:
            piece.state = PieceState.IDLE

    def _resolve_mid_route_collisions(self) -> None:
        motions = list(self._active_motions)
        to_cancel: dict[Motion, Position] = {}
        to_capture: dict[Motion, Color] = {}
        for i in range(len(motions)):
            for j in range(i + 1, len(motions)):
                a, b = motions[i], motions[j]
                if a in to_cancel or b in to_cancel or a in to_capture or b in to_capture:
                    continue
                cell_a = self._current_cell(a)
                cell_b = self._current_cell(b)
                if cell_a != cell_b:
                    continue
                is_hold_a = a.source == a.destination
                is_hold_b = b.source == b.destination
                if is_hold_a != is_hold_b:
                    # A piece actively jumping in place is never the one
                    # captured: it survives and captures whichever enemy
                    # motion lands on its cell while it is mid-jump.
                    holder, attacker = (a, b) if is_hold_a else (b, a)
                    if holder.piece.color != attacker.piece.color:
                        to_capture[attacker] = holder.piece.color
                    continue
                a_done = a.elapsed_ms >= a.duration_ms
                b_done = b.elapsed_ms >= b.duration_ms
                if a_done and b_done:
                    continue
                if a_done and not b_done:
                    later, earlier = b, a
                elif b_done and not a_done:
                    later, earlier = a, b
                else:
                    remaining_a = a.duration_ms - a.elapsed_ms
                    remaining_b = b.duration_ms - b.elapsed_ms
                    later, earlier = (a, b) if remaining_a >= remaining_b else (b, a)
                if a.piece.color != b.piece.color:
                    to_capture[earlier] = later.piece.color
                else:
                    path = linear_path(later.source, later.destination)
                    to_cancel[later] = self._last_legal_stop_before(later, path, cell_a)
        for motion, land_at in to_cancel.items():
            if motion in self._active_motions:
                self._cancel_motion(motion, land_at)
        for motion, captor_color in to_capture.items():
            self._capture_motion(motion, captured_by=captor_color)

    def _capture_motion(self, motion: Motion, captured_by: Optional[Color] = None) -> None:
        if motion in self._active_motions:
            self._active_motions.remove(motion)
        self._board.set(motion.source, None)
        if motion.piece.piece_type == PieceType.KING and self._game_engine is not None:
            self._game_engine.notify_king_captured()
        if captured_by is not None:
            self._captures.append((motion.piece, captured_by))
        piece = self._motion_pieces.pop(motion, None)
        target = piece if piece is not None else motion.piece
        target.state = PieceState.CAPTURED

    def _last_legal_stop_before(
        self, motion: Motion, path: list[Position], collision_cell: Position
    ) -> Position:
        try:
            collision_index = path.index(collision_cell)
        except ValueError:
            return motion.source
        candidates = path[1:collision_index]
        legal = legal_destinations(self._board, motion.source, motion.piece)
        for candidate in reversed(candidates):
            if candidate in legal:
                return candidate
        return motion.source

    def _resolve_arrival(self, motion: Motion) -> None:
        victim = self._board.get(motion.destination)
        if victim is not None and motion.source != motion.destination and victim.color == motion.piece.color:
            # A friendly piece beat us to the destination while we were mid-
            # flight (the square looked empty when this motion was accepted).
            # We can't land on our own piece, so pull up short instead of
            # silently overwriting it.
            path = linear_path(motion.source, motion.destination)
            land_at = self._last_legal_stop_before(motion, path, motion.destination)
            piece = self._motion_pieces.pop(motion, None)
            if piece is not None:
                piece.state = PieceState.IDLE
            if land_at != motion.source:
                self._board.set(motion.source, None)
                self._board.set(land_at, motion.piece)
                self._cooldowns[land_at] = _COOLDOWN_MS
            return
        self._board.set(motion.source, None)
        if victim is not None and victim.piece_type == PieceType.KING:
            if self._game_engine is not None:
                self._game_engine.notify_king_captured()
        final_piece = _promoted(motion.piece, motion.destination.row, self._board.rows)
        self._board.set(motion.destination, final_piece)
        self._cooldowns[motion.destination] = _COOLDOWN_MS
        piece = self._motion_pieces.pop(motion, None)
        if piece is not None:
            piece.state = PieceState.IDLE

    def _calculate_duration_ms(self, source: Position, destination: Position) -> int:
        steps = max(abs(destination.row - source.row), abs(destination.col - source.col))
        return int(steps * CELL_SIZE / PIECE_SPEED * 1000)