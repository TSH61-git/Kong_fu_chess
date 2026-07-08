from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from core.interfaces.i_movement_validator import IMovementValidator
from core.interfaces.i_movement_strategy import IMovementStrategy
from core.game_clock import GameClock
from core.constants import (
    KING_TOKENS, EMPTY_CELL, MS_PER_CELL_TRAVEL,
    WHITE_COLOR, CELL_SIZE_PX,
)
@dataclass
class _PendingMove:
    piece:        str
    from_pos:     Tuple[int, int]
    to_pos:       Tuple[int, int]
    arrival_time: int


class GameService:
    def __init__(
        self,
        board: List[List[str]],
        validator: IMovementValidator,
        clock: GameClock,
        registry: Optional[Dict[str, IMovementStrategy]] = None,
    ) -> None:
        self._board = [row[:] for row in board]
        self._rows = len(board)
        self._cols = len(board[0]) if self._rows > 0 else 0
        self._validator = validator
        self._clock = clock
        self._registry = registry
        self._selected_pos: Optional[Tuple[int, int]] = None
        self._pending_moves: List[_PendingMove] = []
        self._game_over: bool = False

    # ------------------------------------------------------------------ #
    # Public interface                                                     #
    # ------------------------------------------------------------------ #

    def handle_click(self, x: int, y: int) -> None:
        # Ignore all inputs if the game has already ended
        if self._game_over:
            return

        col = x // CELL_SIZE_PX
        row = y // CELL_SIZE_PX

        if not (0 <= row < self._rows and 0 <= col < self._cols):
            return

        # Settle any arrivals before evaluating the current click
        self._flush_pending()

        token = self._board[row][col]

        if self._selected_pos is None:
            # Only select a piece that exists on the matrix and is not in-flight
            if token != EMPTY_CELL and not self._is_in_flight(row, col):
                self._selected_pos = (row, col)
            return

        curr_row, curr_col = self._selected_pos
        selected_token = self._board[curr_row][curr_col]

        # Re-select a friendly piece that is not currently in-flight
        if token != EMPTY_CELL and token[0] == selected_token[0]:  # same color
            if not self._is_in_flight(row, col):
                self._selected_pos = (row, col)
            return

        # Attempt move dispatching with geometric, cross-color concurrency, and head-on collision guards
        if self._validator.is_valid_move(
            self._board, selected_token, (curr_row, curr_col), (row, col)
        ) and not self._has_opposite_color_in_flight(selected_token[0]) \
          and not self._has_head_on_collision((curr_row, curr_col), (row, col)):
            
            dr = abs(row - curr_row)
            dc = abs(col - curr_col)
            arrival = self._clock.now() + max(dr, dc) * MS_PER_CELL_TRAVEL
            
            self._pending_moves.append(
                _PendingMove(selected_token, (curr_row, curr_col), (row, col), arrival)
            )
            # Note: The piece remains visible at its source cell on the matrix until arrival_time

        self._selected_pos = None

    def handle_wait(self, ms: int) -> None:
        self._clock.advance(ms)
        self._flush_pending()

    def get_board_lines(self) -> List[str]:
        return [' '.join(row) for row in self._board]

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _flush_pending(self) -> None:
        """Settle every move whose arrival_time <= clock.now()."""
        arrived = [m for m in self._pending_moves if self._clock.now() >= m.arrival_time]
        arrived.sort(key=lambda m: m.arrival_time)

        for move in arrived:
            if self._game_over:
                break
            self._apply_single_move(move)

        if self._game_over:
            self._pending_moves.clear()

    def _apply_single_move(self, move: _PendingMove) -> None:
        """Mutate the board for one arrived move and handle game-over / on_land hooks."""
        r1, c1 = move.from_pos
        r2, c2 = move.to_pos

        if self._board[r2][c2] in KING_TOKENS:
            self._game_over = True
            self._board[r2][c2] = move.piece
            self._board[r1][c1] = EMPTY_CELL
            return

        self._board[r1][c1] = EMPTY_CELL

        # Delegate landing transformation to the strategy (e.g. pawn promotion)
        landed = move.piece
        if self._registry is not None:
            strategy = self._registry.get(move.piece[1])
            if strategy is not None:
                landed = strategy.on_land(self._board, move.piece, (r2, c2))

        self._board[r2][c2] = landed
        self._pending_moves.remove(move)

    def _is_in_flight(self, row: int, col: int) -> bool:
        """True if a piece at (row, col) has been dispatched but not yet arrived."""
        return any(m.from_pos == (row, col) for m in self._pending_moves)

    def _has_opposite_color_in_flight(self, color: str) -> bool:
        """True if any pending move belongs to the opposite color."""
        return any(m.piece[0] != color for m in self._pending_moves)

    def _has_head_on_collision(
        self, from_pos: Tuple[int, int], to_pos: Tuple[int, int]
    ) -> bool:
        """True if an existing pending move is travelling the exact reverse route."""
        return any(
            m.from_pos == to_pos and m.to_pos == from_pos
            for m in self._pending_moves
        )