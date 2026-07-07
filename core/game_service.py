from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional
from core.interfaces.i_movement_validator import IMovementValidator
from core.game_clock import GameClock
from core.constants import KING_TOKENS, EMPTY_CELL, MS_PER_CELL_TRAVEL
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
    ) -> None:
        self._board = board
        self._rows = len(board)
        self._cols = len(board[0]) if self._rows > 0 else 0
        self._validator = validator
        self._clock = clock
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

        col = x // 100
        row = y // 100

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
        if token != EMPTY_CELL and token[0] == selected_token[0]:
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
        self._flush_pending()
        return [' '.join(row) for row in self._board]

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _flush_pending(self) -> None:
        """Atomically settle every move whose arrival_time <= clock.now()."""
        arrived = [m for m in self._pending_moves if self._clock.now() >= m.arrival_time]
        
        # Sort arrived moves chronologically to guarantee correct arrival order resolution
        arrived.sort(key=lambda x: x.arrival_time)
        
        for move in arrived:
            if self._game_over:
                break

            r1, c1 = move.from_pos
            r2, c2 = move.to_pos
            
            # Check if the target landing square contains an enemy King
            if self._board[r2][c2] in KING_TOKENS:
                self._game_over = True
                self._board[r2][c2] = move.piece  # Execute the winning capture immediately
                self._board[r1][c1] = EMPTY_CELL       # Clear the source cell
                break  # Exit loop immediately to prevent processing remaining moves after Game Over
                
            # Process a standard non-king capture or movement
            self._board[r2][c2] = move.piece  
            self._board[r1][c1] = EMPTY_CELL       
            if move in self._pending_moves:
                self._pending_moves.remove(move)

        # Safely discard all remaining in-flight moves after the loop terminates due to Game Over
        if self._game_over:
            self._pending_moves.clear()

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